"""Editor konten (guru) — buffer draft di DB, publish tulis ke file .md.

Endpoints (isi teks, per-file, model buffer→publish):
    GET    /content/drafts?target_path=...    ambil draft aktif (atau file asli bila belum ada draft)
    POST   /content/drafts                    simpan buffer {target_path, body}
    POST   /content/preview                   render {body} → HTML pakai parser asli
    POST   /content/drafts/<id>/publish       tulis draft.body ke file
    DELETE /content/drafts/<id>                buang draft

Endpoints tree (operasi struktural, langsung ke disk — lihat §3.3):
    GET    /content/tree                       daftar rekursif file+folder
    POST   /content/tree/folder                buat folder
    POST   /content/tree/file                  buat file .md baru
    PATCH  /content/tree/rename                rename/move file atau folder
    DELETE /content/tree/entry                 hapus file atau folder
    POST   /content/assets/upload              upload gambar

Keamanan: pola sama seperti routes/student_management.py — cookie guru,
origin check, path traversal protection ketat pada semua path yang diterima.
"""

import base64
import binascii
import io
import os
import re as _re
import shutil

from flask import Blueprint, jsonify, request

from config import ASSETS_DIR, CONTENT_DIR
from services import repositories
from services.database import SessionLocal
from services.lesson_service import _render_markdown_string
from services.teacher_auth import check_origin, teacher_user_from_cookie

content_editor_bp = Blueprint("content_editor", __name__, url_prefix="/content")

_CONTENT_DIR_ABS = os.path.abspath(CONTENT_DIR)
_ASSETS_DIR_ABS = os.path.abspath(ASSETS_DIR)
_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_MAX_ASSET_BYTES = 5 * 1024 * 1024
_PROTECTED_BASENAMES = {"home.md", "sub-home.md"}


def _is_protected(rel: str) -> bool:
    """True bila path relatif (terhadap root content) merujuk ke file navigasi
    kritis (home.md atau sub-home.md) yang kehilanganannya merusak seluruh
    navigasi situs."""
    return os.path.basename(rel) in _PROTECTED_BASENAMES


def _safe_target_path(raw: str) -> str | None:
    """Validasi & normalisasi target_path relatif CONTENT_DIR, wajib .md."""
    if not raw or not raw.endswith(".md"):
        return None
    candidate = os.path.abspath(os.path.join(_CONTENT_DIR_ABS, raw))
    if not candidate.startswith(_CONTENT_DIR_ABS + os.sep):
        return None
    return raw


def _require_teacher(db):
    """Butuh db karena resolve user_id sungguhan lewat query token → User."""
    if not check_origin():
        return None, (jsonify({"success": False, "message": "Origin tidak diizinkan"}), 403)
    user = teacher_user_from_cookie(db)
    if not user:
        return None, (jsonify({"success": False, "message": "Butuh login guru"}), 401)
    return user, None


# ── Draft endpoints (isi teks, per-file) ─────────────────────────

@content_editor_bp.route("/drafts", methods=["GET"])
def get_draft():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        target_path = _safe_target_path(request.args.get("target_path", ""))
        if not target_path:
            return jsonify({"success": False, "message": "target_path tidak valid"}), 400

        draft = repositories.get_active_draft(db, target_path=target_path)
        if draft:
            return jsonify({
                "success": True, "source": "draft",
                "draft_id": draft.id, "body": draft.body,
                "base_mtime": draft.base_mtime,
            })

        abs_path = os.path.join(_CONTENT_DIR_ABS, target_path)
        if not os.path.isfile(abs_path):
            return jsonify({"success": False, "message": "File tidak ditemukan"}), 404
        with open(abs_path, "r", encoding="utf-8") as f:
            body = f.read()
        return jsonify({
            "success": True, "source": "file",
            "draft_id": None, "body": body,
            "base_mtime": os.path.getmtime(abs_path),
        })
    finally:
        db.close()


@content_editor_bp.route("/drafts", methods=["POST"])
def save_draft():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        data = request.get_json(silent=True, force=True) or {}
        target_path = _safe_target_path(data.get("target_path", ""))
        if not target_path:
            return jsonify({"success": False, "message": "target_path tidak valid"}), 400
        body = data.get("body", "")
        base_mtime = data.get("base_mtime")

        draft = repositories.upsert_draft(
            db, author_id=user.id, target_path=target_path,
            body=body, base_mtime=base_mtime,
        )
        return jsonify({"success": True, "draft_id": draft.id, "updated_at": draft.updated_at.isoformat()})
    finally:
        db.close()


