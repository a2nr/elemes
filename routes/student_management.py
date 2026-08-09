"""
Student management (teacher-only) — round-trip CSV siswa.

Endpoints:
    POST /students/export-csv      JSON: {"student_ids": [...]}
    POST /students/import/preview  multipart: file
    POST /students/import          multipart: file
    POST /students/bulk-delete     JSON: {"student_ids": [...]}

Keamanan:
- Autentikasi guru HANYA dari cookie HttpOnly `student_token` — teacher token
  tidak diterima dari query maupun body.
- Validasi Origin untuk semua POST.
- Upload diproses in-memory (tidak pernah ditulis ke /tmp/filesystem).
- Response preview/import/delete TIDAK memuat raw token, token hash, maupun
  exception internal. Token plaintext tidak pernah di-log.
"""

import logging
import os
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from services import repositories
from services.database import SessionLocal
from services.student_roundtrip import (
    MAX_FILE_BYTES,
    RoundTripImportError,
    mask_student_id,
    parse_roundtrip_csv,
)
from services.token_service import validate_token

student_management_bp = Blueprint("student_management", __name__)

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"csv"}


def _teacher_from_cookie():
    """Guru dari cookie HttpOnly `student_token`; None bila tidak terautentikasi."""
    token = request.cookies.get("student_token", "")
    if not token:
        return None
    info = validate_token(token)
    if not info or not info.get("is_teacher"):
        return None
    return info


def _check_origin() -> bool:
    """Origin harus sesuai konfigurasi aplikasi (ORIGIN) bila origin dikirim."""
    allowed = os.environ.get("ORIGIN", "").strip()
    if not allowed or allowed == "*":
        return True
    origin = request.headers.get("Origin", "")
    if not origin:
        return True  # same-origin / non-browser client
    return origin in {allowed, allowed.rstrip("/")}


def _active_lesson_slugs():
    if SessionLocal is None:
        return []
    db = SessionLocal()
    try:
        return [lesson.slug for lesson in repositories.list_active_lessons(db)]
    finally:
        db.close()


def _read_csv_upload():
    """Baca file multipart in-memory. Return (bytes, filename) atau raise ValueError."""
    file = request.files.get("file")
    if file is None or not file.filename:
        raise ValueError("File CSV wajib disertakan (field 'file')")
    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Ekstensi file harus .csv")
    # Cek ukuran SEBELUM membaca isi agar upload raksasa tidak di-buffer penuh.
    content_length = getattr(file, "content_length", None)
    if content_length and content_length > MAX_FILE_BYTES:
        raise ValueError(f"File melebihi batas {MAX_FILE_BYTES // (1024 * 1024)} MiB")
    content = file.read()
    if not content:
        raise ValueError("File kosong")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"File melebihi batas {MAX_FILE_BYTES // (1024 * 1024)} MiB")
    return content, filename


@student_management_bp.route("/students/export-csv", methods=["POST"])
def export_students():
    if not _check_origin():
        return jsonify({"success": False, "message": "Origin tidak diizinkan"}), 403
    teacher = _teacher_from_cookie()
    if teacher is None:
        return jsonify({"success": False, "message": "Unauthorized (Teacher only)"}), 401
    if SessionLocal is None:
        return jsonify({"success": False, "message": "PostgreSQL tidak aktif"}), 503

    try:
        data = request.get_json(silent=True, force=True) or {}
        student_ids = data.get("student_ids", []) or []
    except Exception:  # noqa: BLE001
        student_ids = []

    db = SessionLocal()
    try:
        csv_bytes = repositories.export_students_csv(db, student_ids)
    except ValueError as exc:
        db.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:  # noqa: BLE001 — jangan bocorkan detail internal
        db.rollback()
        logger.exception("Export CSV gagal")
        return jsonify({"success": False, "message": "Gagal mengekspor siswa"}), 500
    finally:
        db.close()

    filename = f"data_siswa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@student_management_bp.route("/students/import/preview", methods=["POST"])
