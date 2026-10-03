"""
Route test content editor (teacher-only) — butuh PostgreSQL.

Mengunci kontrak:
- autentikasi guru dari cookie HttpOnly student_token;
- draft CRUD, preview, publish dengan validasi & konflik mtime;
- tree operasi struktural (create, rename, delete) + path traversal protection;
- upload asset (JSON+base64) dengan validasi ekstensi & ukuran;
- guard home.md marker ---Available_Lessons---;
- regression: _render_markdown_string() == render_markdown_content() untuk file yang sama;
"""

import io
import os
import pathlib
import shutil
import time
import zipfile

import pytest

from services import repositories as repo
from services.database import SessionLocal
from services.tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

DB_REQUIRED = os.environ.get("DATABASE_URL", "").strip()

pytestmark = [
    pytest.mark.skipif(
        not DB_REQUIRED,
        reason="butuh DATABASE_URL (PostgreSQL nyata)",
    ),
    pytest.mark.integration,
]

# ── Fixtures ──────────────────────────────────────────────────────

TEST_CONTENT = pathlib.Path(os.environ.get("CONTENT_DIR", "/tmp/lms-contract/content"))
TEST_ASSETS = TEST_CONTENT.parent / "assets"


def _seed(db):
    teacher = repo.create_user(db, display_name="Pak Guru", role="teacher")
    repo.create_access_token(db, user_id=teacher.id, raw_token=TEACHER_TOKEN)
    student = repo.create_user(db, display_name="Budi Santoso", role="student")
    repo.create_access_token(db, user_id=student.id, raw_token=STUDENT_TOKEN)
    db.commit()
    return {"teacher": teacher, "student": student}


def _seed_and_setup():
    db = SessionLocal()
    try:
        data = _seed(db)
    finally:
        db.close()
    # Create test content files
    test_dir = TEST_CONTENT / "test_editor"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "hello.md").write_text("# Hello World\n\nIni materi test.\n", encoding="utf-8")
    (test_dir / "quiz.md").write_text(
        "# Quiz Test\n\n### Soal 1\n- [] Opsi A\n- [x] Opsi B\n- [] Opsi C\n",
        encoding="utf-8",
    )
    home = TEST_CONTENT / "home.md"
    if not home.exists():
        home.write_text(
            "# Home\n\n---Available_Lessons---\n\n[Hello](lesson/hello.md)\n",
            encoding="utf-8",
        )
    # Create assets dir
    TEST_ASSETS.mkdir(parents=True, exist_ok=True)
    return data


def _login_teacher(client):
    client.set_cookie("student_token", TEACHER_TOKEN)


def _login_student(client):
    client.set_cookie("student_token", STUDENT_TOKEN)


# ── Auth tests ────────────────────────────────────────────────────

def test_draft_requires_teacher(client):
    _seed_and_setup()
    resp = client.get("/content/drafts?target_path=test_editor/hello.md")
    assert resp.status_code == 401


def test_draft_rejects_student(client):
    _seed_and_setup()
    _login_student(client)
    resp = client.get("/content/drafts?target_path=test_editor/hello.md")
    assert resp.status_code == 401


def test_tree_requires_teacher(client):
    _seed_and_setup()
    resp = client.get("/content/tree?root=content")
    assert resp.status_code == 401


# ── Draft GET (file source) ──────────────────────────────────────