@content_editor_bp.route("/preview", methods=["POST"])
def preview():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        data = request.get_json(silent=True, force=True) or {}
        body = data.get("body", "")
        try:
            parsed = _render_markdown_string(body)
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 422
        return jsonify({
            "success": True,
            "lesson_content": parsed["lesson_html"],
            "exercise_content": parsed["exercise_html"],
            "quiz_data": parsed.get("quiz_data", []),
            "slides": parsed.get("slides", []),
            "active_tabs": parsed.get("active_tabs", []),
        })
    finally:
        db.close()


@content_editor_bp.route("/drafts/<draft_id>/publish", methods=["POST"])
def publish(draft_id):
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        draft = db.query(repositories.ContentDraft).filter(
            repositories.ContentDraft.id == draft_id
        ).first()
        if not draft or draft.status != "draft":
            return jsonify({"success": False, "message": "Draft tidak ditemukan"}), 404

        target_path = _safe_target_path(draft.target_path)
        if not target_path:
            return jsonify({"success": False, "message": "target_path tidak valid"}), 400
        abs_path = os.path.join(_CONTENT_DIR_ABS, target_path)

        # Deteksi konflik: file berubah di disk sejak draft dibuat/di-refresh.
        if os.path.exists(abs_path) and draft.base_mtime is not None:
            current_mtime = os.path.getmtime(abs_path)
            if abs(current_mtime - draft.base_mtime) > 0.001:
                return jsonify({
                    "success": False, "message": "conflict",
                    "detail": "File berubah di server sejak draft ini dibuat. "
                              "Muat ulang isi terbaru sebelum publish.",
                }), 409

        # Validasi sebelum menulis — jangan pernah publish konten yang gagal parse.
        try:
            _render_markdown_string(draft.body)
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 422

        # Guard khusus home.md/sub-home.md: marker navigasi wajib ada.
        base_name = os.path.basename(target_path)
        if base_name in _PROTECTED_BASENAMES and "---Available_Lessons---" not in draft.body:
            return jsonify({
                "success": False,
                "message": f"Marker ---Available_Lessons--- hilang dari {base_name} — "
                            "publish dibatalkan supaya navigasi tidak rusak.",
            }), 422

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        try:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(draft.body)
        except PermissionError:
            return jsonify({
                "success": False,
                "message": "Permission denied — tidak bisa menulis ke file di server. "
                            "Pastikan folder content/ memiliki izin tulis untuk container.",
            }), 403
        except OSError as e:
            return jsonify({
                "success": False,
                "message": f"Gagal menulis file: {e}",
            }), 500

        repositories.mark_draft_published(db, draft=draft)
        return jsonify({"success": True, "published_path": target_path})
    finally:
        db.close()


@content_editor_bp.route("/drafts/<draft_id>", methods=["DELETE"])
def delete_draft(draft_id):
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        ok = repositories.discard_draft(db, draft_id=draft_id, author_id=user.id)
        return jsonify({"success": ok})
    finally:
        db.close()


# ── Tree endpoints (operasi struktural) ──────────────────────────

def _root_dir(root: str) -> str | None:
    if root == "content":
        return _CONTENT_DIR_ABS
    if root == "assets":
        return _ASSETS_DIR_ABS
    return None


def _safe_rel_path(root_abs: str, raw: str) -> str | None:
    """Sama seperti _safe_target_path tapi generik untuk root manapun,
    tanpa syarat ekstensi .md (dipakai juga untuk folder & assets)."""
    if not raw or raw.startswith("/") or ".." in raw.split("/"):
        return None
    candidate = os.path.abspath(os.path.join(root_abs, raw))
    if not candidate.startswith(root_abs + os.sep) and candidate != root_abs:
        return None
    return raw


def _build_tree(root_abs: str, allowed_ext: set | None) -> list[dict]:
    """Tree rekursif. allowed_ext=None → semua file (Assets);
    allowed_ext={'.md'} → filter (Materi)."""
    def walk(dir_abs: str, rel_prefix: str) -> list[dict]:
        entries = []
        try:
            items = sorted(os.scandir(dir_abs), key=lambda e: (e.is_file(), e.name.lower()))
        except OSError:
            return entries
        for entry in items:
            rel = f"{rel_prefix}{entry.name}"
            if entry.is_dir():
                entries.append({
                    "type": "folder", "name": entry.name, "path": rel,
                    "children": walk(entry.path, rel + "/"),
                })
            elif entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if allowed_ext is not None and ext not in allowed_ext:
                    continue
                entries.append({"type": "file", "name": entry.name, "path": rel, "ext": ext})
        return entries
    return walk(root_abs, "")