def import_preview():
    if not _check_origin():
        return jsonify({"success": False, "message": "Origin tidak diizinkan"}), 403
    teacher = _teacher_from_cookie()
    if teacher is None:
        return jsonify({"success": False, "message": "Unauthorized (Teacher only)"}), 401
    if SessionLocal is None:
        return jsonify({"success": False, "message": "PostgreSQL tidak aktif"}), 503

    try:
        content, _filename = _read_csv_upload()
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    try:
        rows = parse_roundtrip_csv(content, _active_lesson_slugs())
    except RoundTripImportError as exc:
        return jsonify({"success": False, "message": "File tidak valid", "errors": exc.errors}), 400

    db = SessionLocal()
    try:
        summary = repositories.preview_student_import(db, rows)
    finally:
        db.close()

    # Preview memakai nama & masked student_id — TIDAK token/hash.
    preview_rows = [
        {
            "line": row.line,
            "student_id": mask_student_id(row.student_id),
            "nama_siswa": row.display_name,
            "progress_lessons": len(row.progress),
        }
        for row in rows
    ]
    return jsonify({"success": True, "summary": summary, "rows": preview_rows})


@student_management_bp.route("/students/import", methods=["POST"])
def import_students():
    if not _check_origin():
        return jsonify({"success": False, "message": "Origin tidak diizinkan"}), 403
    teacher = _teacher_from_cookie()
    if teacher is None:
        return jsonify({"success": False, "message": "Unauthorized (Teacher only)"}), 401
    if SessionLocal is None:
        return jsonify({"success": False, "message": "PostgreSQL tidak aktif"}), 503

    try:
        content, _filename = _read_csv_upload()
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    try:
        rows = parse_roundtrip_csv(content, _active_lesson_slugs())
    except RoundTripImportError as exc:
        return jsonify({"success": False, "message": "File tidak valid", "errors": exc.errors}), 400

    db = SessionLocal()
    try:
        result = repositories.run_student_import(db, rows)
    except RoundTripImportError as exc:
        db.rollback()
        return jsonify(
            {
                "success": False,
                "message": "Import ditolak — ada data siswa/token yang bertentangan dengan database",
                "errors": exc.errors,
            }
        ), 409
    except Exception:  # noqa: BLE001 — jangan bocorkan exception internal
        db.rollback()
        logger.exception("Import CSV gagal")
        return jsonify({"success": False, "message": "Gagal mengimpor siswa"}), 500
    finally:
        db.close()

    logger.info(
        "Import CSV: students_created=%s students_updated=%s "
        "progress_created=%s progress_restored=%s",
        result["students_created"],
        result["students_updated"],
        result["progress_created"],
        result["progress_restored"],
    )
    return jsonify(
        {
            "success": True,
            "students_created": result["students_created"],
            "students_updated": result["students_updated"],
            "progress_created": result["progress_created"],
            "progress_restored": result["progress_restored"],
        }
    )


@student_management_bp.route("/students/bulk-delete", methods=["POST"])
def bulk_delete():
    if not _check_origin():
        return jsonify({"success": False, "message": "Origin tidak diizinkan"}), 403
    teacher = _teacher_from_cookie()
    if teacher is None:
        return jsonify({"success": False, "message": "Unauthorized (Teacher only)"}), 401
    if SessionLocal is None:
        return jsonify({"success": False, "message": "PostgreSQL tidak aktif"}), 503

    try:
        data = request.get_json(silent=True, force=True) or {}
        student_ids = data.get("student_ids", [])
    except Exception:  # noqa: BLE001
        student_ids = []

    db = SessionLocal()
    try:
        deleted_ids = repositories.delete_students(db, student_ids)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Bulk delete gagal")
        return jsonify({"success": False, "message": "Gagal menghapus siswa"}), 500
    finally:
        db.close()

    return jsonify(
        {
            "success": True,
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids,
        }
    )