def test_get_draft_from_file(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.get("/content/drafts?target_path=test_editor/hello.md")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["source"] == "file"
    assert data["draft_id"] is None
    assert "Hello World" in data["body"]
    assert data["base_mtime"] is not None


def test_get_draft_invalid_path(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.get("/content/drafts?target_path=../../etc/passwd")
    assert resp.status_code == 400


def test_get_draft_missing_file(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.get("/content/drafts?target_path=nonexistent.md")
    assert resp.status_code == 404


def test_get_draft_non_md_rejected(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.get("/content/drafts?target_path=test_editor/hello.txt")
    assert resp.status_code == 400


# ── Draft POST (save) + GET (from draft) ─────────────────────────

def test_save_and_get_draft(client):
    _seed_and_setup()
    _login_teacher(client)

    # Save a draft
    resp = client.post("/content/drafts", json={
        "target_path": "test_editor/hello.md",
        "body": "# Draft Content\n\nIsi draft.",
        "base_mtime": 12345.0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    draft_id = data["draft_id"]

    # Get it back — should be from draft
    resp = client.get("/content/drafts?target_path=test_editor/hello.md")
    data = resp.get_json()
    assert data["success"] is True
    assert data["source"] == "draft"
    assert data["draft_id"] == draft_id
    assert "Draft Content" in data["body"]


# ── Preview ───────────────────────────────────────────────────────

def test_preview_valid_quiz(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.post("/content/preview", json={
        "body": "# Quiz\n\n---QUIZ_FLASHCARD---\n### Soal 1\n- [] Opsi A\n- [x] Opsi B\n- [] Opsi C\n---END_QUIZ_FLASHCARD---\n",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["quiz_data"]) == 1
    assert data["quiz_data"][0]["type"] == "mcq"


def test_preview_invalid_quiz_two_correct(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.post("/content/preview", json={
        "body": "# Quiz\n\n---QUIZ_FLASHCARD---\n### Soal 1\n- [x] Opsi A\n- [x] Opsi B\n- [] Opsi C\n---END_QUIZ_FLASHCARD---\n",
    })
    assert resp.status_code == 422
    data = resp.get_json()
    assert data["success"] is False
    assert "tepat satu" in data["message"]


def test_preview_arduino_velxio_tabs(client):
    _seed_and_setup()
    _login_teacher(client)
    body = (
        "# LED Arduino\n\n"
        "Materi pengenalan LED.\n\n"
        "---INITIAL_CODE_ARDUINO---\n"
        "void setup() { pinMode(13, OUTPUT); }\n"
        "void loop() { digitalWrite(13, HIGH); }\n"
        "---END_INITIAL_CODE_ARDUINO---\n\n"
        "---VELXIO_CIRCUIT---\n"
        '{"board": "arduino:avr:uno"}\n'
        "---END_VELXIO_CIRCUIT---\n"
    )
    resp = client.post("/content/preview", json={"body": body})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["active_tabs"] == ["velxio"]
    assert "LED Arduino" in data["lesson_content"]


# ── Publish ───────────────────────────────────────────────────────

def test_publish_arduino_velxio_lesson(client):
    _seed_and_setup()
    _login_teacher(client)
    target_path = "test_editor/arduino_lesson.md"
    (TEST_CONTENT / target_path).write_text("# Old", encoding="utf-8")

    body = (
        "# Belajar Arduino Uno\n\n"
        "---INITIAL_CODE_ARDUINO---\n"
        "void setup() {}\n"
        "---END_INITIAL_CODE_ARDUINO---\n\n"
        "---VELXIO_CIRCUIT---\n"
        '{"board": "arduino:avr:uno", "components": []}\n'
        "---END_VELXIO_CIRCUIT---\n"
    )

    resp = client.post("/content/drafts", json={
        "target_path": target_path,
        "body": body,
        "base_mtime": os.path.getmtime(str(TEST_CONTENT / target_path)),
    })
    draft_id = resp.get_json()["draft_id"]

    resp = client.post(f"/content/drafts/{draft_id}/publish")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # Verify published file on disk
    saved = (TEST_CONTENT / target_path).read_text(encoding="utf-8")
    assert "---INITIAL_CODE_ARDUINO---" in saved
    assert "---VELXIO_CIRCUIT---" in saved
    assert "arduino:avr:uno" in saved

def test_publish_success(client):
    _seed_and_setup()
    _login_teacher(client)

    # Save draft
    resp = client.post("/content/drafts", json={
        "target_path": "test_editor/hello.md",
        "body": "# Published Content\n\nBaru.",
        "base_mtime": os.path.getmtime(str(TEST_CONTENT / "test_editor/hello.md")),
    })
    draft_id = resp.get_json()["draft_id"]

    # Publish
    resp = client.post(f"/content/drafts/{draft_id}/publish")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["published_path"] == "test_editor/hello.md"

    # Verify file on disk
    content = (TEST_CONTENT / "test_editor/hello.md").read_text(encoding="utf-8")
    assert "Published Content" in content


def test_publish_stale_mtime_conflict(client):
    _seed_and_setup()
    _login_teacher(client)

    # Save draft with old mtime
    resp = client.post("/content/drafts", json={
        "target_path": "test_editor/hello.md",
        "body": "# New Content",
        "base_mtime": 1.0,  # very old
    })
    draft_id = resp.get_json()["draft_id"]

    # Publish — should conflict
    resp = client.post(f"/content/drafts/{draft_id}/publish")
    assert resp.status_code == 409
    data = resp.get_json()
    assert "conflict" in data["message"]


def test_publish_invalid_quiz_rejected(client):
    _seed_and_setup()
    _login_teacher(client)

    resp = client.post("/content/drafts", json={
        "target_path": "test_editor/quiz.md",
        "body": "# Quiz\n\n---QUIZ_FLASHCARD---\n### Soal 1\n- [x] A\n- [x] B\n---END_QUIZ_FLASHCARD---\n",
        "base_mtime": os.path.getmtime(str(TEST_CONTENT / "test_editor/quiz.md")),
    })
    draft_id = resp.get_json()["draft_id"]

    resp = client.post(f"/content/drafts/{draft_id}/publish")
    assert resp.status_code == 422
    assert "tepat satu" in resp.get_json()["message"]


def test_publish_home_without_marker_rejected(client):
    _seed_and_setup()
    _login_teacher(client)

    # gunakan home.md asli yang sudah di-seed oleh _seed_and_setup
    home = TEST_CONTENT / "home.md"
    assert home.exists(), "home.md harus ada dari _seed_and_setup"

    resp = client.post("/content/drafts", json={
        "target_path": "home.md",
        "body": "# Home\n\nNo marker here.\n",
        "base_mtime": os.path.getmtime(str(home)),
    })
    draft_id = resp.get_json()["draft_id"]

    resp = client.post(f"/content/drafts/{draft_id}/publish")
    assert resp.status_code == 422
    assert "---Available_Lessons---" in resp.get_json()["message"]


def test_publish_sub_home_without_marker_rejected(client):
    """P1-1: guard sub-home.md di publish flow."""
    _seed_and_setup()
    _login_teacher(client)

    # Buat folder + sub-home.md dengan marker valid
    sub_dir = TEST_CONTENT / "folder_x"
    sub_dir.mkdir(parents=True, exist_ok=True)
    sub_home = sub_dir / "sub-home.md"
    sub_home.write_text(
        "# Sub Home\n\n---Available_Lessons---\n\n[Hello](lesson/test_editor/hello.md)\n",
        encoding="utf-8",
    )

    resp = client.post("/content/drafts", json={
        "target_path": "folder_x/sub-home.md",
        "body": "# Sub Home\n\nNo marker here.\n",
        "base_mtime": os.path.getmtime(str(sub_home)),
    })
    draft_id = resp.get_json()["draft_id"]

    resp = client.post(f"/content/drafts/{draft_id}/publish")
    assert resp.status_code == 422
    assert "---Available_Lessons---" in resp.get_json()["message"]


# ── Tree ──────────────────────────────────────────────────────────

def test_get_tree_content(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.get("/content/tree?root=content")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["tree"], list)


def test_tree_create_folder(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.post("/content/tree/folder", json={
        "root": "content",
        "path": "test_editor/new_folder",
    })
    assert resp.status_code == 200
    assert (TEST_CONTENT / "test_editor/new_folder").is_dir()


def test_tree_create_file(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.post("/content/tree/file", json={
        "root": "content",
        "path": "test_editor/new_file.md",
    })
    assert resp.status_code == 200
    assert (TEST_CONTENT / "test_editor/new_file.md").is_file()


def test_tree_file_rejects_assets_root(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.post("/content/tree/file", json={
        "root": "assets",
        "path": "test.png",
    })
    assert resp.status_code == 400


def test_tree_path_traversal_rejected(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.post("/content/tree/folder", json={
        "root": "content",
        "path": "../../etc/passwd",
    })
    assert resp.status_code == 400


def test_tree_rename(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.patch("/content/tree/rename", json={
        "root": "content",
        "old_path": "test_editor/hello.md",
        "new_path": "test_editor/renamed.md",
    })
    assert resp.status_code == 200
    assert (TEST_CONTENT / "test_editor/renamed.md").is_file()
    assert not (TEST_CONTENT / "test_editor/hello.md").exists()


def test_tree_delete_file(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.delete("/content/tree/entry?root=content&path=test_editor/hello.md")
    assert resp.status_code == 200
    assert not (TEST_CONTENT / "test_editor/hello.md").exists()


def test_tree_delete_nonempty_folder_without_force(client):
    _seed_and_setup()
    _login_teacher(client)
    # test_editor has files in it
    resp = client.delete("/content/tree/entry?root=content&path=test_editor")
    assert resp.status_code == 409
    data = resp.get_json()
    assert data.get("needs_force") is True


# ── P0-1: Proteksi file navigasi kritis (home.md, sub-home.md) ──

def test_tree_delete_home_protected(client):
    _seed_and_setup()
    _login_teacher(client)
    # tanpa confirm_critical → 409
    resp = client.delete("/content/tree/entry?root=content&path=home.md")
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["message"] == "protected"
    # file masih ada
    assert (TEST_CONTENT / "home.md").exists()


def test_tree_delete_home_with_confirm(client):
    _seed_and_setup()
    _login_teacher(client)
    # dengan confirm_critical=true → 200, file terhapus
    resp = client.delete("/content/tree/entry?root=content&path=home.md&confirm_critical=true")
    assert resp.status_code == 200
    assert not (TEST_CONTENT / "home.md").exists()


def test_tree_delete_sub_home_protected(client):
    _seed_and_setup()
    _login_teacher(client)
    # buat folder_x/sub-home.md
    sub_dir = TEST_CONTENT / "folder_x"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "sub-home.md").write_text("# Sub\n\n---Available_Lessons---\n\n", encoding="utf-8")
    # tanpa confirm_critical → 409
    resp = client.delete("/content/tree/entry?root=content&path=folder_x/sub-home.md")
    assert resp.status_code == 409
    assert resp.get_json()["message"] == "protected"
    # file masih ada
    assert (sub_dir / "sub-home.md").exists()


def test_tree_delete_sub_home_with_confirm(client):
    _seed_and_setup()
    _login_teacher(client)
    sub_dir = TEST_CONTENT / "folder_x"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "sub-home.md").write_text("# Sub\n\n---Available_Lessons---\n\n", encoding="utf-8")
    resp = client.delete("/content/tree/entry?root=content&path=folder_x/sub-home.md&confirm_critical=true")
    assert resp.status_code == 200
    assert not (sub_dir / "sub-home.md").exists()


def test_tree_delete_normal_file_not_protected(client):
    _seed_and_setup()
    _login_teacher(client)
    # file biasa tidak perlu confirm_critical → 200
    resp = client.delete("/content/tree/entry?root=content&path=test_editor/hello.md")
    assert resp.status_code == 200
    assert not (TEST_CONTENT / "test_editor/hello.md").exists()


def test_tree_rename_home_protected(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.patch("/content/tree/rename", json={
        "root": "content",
        "old_path": "home.md",
        "new_path": "home_renamed.md",
    })
    assert resp.status_code == 409
    assert resp.get_json()["message"] == "protected"
    assert (TEST_CONTENT / "home.md").exists()
    assert not (TEST_CONTENT / "home_renamed.md").exists()


def test_tree_rename_home_with_confirm(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.patch("/content/tree/rename", json={
        "root": "content",
        "old_path": "home.md",
        "new_path": "home_renamed.md",
        "confirm_critical": True,
    })
    assert resp.status_code == 200
    assert not (TEST_CONTENT / "home.md").exists()
    assert (TEST_CONTENT / "home_renamed.md").exists()


def test_tree_rename_normal_file_not_protected(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.patch("/content/tree/rename", json={
        "root": "content",
        "old_path": "test_editor/hello.md",
        "new_path": "test_editor/renamed.md",
    })
    assert resp.status_code == 200
    assert (TEST_CONTENT / "test_editor/renamed.md").is_file()


# ── P1-2: Enforce .md extension di rename untuk root content ──

def test_tree_rename_reject_non_md_extension(client):
    _seed_and_setup()
    _login_teacher(client)
    resp = client.patch("/content/tree/rename", json={
        "root": "content",
        "old_path": "test_editor/hello.md",
        "new_path": "test_editor/hello.txt",
    })
    assert resp.status_code == 400
    assert "Materi hanya boleh berekstensi .md" in resp.get_json()["message"]
    assert (TEST_CONTENT / "test_editor/hello.md").exists()
    assert not (TEST_CONTENT / "test_editor/hello.txt").exists()


def test_tree_rename_assets_root_allows_any_extension(client):
    _seed_and_setup()
    _login_teacher(client)
    # Assets root tidak dibatasi ekstensi
    asset_file = TEST_ASSETS / "test_image.png"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_bytes(b"fake-png")
    resp = client.patch("/content/tree/rename", json={
        "root": "assets",
        "old_path": "test_image.png",
        "new_path": "test_image.bin",
    })
    assert resp.status_code == 200
    assert (TEST_ASSETS / "test_image.bin").exists()


# ── Draft delete ──────────────────────────────────────────────────

def test_discard_draft(client):
    _seed_and_setup()
    _login_teacher(client)

    # Save draft
    resp = client.post("/content/drafts", json={
        "target_path": "test_editor/hello.md",
        "body": "# To be discarded",
    })
    draft_id = resp.get_json()["draft_id"]

    # Delete it
    resp = client.delete(f"/content/drafts/{draft_id}")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # Should now read from file again
    resp = client.get("/content/drafts?target_path=test_editor/hello.md")
    data = resp.get_json()
    assert data["source"] == "file"


# ── Regression: _render_markdown_string == render_markdown_content ─

def test_render_markdown_string_matches_file_render(client):
    """_render_markdown_string() and render_markdown_content() produce identical dict
    for the same file content (regression for CONTENT-02 refactor)."""
    from services.lesson_service import _render_markdown_string, render_markdown_content

    test_file = TEST_CONTENT / "test_editor" / "hello.md"
    if not test_file.exists():
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# Hello\n\nTest content.\n", encoding="utf-8")

    file_result = render_markdown_content(str(test_file))
    content = test_file.read_text(encoding="utf-8")
    string_result = _render_markdown_string(content)

    # Compare all keys
    assert set(file_result.keys()) == set(string_result.keys())
    for key in file_result:
        assert file_result[key] == string_result[key], f"Mismatch at key '{key}'"


# ── Author ID verification ────────────────────────────────────────

def test_save_draft_stores_correct_author_id(client):
    _seed_and_setup()
    _login_teacher(client)

    resp = client.post("/content/drafts", json={
        "target_path": "test_editor/hello.md",
        "body": "# Test",
    })
    draft_id = resp.get_json()["draft_id"]

    # Query DB directly to verify author_id
    db = SessionLocal()
    try:
        from services.models import ContentDraft
        draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
        assert draft is not None
        teacher = db.query(repo.User).filter(repo.User.role == "teacher").first()
        assert draft.author_id == teacher.id
    finally:
        db.close()


# ── Export bundle ──────────────────────────────────────────────────

def test_export_requires_teacher(client):
    _seed_and_setup()
    resp = client.get("/content/export")
    assert resp.status_code == 401


def test_export_returns_zip_with_content_and_assets(client):
    _seed_and_setup()
    _login_teacher(client)
    (TEST_ASSETS / "diag.png").write_bytes(b"fake-png")
    resp = client.get("/content/export")
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["Content-Type"]
    assert resp.headers["Content-Disposition"].startswith("attachment; filename=")
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    names = set(zf.namelist())
    assert "content/test_editor/hello.md" in names
    assert "content/home.md" in names
    assert "assets/diag.png" in names


def test_export_scope_content_excludes_assets(client):
    _seed_and_setup()
    _login_teacher(client)
    (TEST_ASSETS / "diag.png").write_bytes(b"fake-png")
    resp = client.get("/content/export?scope=content")
    assert resp.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(resp.data)).namelist()
    assert any(n.startswith("content/") for n in names)
    assert not any(n.startswith("assets/") for n in names)
# ── Boundary 5 MiB (cabang len(raw) — bukan pre-check len(b64)) ──────
# SVG dipakai karena dikecualikan dari validasi gambar PIL (Pillow tidak
# parse SVG), sehingga ukuran murni yang diuji, bukan validasi isi.
# Blok ini self-contained (helper sendiri) agar tidak bergantung helper
# lain di file ini.

import base64 as _b64_mod  # noqa: E402  (import lokal — blok ini standalone)

_SVG_HDR = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'


def _svg_of(raw_size: int) -> bytes:
    return _SVG_HDR + b" " * (raw_size - len(_SVG_HDR))


def _post_upload_plain(client, filename, raw):
    """POST upload tanpa flag overwrite (blok ini standalone — tidak
    memakai helper _upload di atas agar commit-nya bisa berdiri sendiri)."""
    return client.post("/content/assets/upload", json={
        "filename": filename,
        "folder": "",
        "content_base64": _b64_mod.b64encode(raw).decode(),
    })


def test_upload_exactly_5mib_accepted(client):
    """File TEPAT _MAX_ASSET_BYTES (5 MiB) harus lolos — bukan ditolak."""
    _seed_and_setup()
    _login_teacher(client)
    resp = _post_upload_plain(client, "exact5mib.svg", _svg_of(5 * 1024 * 1024))
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["success"] is True


def test_upload_5mib_plus_1_rejected(client):
    """5 MiB + 1 byte harus ditolak cabang len(raw) dengan pesan ukuran."""
    _seed_and_setup()
    _login_teacher(client)
    resp = _post_upload_plain(client, "over5mib.svg", _svg_of(5 * 1024 * 1024 + 1))
    assert resp.status_code == 400
    assert "mib" in resp.get_json()["message"].lower()


# ── CSP saat serve SVG (mitigasi stored-XSS via SVG ber-script) ──────


def test_serve_svg_has_restrictive_csp(client):
    """SVG diserve dengan CSP ketat — <script> di dalamnya tak bisa jalan
    saat SVG dibuka langsung di tab browser (same-origin)."""
    (TEST_ASSETS / "malware.svg").write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>fetch("/api/login")</script></svg>'
    )
    resp = client.get("/assets/malware.svg")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Security-Policy") == "default-src 'none'; sandbox"


def test_serve_raster_image_no_csp(client):
    """Gambar raster (PNG) tidak diberi CSP — hanya SVG yang berisiko."""
    (TEST_ASSETS / "normal.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    resp = client.get("/assets/normal.png")
    assert resp.status_code == 200
    assert "Content-Security-Policy" not in resp.headers