@content_editor_bp.route("/tree", methods=["GET"])
def get_tree():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        root = request.args.get("root", "content")
        root_abs = _root_dir(root)
        if not root_abs:
            return jsonify({"success": False, "message": "root tidak valid"}), 400
        allowed = {".md"} if root == "content" else None
        return jsonify({"success": True, "root": root, "tree": _build_tree(root_abs, allowed)})
    finally:
        db.close()


@content_editor_bp.route("/tree/folder", methods=["POST"])
def create_folder():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        data = request.get_json(silent=True, force=True) or {}
        root = data.get("root", "content")
        root_abs = _root_dir(root)
        if not root_abs:
            return jsonify({"success": False, "message": "root tidak valid"}), 400
        rel = _safe_rel_path(root_abs, data.get("path", ""))
        if not rel:
            return jsonify({"success": False, "message": "path tidak valid"}), 400
        abs_path = os.path.join(root_abs, rel)
        if os.path.exists(abs_path):
            return jsonify({"success": False, "message": "Folder sudah ada"}), 409
        try:
            os.makedirs(abs_path)
        except PermissionError:
            return jsonify({"success": False, "message": "Permission denied — tidak bisa membuat folder"}), 403
        return jsonify({"success": True, "path": rel})
    finally:
        db.close()


@content_editor_bp.route("/tree/file", methods=["POST"])
def create_file():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        data = request.get_json(silent=True, force=True) or {}
        root = data.get("root", "content")
        if root != "content":
            return jsonify({"success": False, "message": "File baru hanya untuk Materi; Assets lewat upload"}), 400
        rel = _safe_target_path(data.get("path", ""))  # sudah wajibkan .md
        if not rel:
            return jsonify({"success": False, "message": "path tidak valid (harus .md)"}), 400
        abs_path = os.path.join(_CONTENT_DIR_ABS, rel)
        if os.path.exists(abs_path):
            return jsonify({"success": False, "message": "File sudah ada"}), 409
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        template = data.get("template") or "# Judul Materi Baru\n\nTulis isi materi di sini.\n"
        try:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(template)
        except PermissionError:
            return jsonify({"success": False, "message": "Permission denied — tidak bisa menulis file"}), 403
        return jsonify({"success": True, "path": rel})
    finally:
        db.close()


@content_editor_bp.route("/tree/rename", methods=["PATCH"])
def rename_entry():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        data = request.get_json(silent=True, force=True) or {}
        root = data.get("root", "content")
        root_abs = _root_dir(root)
        if not root_abs:
            return jsonify({"success": False, "message": "root tidak valid"}), 400
        old_rel = _safe_rel_path(root_abs, data.get("old_path", ""))
        new_rel = _safe_rel_path(root_abs, data.get("new_path", ""))
        if not old_rel or not new_rel:
            return jsonify({"success": False, "message": "path tidak valid"}), 400

        # P1-2: rename di root content wajib hasil & sumber berekstensi .md
        if root == "content" and not new_rel.endswith(".md"):
            return jsonify({"success": False, "message": "Materi hanya boleh berekstensi .md"}), 400

        # P0-1: blokir rename file navigasi kritis tanpa konfirmasi eksplisit
        if root == "content" and _is_protected(old_rel) and not data.get("confirm_critical"):
            return jsonify({
                "success": False, "message": "protected",
                "detail": f"'{os.path.basename(old_rel)}' adalah file navigasi penting. "
                          "Konfirmasi ulang untuk melanjutkan.",
            }), 409

        old_abs = os.path.join(root_abs, old_rel)
        new_abs = os.path.join(root_abs, new_rel)
        if not os.path.exists(old_abs):
            return jsonify({"success": False, "message": "Sumber tidak ditemukan"}), 404
        if os.path.exists(new_abs):
            return jsonify({"success": False, "message": "Tujuan sudah ada"}), 409

        os.makedirs(os.path.dirname(new_abs), exist_ok=True)
        try:
            shutil.move(old_abs, new_abs)
        except PermissionError:
            return jsonify({"success": False, "message": "Permission denied — tidak bisa rename"}), 403

        if root == "content":
            repositories.retarget_drafts(db, old_prefix=old_rel, new_prefix=new_rel)
        return jsonify({"success": True, "path": new_rel})
    finally:
        db.close()


