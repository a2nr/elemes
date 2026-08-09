"""
Route test student management (teacher-only) — butuh PostgreSQL.

Mengunci kontrak:
- autentikasi guru HANYA dari cookie HttpOnly `student_token`;
- export selection / export-all / DB kosong (header-only);
- import preview tanpa write, apply all-or-nothing, conflict 409;
- bulk delete atomic dengan perlindungan teacher;
- token plaintext & hash TIDAK pernah muncul di response.
"""

import io
import os
import uuid as uuid_lib
from pathlib import Path

import pytest

from services import repositories as repo
from services.database import SessionLocal
from services.tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

DB_REQUIRED = os.environ.get("DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")

FIXTURES = Path(__file__).parent / "fixtures"

HEADER = "student_id;token;nama_siswa;hello_world;variabel"
HEADER_COMMA = "student_id,token,nama_siswa,hello_world,variabel"


def _seed(db, with_students=True):
    repo.upsert_lesson(db, slug="hello_world", title="Hello World", order_index=0)
    repo.upsert_lesson(db, slug="variabel", title="Variabel", order_index=1)
    teacher = repo.create_user(db, display_name="Pak Guru", role="teacher")
    repo.create_access_token(db, user_id=teacher.id, raw_token=TEACHER_TOKEN)
    students = []
    if with_students:
        for name, token in (("Budi Santoso", STUDENT_TOKEN), ("Siti Aminah", "TOKEN_SISWA_002")):
            user = repo.create_user(db, display_name=name, role="student")
            repo.create_access_token(db, user_id=user.id, raw_token=token)
            students.append(user)
    db.commit()
    return {"teacher": teacher, "students": students}


def _seed_teacher_and_students():
    db = SessionLocal()
    try:
        return _seed(db)
    finally:
        db.close()


def _login_teacher(client):
    client.set_cookie("student_token", TEACHER_TOKEN)


def _login_student(client):
    client.set_cookie("student_token", STUDENT_TOKEN)


def _valid_csv(rows=None, header=HEADER):
    rows = rows or [";TOKEN_12345678;Siswa Baru;completed;3/4"]
    return (header + "\n" + "\n".join(rows)).encode("utf-8")