@content_editor_bp.route("/tree/entry", methods=["DELETE"])
def delete_entry():
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        root = request.args.get("root", "content")
        root_abs = _root_dir(root)
        if not root_abs:
            return jsonify({"success": False, "message": "root tidak valid"}), 400
        rel = _safe_rel_path(root_abs, request.args.get("path", ""))
        if not rel:
            return jsonify({"success": False, "message": "path tidak valid"}), 400

        # P0-1: blokir delete file navigasi kritis (home.md, sub-home.md)
        # tanpa konfirmasi eksplisit dari user.
        if root == "content" and _is_protected(rel) and request.args.get("confirm_critical") != "true":
            return jsonify({
                "success": False, "message": "protected",
                "detail": f"'{os.path.basename(rel)}' adalah file navigasi penting. "
                          "Konfirmasi ulang untuk melanjutkan.",
            }), 409

        abs_path = os.path.join(root_abs, rel)
        if not os.path.exists(abs_path):
            return jsonify({"success": False, "message": "Tidak ditemukan"}), 404

        if os.path.isdir(abs_path):
            if os.listdir(abs_path) and request.args.get("force") != "true":
                return jsonify({"success": False, "message": "Folder tidak kosong", "needs_force": True}), 409
            try:
                shutil.rmtree(abs_path)
            except PermissionError:
                return jsonify({"success": False, "message": "Permission denied — tidak bisa menghapus folder"}), 403
        else:
            try:
                os.remove(abs_path)
            except PermissionError:
                return jsonify({"success": False, "message": "Permission denied — tidak bisa menghapus file"}), 403

        if root == "content":
            repositories.drop_drafts_under(db, path=rel)
        return jsonify({"success": True})
    finally:
        db.close()


@content_editor_bp.route("/assets/upload", methods=["POST"])
def upload_asset():
    """Body JSON (bukan multipart — lihat catatan proxy di hooks.server.ts):
    {"filename": "resistor.png", "folder": "diagrams", "content_base64": "..."}
    """
    db = SessionLocal()
    try:
        user, err = _require_teacher(db)
        if err:
            return err
        data = request.get_json(silent=True, force=True) or {}

        filename = (data.get("filename") or "").strip()
        if not filename:
            return jsonify({"success": False, "message": "filename wajib disertakan"}), 400
        ext = os.path.splitext(filename)[1].lower()
        if ext not in _ALLOWED_IMAGE_EXT:
            return jsonify({"success": False, "message": f"Ekstensi {ext} tidak diizinkan"}), 400

        folder = (data.get("folder") or "").strip()
        folder_rel = _safe_rel_path(_ASSETS_DIR_ABS, folder) if folder else ""
        if folder and folder_rel is None:
            return jsonify({"success": False, "message": "folder tidak valid"}), 400

        b64 = data.get("content_base64") or ""
        if len(b64) > (_MAX_ASSET_BYTES * 4 // 3) + 1024:
            return jsonify({"success": False, "message": "Ukuran file melebihi 5 MiB"}), 400
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            return jsonify({"success": False, "message": "content_base64 tidak valid"}), 400
        if not raw:
            return jsonify({"success": False, "message": "File kosong"}), 400
        if len(raw) > _MAX_ASSET_BYTES:
            return jsonify({"success": False, "message": "Ukuran file melebihi 5 MiB"}), 400

        # Validasi isi benar-benar gambar (bukan cuma cek ekstensi) — SVG
        # dikecualikan (Pillow tidak parse SVG).
        # Pakai .load() (decode sungguhan)而不是 .verify(): .verify() melakukan
        # CRC check strict pada IDAT yang sering FALSE-POSITIVE pada PNG valid
        # (terutama PNG sederhana / hasil re-encode) → backend 500. .load()
        # sudah cukup membuktikan file adalah gambar yang bisa di-decode.
        if ext != ".svg":
            try:
                from PIL import Image, UnidentifiedImageError
                im = Image.open(io.BytesIO(raw))
                im.load()  # raises jika bukan gambar yang bisa di-decode
            except ImportError:
                pass  # Pillow tidak terinstal — skip validasi gambar
            except (UnidentifiedImageError, OSError, SyntaxError):
                return jsonify({"success": False, "message": "File bukan gambar yang valid"}), 400

        safe_name = _re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(filename))
        rel_path = f"{folder_rel}/{safe_name}" if folder_rel else safe_name
        abs_path = os.path.join(_ASSETS_DIR_ABS, rel_path)
        if os.path.exists(abs_path):
            return jsonify({"success": False, "message": "Nama file sudah ada, ganti nama dulu"}), 409

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        try:
            with open(abs_path, "wb") as f:
                f.write(raw)
        except PermissionError:
            return jsonify({"success": False, "message": "Permission denied — tidak bisa menulis file"}), 403

        return jsonify({"success": True, "path": rel_path, "url": f"/assets/{rel_path}"})
    finally:
        db.close()