def _upload(client, url, content, filename="data_siswa.csv"):
    return client.post(
        url,
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def _counts():
    db = SessionLocal()
    try:
        from sqlalchemy import func, select

        from services.models import AccessToken, StudentProgress, User

        return {
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "tokens": db.scalar(select(func.count()).select_from(AccessToken)) or 0,
            "progress": db.scalar(select(func.count()).select_from(StudentProgress)) or 0,
        }
    finally:
        db.close()


# ── auth ───────────────────────────────────────────────────────────


def test_export_requires_teacher_cookie(client):
    resp = client.post("/students/export-csv", json={"student_ids": []})
    assert resp.status_code == 401


def test_export_rejects_student_cookie(client):
    _seed_teacher_and_students()
    _login_student(client)
    resp = client.post("/students/export-csv", json={"student_ids": []})
    assert resp.status_code == 401


def test_export_rejects_token_in_query_or_body(client):
    _seed_teacher_and_students()
    # token di body, tanpa cookie → tetap ditolak
    resp = client.post("/students/export-csv", json={"student_ids": [], "token": TEACHER_TOKEN})
    assert resp.status_code == 401


def test_origin_mismatch_rejected(client, monkeypatch):
    _seed_teacher_and_students()
    _login_teacher(client)
    monkeypatch.setenv("ORIGIN", "http://lms.example.com")
    resp = client.post(
        "/students/export-csv",
        json={"student_ids": []},
        headers={"Origin": "http://evil.example.com"},
    )
    assert resp.status_code == 403
    # origin yang benar → lolos
    resp = client.post(
        "/students/export-csv",
        json={"student_ids": []},
        headers={"Origin": "http://lms.example.com"},
    )
    assert resp.status_code == 200


# ── export ─────────────────────────────────────────────────────────


def test_export_selection(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1 = seeded["students"][0]

    resp = client.post("/students/export-csv", json={"student_ids": [s1.id]})
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type
    assert "data_siswa_" in resp.headers["Content-Disposition"]
    assert ".csv" in resp.headers["Content-Disposition"]

    text = resp.data.decode("utf-8-sig")
    assert text.startswith("\ufeff") or resp.data.startswith(b"\xef\xbb\xbf")
    lines = text.strip().splitlines()
    assert lines[0].startswith("student_id;token;nama_siswa;")
    assert len(lines) == 2  # hanya siswa terpilih
    cols = lines[1].split(";")
    assert cols[0] == s1.id
    assert cols[1] == ""  # token selalu kosong
    assert "Pak Guru" not in text  # teacher tidak pernah diekspor
    assert "completed_count" not in text
    assert "token_hash" not in text


def test_export_no_selection_exports_all(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    ids = {s.id for s in seeded["students"]}

    resp = client.post("/students/export-csv", json={"student_ids": []})
    assert resp.status_code == 200
    lines = resp.data.decode("utf-8-sig").strip().splitlines()
    assert len(lines) == 3  # header + 2 siswa
    exported = {l.split(";")[0] for l in lines[1:]}
    assert exported == ids


def test_export_invalid_selection_rejected(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1 = seeded["students"][0]
    teacher = seeded["teacher"]

    for bad in (
        [str(uuid_lib.uuid4())],  # unknown
        [teacher.id],  # teacher ID
        [s1.id, s1.id],  # duplikat
        ["bukan-uuid"],  # malformed
    ):
        resp = client.post("/students/export-csv", json={"student_ids": bad})
        assert resp.status_code == 400


def test_export_empty_db_header_only(client):
    _seed_teacher_and_students()
    _login_teacher(client)
    # kosongkan DB: semua siswa dihapus (teacher tetap login; lesson tetap)
    db = SessionLocal()
    try:
        from sqlalchemy import delete

        from services.models import User

        db.execute(delete(User).where(User.role == "student"))
        db.commit()
    finally:
        db.close()

    resp = client.post("/students/export-csv", json={"student_ids": []})
    assert resp.status_code == 200
    text = resp.data.decode("utf-8-sig")
    assert text.strip().splitlines()[0].startswith("student_id;token;nama_siswa;")


# ── import ─────────────────────────────────────────────────────────


def test_import_requires_file(client):
    _seed_teacher_and_students()
    _login_teacher(client)
    resp = client.post("/students/import", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_import_wrong_extension_rejected(client):
    _seed_teacher_and_students()
    _login_teacher(client)
    resp = _upload(client, "/students/import", _valid_csv(), filename="data.txt")
    assert resp.status_code == 400


def test_import_file_too_big_rejected(client):
    _seed_teacher_and_students()
    _login_teacher(client)
    big = b"a" * (5 * 1024 * 1024 + 1)
    resp = _upload(client, "/students/import", big)
    assert resp.status_code == 400


def test_import_malformed_rejected(client):
    _seed_teacher_and_students()
    _login_teacher(client)
    resp = _upload(client, "/students/import", b"student_id;token;nama_siswa\n;;Nama\n")
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_preview_no_write_and_masked(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    before = _counts()

    resp = _upload(client, "/students/import/preview", _valid_csv())
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["summary"]["rows"] == 1
    assert data["summary"]["students_to_create"] == 1
    assert data["summary"]["students_to_update"] == 0
    assert data["summary"]["progress_to_restore"] == 0
    assert data["summary"]["conflicts"] == []
    assert data["rows"][0]["nama_siswa"] == "Siswa Baru"

    # preview tidak menulis apa pun
    assert _counts() == before
    assert seeded["students"]


def test_import_apply_success_and_digest_only(client):
    _seed_teacher_and_students()
    _login_teacher(client)

    resp = _upload(client, "/students/import", _valid_csv())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["students_created"] == 1
    assert body["progress_created"] == 2

    # token valid & progress terbentuk; hanya digest tersimpan
    from services.token_hashing import hash_token

    db = SessionLocal()
    try:
        from sqlalchemy import func, select

        from services.models import AccessToken, StudentProgress

        user = repo.find_user_by_raw_token(db, "TOKEN_12345678")
        assert user is not None and user.role == "student"
        digest = hash_token("TOKEN_12345678")
        assert (
            db.scalar(
                select(func.count()).select_from(AccessToken).where(AccessToken.token_hash == digest)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count()).select_from(AccessToken).where(
                    AccessToken.token_hash == "TOKEN_12345678"
                )
            )
            == 0
        )
        assert db.scalar(select(func.count()).select_from(StudentProgress)) == 2
    finally:
        db.close()

    # response tidak memuat token plaintext maupun hash
    raw = resp.get_data(as_text=True)
    assert "TOKEN_12345678" not in raw
    assert hash_token("TOKEN_12345678") not in raw


def test_import_conflict_existing_id_and_token_409(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1 = seeded["students"][0]
    before = _counts()

    # student_id existing
    rows = [f"{s1.id};TOKEN_99999999;Hacker;completed"]
    resp = _upload(client, "/students/import", _valid_csv(rows))
    assert resp.status_code == 409
    assert resp.get_json()["success"] is False

    # token existing (digest sama), UUID baru
    rows = [";TOKEN_SISWA_002;Peniru;completed"]
    resp = _upload(client, "/students/import", _valid_csv(rows))
    assert resp.status_code == 409

    # campuran baru + existing → zero write
    rows = [";TOKEN_11111111;Siswa Baru 1;completed", f"{s1.id};TOKEN_22222222;Siswa Baru 2;completed"]
    resp = _upload(client, "/students/import", _valid_csv(rows))
    assert resp.status_code == 409
    assert _counts() == before  # tidak ada yang dibuat


def test_import_same_file_twice_fails_second(client):
    _seed_teacher_and_students()
    _login_teacher(client)

    first = _upload(client, "/students/import", _valid_csv())
    assert first.status_code == 200

    second = _upload(client, "/students/import", _valid_csv())
    assert second.status_code == 409


def test_import_empty_uuid_creates_server_side_uuid(client):
    _seed_teacher_and_students()
    _login_teacher(client)

    resp = _upload(client, "/students/import", _valid_csv([";TOKEN_12345678;Siswa Baru;completed"]))
    assert resp.status_code == 200

    db = SessionLocal()
    try:
        user = repo.find_user_by_raw_token(db, "TOKEN_12345678")
        assert user is not None
        import uuid as uuid_lib

        assert str(uuid_lib.UUID(user.id)) == user.id  # canonical UUID server-side
    finally:
        db.close()


# ── import: round-trip export → restore (token kosong) ─────────────


def test_import_export_roundtrip_with_empty_token(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1, s2 = seeded["students"]

    # progress seed untuk s1 agar export membawa data non-empty
    db = SessionLocal()
    try:
        lessons = {l.slug: l for l in repo.list_active_lessons(db)}
        repo.set_progress(db, user_id=s1.id, lesson_id=lessons["hello_world"].id, state="completed")
        db.commit()
    finally:
        db.close()

    # 1) export hasil → token selalu kosong
    resp = client.post("/students/export-csv", json={"student_ids": [s1.id, s2.id]})
    assert resp.status_code == 200
    csv_bytes = resp.data

    # 2) upload hasil export (token kosong) → preview sukses, dilaporkan sebagai
    #    update/restore, BUKAN create
    prev = _upload(client, "/students/import/preview", csv_bytes)
    assert prev.status_code == 200
    summary = prev.get_json()["summary"]
    assert summary["rows"] == 2
    assert summary["students_to_update"] == 2
    assert summary["students_to_create"] == 0
    assert summary["progress_to_restore"] == 1
    assert summary["conflicts"] == []

    # 3) apply hasil export sukses tanpa menambah user/access-token/progress
    before = _counts()
    apply = _upload(client, "/students/import", csv_bytes)
    assert apply.status_code == 200
    body = apply.get_json()
    assert body["success"] is True
    assert body["students_created"] == 0
    assert body["students_updated"] == 2
    assert body["progress_restored"] == 1
    assert _counts() == before

    # 4) token existing tetap valid setelah apply
    db = SessionLocal()
    try:
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN) is not None
        assert repo.find_user_by_raw_token(db, "TOKEN_SISWA_002") is not None
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN).id == s1.id
    finally:
        db.close()

    # response tidak memuat token
    raw = apply.get_data(as_text=True)
    assert STUDENT_TOKEN not in raw
    assert "TOKEN_SISWA_002" not in raw


def test_import_unknown_student_id_with_empty_token_rejected(client):
    _seed_teacher_and_students()
    _login_teacher(client)
    before = _counts()

    unknown = str(uuid_lib.uuid4())
    rows = [f"{unknown};;Hacker;completed"]
    resp = _upload(client, "/students/import", _valid_csv(rows))
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["success"] is False
    assert any("tidak dikenal" in e for e in data["errors"])
    assert _counts() == before  # zero write


def test_import_mixed_existing_restore_and_new_student_atomic(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1 = seeded["students"][0]

    rows = [
        f"{s1.id};;Siswa Lama;completed",
        ";TOKEN_12345678;Siswa Baru;completed",
    ]
    resp = _upload(client, "/students/import", _valid_csv(rows))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["students_updated"] == 1
    assert body["students_created"] == 1

    # satu transaksi: restore existing + create siswa baru bersama-sama
    db = SessionLocal()
    try:
        from services.models import User

        assert db.get(User, s1.id) is not None
        assert repo.find_user_by_raw_token(db, "TOKEN_12345678") is not None
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN) is not None
    finally:
        db.close()


def test_import_existing_student_with_new_token_conflict(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1 = seeded["students"][0]
    before = _counts()

    rows = [f"{s1.id};TOKEN_BARU_12345678;Siswa Lama;completed"]
    resp = _upload(client, "/students/import", _valid_csv(rows))
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["success"] is False
    assert any("token baru" in e for e in data["errors"])

    # zero write: token baru tidak pernah dibuat, siswa lama tidak berubah
    db = SessionLocal()
    try:
        assert repo.find_user_by_raw_token(db, "TOKEN_BARU_12345678") is None
    finally:
        db.close()
    assert _counts() == before


# ── bulk delete ────────────────────────────────────────────────────


def test_bulk_delete_success(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    ids = [s.id for s in seeded["students"]]

    resp = client.post("/students/bulk-delete", json={"student_ids": ids})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["deleted_count"] == 2
    assert set(body["deleted_ids"]) == set(ids)

    db = SessionLocal()
    try:
        from services.models import User

        for sid in ids:
            assert db.get(User, sid) is None
        assert db.get(User, seeded["teacher"].id) is not None  # teacher aman
    finally:
        db.close()


def test_bulk_delete_invalid_zero_delete(client):
    seeded = _seed_teacher_and_students()
    _login_teacher(client)
    s1 = seeded["students"][0]
    teacher = seeded["teacher"]

    for bad in (
        [],
        ["bukan-uuid"],
        [str(uuid_lib.uuid4())],
        [teacher.id],
        [s1.id, s1.id],
        [s1.id] * 1001,
    ):
        resp = client.post("/students/bulk-delete", json={"student_ids": bad})
        assert resp.status_code == 400, bad

    db = SessionLocal()
    try:
        from services.models import User

        assert db.get(User, s1.id) is not None  # tetap ada
        assert db.get(User, teacher.id) is not None
    finally:
        db.close()


def test_bulk_delete_requires_auth(client):
    resp = client.post("/students/bulk-delete", json={"student_ids": []})
    assert resp.status_code == 401


# ── import: delimiter koma (`,`) — kompatibilitas spreadsheet ──────


def _valid_comma_csv(rows=None):
    rows = rows or [",LocustBot48,Locust Bot 48,completed,"]
    return (HEADER_COMMA + "\n" + "\n".join(rows)).encode("utf-8")


def test_preview_comma_delimiter_csv_success(client):
    _seed_teacher_and_students()
    _login_teacher(client)

    resp = _upload(client, "/students/import/preview", _valid_comma_csv())
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["summary"]["rows"] == 1
    assert data["summary"]["students_to_create"] == 1
    assert data["summary"]["students_to_update"] == 0
    assert data["summary"]["conflicts"] == []
    assert data["rows"][0]["nama_siswa"] == "Locust Bot 48"

    # raw token tidak pernah muncul di preview
    raw = resp.get_data(as_text=True)
    assert "LocustBot48" not in raw


def test_import_comma_delimiter_csv_apply_success(client):
    _seed_teacher_and_students()
    _login_teacher(client)

    resp = _upload(client, "/students/import", _valid_comma_csv())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["students_created"] == 1

    # user ditemukan lewat raw token; hanya digest tersimpan
    db = SessionLocal()
    try:
        from sqlalchemy import select

        from services.models import AccessToken, Lesson, StudentProgress, User
        from services.token_hashing import hash_token

        user = repo.find_user_by_raw_token(db, "LocustBot48")
        assert user is not None and user.role == "student"
        assert user.display_name == "Locust Bot 48"

        digest = hash_token("LocustBot48")
        token_row = db.scalar(
            select(AccessToken).where(AccessToken.token_hash == digest)
        )
        assert token_row is not None
        assert token_row.token_hash != "LocustBot48"  # bukan plaintext

        lesson = db.scalar(select(Lesson).where(Lesson.slug == "hello_world"))
        assert lesson is not None
        progress = db.scalar(
            select(StudentProgress).where(
                StudentProgress.user_id == user.id,
                StudentProgress.lesson_id == lesson.id,
            )
        )
        assert progress is not None and progress.state == "completed"
    finally:
        db.close()

    # response tidak memuat raw token maupun hash
    from services.token_hashing import hash_token

    raw = resp.get_data(as_text=True)
    assert "LocustBot48" not in raw
    assert hash_token("LocustBot48") not in raw
