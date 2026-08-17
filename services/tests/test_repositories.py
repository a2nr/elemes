"""
Integration test repository round-trip siswa (butuh PostgreSQL — skip bila
DATABASE_URL tidak diset). Mengunci:

- export: student-only, deterministic, token kosong, tanpa metadata internal;
- import: create (siswa baru) + restore/update (siswa existing), all-or-nothing,
  digest-only, sparse progress, race-safe;
- bulk delete: atomic, cascade, teacher terlindungi, UUID/token dapat dipakai
  ulang untuk re-create.
"""

import os
import uuid as uuid_lib
from pathlib import Path

import pytest
from sqlalchemy import func, select

from services import repositories as repo
from services.database import SessionLocal
from services.models import AccessToken, StudentProgress, User
from services.progress_status import ParsedProgress
from services.student_roundtrip import (
    RoundTripImportError,
    StudentRoundTripRow,
    parse_roundtrip_csv,
)
from services.token_hashing import hash_token
from services.tests.conftest import STUDENT2_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN

DB_REQUIRED = os.environ.get("DATABASE_URL", "").strip()

pytestmark = [
    pytest.mark.skipif(
        not DB_REQUIRED,
        reason="butuh DATABASE_URL (PostgreSQL nyata)",
    ),
    pytest.mark.integration,
]

FIXTURES = Path(__file__).parent / "fixtures"
UUID_1 = "7eab651c-5eb1-4eb8-8fd2-17fd77aec6df"


# ── helper ─────────────────────────────────────────────────────────


def _seed_lesson(db, slug="hello_world", order=0):
    return repo.upsert_lesson(
        db, slug=slug, title=slug.replace("_", " ").title(), order_index=order
    )


def _seed_student(db, token, name="Budi Santoso", role="student"):
    user = repo.create_user(db, display_name=name, role=role)
    repo.create_access_token(db, user_id=user.id, raw_token=token)
    return user


def _make_row(
    student_id,
    token,
    name,
    progress=None,
    line=2,
):
    return StudentRoundTripRow(
        line=line,
        student_id=student_id,
        raw_token=token,
        display_name=name,
        progress=progress or {},
    )


def _counts(db):
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "tokens": db.scalar(select(func.count()).select_from(AccessToken)) or 0,
        "progress": db.scalar(select(func.count()).select_from(StudentProgress)) or 0,
    }


# ── export: list_students_for_export ───────────────────────────────


def test_list_students_for_export_student_only():
    db = SessionLocal()
    try:
        _seed_student(db, TEACHER_TOKEN, "Pak Guru", role="teacher")
        s1 = _seed_student(db, STUDENT_TOKEN, "Budi Santoso")
        s2 = _seed_student(db, STUDENT2_TOKEN, "Siti Aminah")

        users = repo.list_students_for_export(db)
        assert {u.id for u in users} == {s1.id, s2.id}  # teacher tidak ikut
    finally:
        db.close()


def test_export_selection_rejects_invalid_ids():
    db = SessionLocal()
    try:
        s = _seed_student(db, STUDENT_TOKEN, "Budi")
        teacher = _seed_student(db, TEACHER_TOKEN, "Pak Guru", role="teacher")

        with pytest.raises(ValueError):
            repo.list_students_for_export(db, [str(uuid_lib.uuid4())])  # unknown
        with pytest.raises(ValueError):
            repo.list_students_for_export(db, [teacher.id])  # teacher ID
        with pytest.raises(ValueError):
            repo.list_students_for_export(db, [s.id, s.id])  # duplikat
        with pytest.raises(ValueError):
            repo.list_students_for_export(db, ["bukan-uuid"])  # malformed
        with pytest.raises(ValueError):
            repo.list_students_for_export(db, [s.id] * 1001)  # melebihi 1000
    finally:
        db.close()


def test_export_selection_subset_and_order():
    db = SessionLocal()
    try:
        _seed_lesson(db, "hello_world", 0)
        s1 = _seed_student(db, STUDENT_TOKEN, "Budi")
        s2 = _seed_student(db, STUDENT2_TOKEN, "Siti")
        selected = repo.list_students_for_export(db, [s2.id])
        assert [u.id for u in selected] == [s2.id]

        all_users = repo.list_students_for_export(db)
        assert [u.id for u in all_users] == sorted([s1.id, s2.id])  # deterministic by (created_at, id)
    finally:
        db.close()


# ── export: serialize ──────────────────────────────────────────────


def test_export_csv_content_and_no_leak():
    db = SessionLocal()
    try:
        lesson = _seed_lesson(db, "hello_world", 0)
        lesson2 = _seed_lesson(db, "variabel", 1)
        teacher = _seed_student(db, TEACHER_TOKEN, "Pak Guru", role="teacher")
        s1 = _seed_student(db, STUDENT_TOKEN, "Budi Santoso")
        repo.set_progress(db, user_id=s1.id, lesson_id=lesson.id, state="completed")
        repo.set_progress(db, user_id=s1.id, lesson_id=lesson2.id, state="scored", score_earned=3, score_total=4)

        csv_bytes = repo.export_students_csv(db)
        text = csv_bytes.decode("utf-8-sig")
        assert csv_bytes.startswith("\ufeff".encode("utf-8"))
        lines = text.strip().splitlines()
        assert lines[0] == "student_id;token;nama_siswa;hello_world;variabel"
        assert len(lines) == 2  # hanya 1 siswa (teacher tidak ikut)
        cols = lines[1].split(";")
        assert cols[0] == s1.id
        assert cols[1] == ""  # token selalu kosong
        assert cols[2] == "Budi Santoso"
        assert cols[3] == "completed"
        assert cols[4] == "3/4"

        # tanpa metadata internal / hash / teacher / completed_count
        for forbidden in ("completed_count", "token_hash", "digest", teacher.id, TEACHER_TOKEN):
            assert forbidden not in text
    finally:
        db.close()


def test_export_empty_db_header_only():
    db = SessionLocal()
    try:
        csv_bytes = repo.export_students_csv(db)
        text = csv_bytes.decode("utf-8-sig")
        assert text.strip() == "student_id;token;nama_siswa"
    finally:
        db.close()


def test_export_does_not_modify_database():
    db = SessionLocal()
    try:
        _seed_student(db, STUDENT_TOKEN, "Budi")
        before = _counts(db)
        repo.export_students_csv(db)
        assert _counts(db) == before
    finally:
        db.close()


# ── import: create-user & transaksi ────────────────────────────────


def test_create_user_with_explicit_id():
    db = SessionLocal()
    try:
        user = repo.create_user(db, display_name="X", role="student", user_id=UUID_1)
        assert user.id == UUID_1
        assert db.get(User, UUID_1) is not None
    finally:
        db.close()


def test_import_generates_canonical_uuids_for_new_students():
    db = SessionLocal()
    try:
        _seed_lesson(db, "hello_world", 0)
        rows = [
            _make_row(None, "TOKEN_12345678", "Siswa Baru"),
            _make_row(None, "TOKEN_87654321", "Siswa Baru 2"),
        ]
        result = repo.run_student_import(db, rows)
        assert result["students_created"] == 2

        first = repo.find_user_by_raw_token(db, "TOKEN_12345678")
        assert first is not None
        assert str(uuid_lib.UUID(first.id)) == first.id  # canonical UUID server-side
        assert first.role == "student"
    finally:
        db.close()


def test_import_all_users_are_students():
    db = SessionLocal()
    try:
        rows = [_make_row(None, f"TOKEN_AKHIR_{i:04d}", f"Siswa {i}") for i in range(3)]
        repo.run_student_import(db, rows)
        users = db.scalars(select(User)).all()
        assert len(users) == 3
        assert all(u.role == "student" for u in users)
    finally:
        db.close()


def test_import_stores_digest_not_plaintext():
    db = SessionLocal()
    try:
        rows = [_make_row(None, "TOKEN_12345678", "Budi")]
        repo.run_student_import(db, rows)
        digest = hash_token("TOKEN_12345678")
        assert db.scalar(select(AccessToken.id).where(AccessToken.token_hash == digest)) is not None
        assert db.scalar(select(func.count()).select_from(AccessToken).where(AccessToken.token_hash == "TOKEN_12345678")) == 0
    finally:
        db.close()


def test_import_sparse_progress_and_counts():
    db = SessionLocal()
    try:
        hello = _seed_lesson(db, "hello_world", 0)
        var = _seed_lesson(db, "variabel", 1)
        rows = [
            _make_row(
                None,
                "TOKEN_12345678",
                "Budi",
                progress={
                    "hello_world": ParsedProgress("completed"),
                    "variabel": ParsedProgress("scored", 3, 4),
                },
            ),
            _make_row(None, "TOKEN_87654321", "Siti"),  # tanpa progress
        ]
        result = repo.run_student_import(db, rows)
        assert result["progress_created"] == 2

        user = repo.find_user_by_raw_token(db, "TOKEN_12345678")
        assert db.scalar(select(func.count()).select_from(StudentProgress).where(StudentProgress.user_id == user.id)) == 2
        scored = db.scalar(
            select(StudentProgress).where(StudentProgress.user_id == user.id, StudentProgress.lesson_id == var.id)
        )
        assert scored.state == "scored" and scored.score_earned == 3 and scored.score_total == 4
        # sparse: Siti tidak punya row progress sama sekali
        siti = repo.find_user_by_raw_token(db, "TOKEN_87654321")
        assert db.scalar(select(func.count()).select_from(StudentProgress).where(StudentProgress.user_id == siti.id)) == 0
        _ = hello  # dipakai di assertion count di atas
    finally:
        db.close()


# ── import: conflict & all-or-nothing ──────────────────────────────


def test_import_rejects_new_token_for_existing_student():
    db = SessionLocal()
    try:
        existing = _seed_student(db, STUDENT_TOKEN, "Budi")
        rows = [_make_row(existing.id, "TOKEN_99999999", "Budi Baru")]
        with pytest.raises(RoundTripImportError) as exc:
            repo.run_student_import(db, rows)
        assert any("tidak boleh menerima token baru" in e for e in exc.value.errors)
        assert _counts(db)["users"] == 1  # zero write
    finally:
        db.close()


def test_import_fails_if_teacher_id_exists():
    db = SessionLocal()
    try:
        teacher = _seed_student(db, TEACHER_TOKEN, "Pak Guru", role="teacher")
        rows = [_make_row(teacher.id, "TOKEN_99999999", "Hacker")]
        with pytest.raises(RoundTripImportError):
            repo.run_student_import(db, rows)
        assert _counts(db)["users"] == 1
    finally:
        db.close()


def test_import_fails_if_token_exists_including_revoked():
    db = SessionLocal()
    try:
        existing = _seed_student(db, STUDENT_TOKEN, "Budi")
        rows = [_make_row(None, STUDENT_TOKEN, "Peniru")]  # token sama, UUID berbeda
        with pytest.raises(RoundTripImportError) as exc:
            repo.run_student_import(db, rows)
        assert any("token sudah terdaftar" in e for e in exc.value.errors)

        # token revoked pun tetap menabrak (guard terhadap reuse token)
        repo.revoke_token(db, user_id=existing.id, raw_token=STUDENT_TOKEN)
        db.commit()
        with pytest.raises(RoundTripImportError):
            repo.run_student_import(db, rows)
    finally:
        db.close()


def test_import_mixed_new_and_existing_zero_write():
    db = SessionLocal()
    try:
        existing = _seed_student(db, STUDENT_TOKEN, "Budi")
        before = _counts(db)
        rows = [
            _make_row(None, "TOKEN_11111111", "Siswa Baru 1"),
            _make_row(existing.id, "TOKEN_22222222", "Siswa Baru 2"),  # menabrak
        ]
        with pytest.raises(RoundTripImportError):
            repo.run_student_import(db, rows)
        assert _counts(db) == before  # tidak ada satupun yang dibuat
    finally:
        db.close()


def test_import_same_file_twice_fails_second_time():
    db = SessionLocal()
    try:
        _seed_lesson(db, "hello_world", 0)
        rows = [_make_row(None, "TOKEN_12345678", "Budi")]
        first = repo.run_student_import(db, rows)
        assert first["students_created"] == 1
        # upload ulang file yang sama → seluruh import ditolak
        with pytest.raises(RoundTripImportError):
            repo.run_student_import(db, rows)
        assert _counts(db)["users"] == 1
    finally:
        db.close()


def test_import_rollback_on_mid_exception():
    db = SessionLocal()
    try:
        rows = [
            _make_row(None, "TOKEN_12345678", "Budi"),
            _make_row(None, "TOKEN_87654321", "Siti", progress={"tidak_ada_di_db": ParsedProgress("completed")}),
        ]
        with pytest.raises(ValueError):
            repo.run_student_import(db, rows)
        # rollback penuh — user pertama pun tidak tersimpan
        assert _counts(db)["users"] == 0
        assert _counts(db)["tokens"] == 0
    finally:
        db.close()


def test_import_race_preview_apply_conflict():
    db = SessionLocal()
    try:
        rows = [_make_row(None, "TOKEN_12345678", "Budi")]
        # preview sukses (tidak ada conflict)
        assert repo.preview_student_import(db, rows)["conflicts"] == []
        # antara preview & apply, siswa lain dibuat dengan token sama
        other = SessionLocal()
        try:
            repo.run_student_import(other, rows)
        finally:
            other.close()
        # apply harus memvalidasi ulang → gagal, zero write
        with pytest.raises(RoundTripImportError):
            repo.run_student_import(db, rows)
        assert _counts(db)["users"] == 1
    finally:
        db.close()


def test_preview_student_import_summary():
    db = SessionLocal()
    try:
        rows = [
            _make_row(None, "TOKEN_12345678", "Budi", progress={"a": ParsedProgress("completed")}),
            _make_row(None, "TOKEN_87654321", "Siti"),
        ]
        summary = repo.preview_student_import(db, rows)
        assert summary == {
            "rows": 2,
            "students_to_create": 2,
            "students_to_update": 0,
            "progress_to_create": 1,
            "progress_to_restore": 0,
            "conflicts": [],
        }
    finally:
        db.close()


# ── import: restore/update siswa existing (token kosong) ──────────


def test_import_existing_with_empty_token_restores_without_new_token():
    db = SessionLocal()
    try:
        hello = _seed_lesson(db, "hello_world", 0)
        existing = _seed_student(db, STUDENT_TOKEN, "Budi Santoso")
        repo.set_progress(db, user_id=existing.id, lesson_id=hello.id, state="completed")
        db.commit()
        before = _counts(db)

        # hasil export: student_id terisi + token kosong → restore/update
        rows = [
            _make_row(
                existing.id,
                "",
                "Budi Update",
                progress={"hello_world": ParsedProgress("scored", 3, 4)},
            )
        ]
        result = repo.run_student_import(db, rows)
        assert result == {
            "students_created": 0,
            "students_updated": 1,
            "progress_created": 0,
            "progress_restored": 1,
            "user_ids": [existing.id],
        }

        # TIDAK ada user/token/progress baru — hanya update nama + restore progress
        assert _counts(db) == before
        user = db.get(User, existing.id)
        assert user is not None and user.display_name == "Budi Update"
        # token lama tetap valid dan tidak dibuat ulang/ditimpa
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN) is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccessToken)
                .where(AccessToken.user_id == existing.id)
            )
            == 1
        )
        restored = db.scalar(
            select(StudentProgress).where(
                StudentProgress.user_id == existing.id, StudentProgress.lesson_id == hello.id
            )
        )
        assert restored.state == "scored"
        assert restored.score_earned == 3 and restored.score_total == 4
    finally:
        db.close()


def test_import_unknown_student_id_with_empty_token_rejected():
    db = SessionLocal()
    try:
        rows = [_make_row(str(uuid_lib.uuid4()), "", "Siswa Hantu")]
        with pytest.raises(RoundTripImportError) as exc:
            repo.run_student_import(db, rows)
        assert any("tidak dikenal" in e for e in exc.value.errors)
        assert _counts(db)["users"] == 0  # zero write
    finally:
        db.close()


def test_import_teacher_with_empty_token_rejected():
    db = SessionLocal()
    try:
        teacher = _seed_student(db, TEACHER_TOKEN, "Pak Guru", role="teacher")
        rows = [_make_row(teacher.id, "", "Hacker")]
        with pytest.raises(RoundTripImportError) as exc:
            repo.run_student_import(db, rows)
        assert any("teacher" in e for e in exc.value.errors)
        assert _counts(db)["users"] == 1  # zero write
    finally:
        db.close()


def test_import_mixed_existing_restore_and_new_student_atomic():
    db = SessionLocal()
    try:
        hello = _seed_lesson(db, "hello_world", 0)
        existing = _seed_student(db, STUDENT_TOKEN, "Budi")
        rows = [
            _make_row(
                existing.id,
                "",
                "Budi Update",
                progress={"hello_world": ParsedProgress("completed")},
            ),
            _make_row(None, "TOKEN_BARU_12345678", "Siswa Baru"),
        ]
        result = repo.run_student_import(db, rows)
        assert result["students_created"] == 1
        assert result["students_updated"] == 1

        # satu transaksi: keduanya tersimpan bersama
        assert db.get(User, existing.id).display_name == "Budi Update"
        baru = repo.find_user_by_raw_token(db, "TOKEN_BARU_12345678")
        assert baru is not None and baru.role == "student"
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN) is not None  # token lama utuh
    finally:
        db.close()


def test_preview_reports_existing_as_update_restore():
    db = SessionLocal()
    try:
        existing = _seed_student(db, STUDENT_TOKEN, "Budi")
        rows = [
            _make_row(existing.id, "", "Budi", progress={"a": ParsedProgress("completed")}),
            _make_row(None, "TOKEN_12345678", "Baru", progress={"b": ParsedProgress("completed")}),
        ]
        summary = repo.preview_student_import(db, rows)
        assert summary == {
            "rows": 2,
            "students_to_create": 1,
            "students_to_update": 1,
            "progress_to_create": 1,
            "progress_to_restore": 1,
            "conflicts": [],
        }
    finally:
        db.close()


# ── bulk delete ────────────────────────────────────────────────────


def test_delete_students_cascades():
    db = SessionLocal()
    try:
        lesson = _seed_lesson(db, "hello_world", 0)
        s1 = _seed_student(db, STUDENT_TOKEN, "Budi")
        s2 = _seed_student(db, STUDENT2_TOKEN, "Siti")
        repo.set_progress(db, user_id=s1.id, lesson_id=lesson.id, state="completed")

        deleted = repo.delete_students(db, [s1.id, s2.id])
        assert set(deleted) == {s1.id, s2.id}
        db.commit()

        assert db.get(User, s1.id) is None
        assert db.get(User, s2.id) is None
        # cascade: token & progress ikut terhapus
        assert db.scalar(select(func.count()).select_from(AccessToken)) == 0
        assert db.scalar(select(func.count()).select_from(StudentProgress)) == 0
        # lesson tetap ada
        assert db.get(lesson.__class__, lesson.id) is not None
    finally:
        db.close()


def test_delete_rejects_invalid_and_zero_delete():
    db = SessionLocal()
    try:
        s = _seed_student(db, STUDENT_TOKEN, "Budi")
        teacher = _seed_student(db, TEACHER_TOKEN, "Pak Guru", role="teacher")
        db.commit()  # seeding aman dari rollback percobaan delete di bawah

        for bad in (
            [str(uuid_lib.uuid4())],  # unknown
            [teacher.id],  # teacher
            [s.id, s.id],  # duplikat
            ["malformed"],  # non-UUID
            [],  # kosong
            [s.id] * 1001,
        ):
            with pytest.raises(ValueError):
                repo.delete_students(db, bad)
            db.rollback()
        assert db.get(User, s.id) is not None  # tidak ada yang terhapus
        assert db.get(User, teacher.id) is not None
    finally:
        db.close()


# ── round-trip: export → delete → import ───────────────────────────


def test_roundtrip_export_restore_delete_recreate():
    db = SessionLocal()
    try:
        hello = _seed_lesson(db, "hello_world", 0)
        var = _seed_lesson(db, "variabel", 1)
        s1 = _seed_student(db, STUDENT_TOKEN, "Budi Santoso")
        s2 = _seed_student(db, STUDENT2_TOKEN, "Siti Aminah")
        repo.set_progress(db, user_id=s1.id, lesson_id=hello.id, state="completed")
        repo.set_progress(db, user_id=s1.id, lesson_id=var.id, state="scored", score_earned=3, score_total=4)

        # 1) export selection → verifikasi token kosong & progress benar
        csv_bytes = repo.export_students_csv(db, [s1.id])
        active_slugs = ["hello_world", "variabel"]
        text = csv_bytes.decode("utf-8-sig")
        lines = text.strip().splitlines()
        assert lines[0] == "student_id;token;nama_siswa;hello_world;variabel"
        cols = lines[1].split(";")
        assert cols[0] == s1.id and cols[1] == ""  # token kosong
        assert cols[2] == "Budi Santoso" and cols[3] == "completed" and cols[4] == "3/4"

        # 2) export mentah (token kosong) KINI dapat langsung diimport sebagai
        #    restore/update — tanpa membuat user/token baru.
        rows_export = parse_roundtrip_csv(csv_bytes, active_slugs)
        assert len(rows_export) == 1
        assert rows_export[0].student_id == s1.id
        assert rows_export[0].raw_token == ""
        restore_result = repo.run_student_import(db, rows_export)
        assert restore_result["students_updated"] == 1
        assert restore_result["students_created"] == 0
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN) is not None

        # 3) mengisi token pada baris existing → ditolak (siswa existing tidak
        #    boleh menerima token baru)
        filled = text.replace(
            f"{s1.id};;Budi Santoso", f"{s1.id};TOKEN_BARU_12345678;Budi Santoso"
        )
        rows = parse_roundtrip_csv(filled, active_slugs)
        assert len(rows) == 1
        assert rows[0].student_id == s1.id
        assert rows[0].raw_token == "TOKEN_BARU_12345678"
        with pytest.raises(RoundTripImportError) as exc:
            repo.run_student_import(db, rows)
        assert any("tidak boleh menerima token baru" in e for e in exc.value.errors)

        # 4) delete → UUID lama tidak dikenal; import ulang dengan UUID lama
        #    DITOLAK (tidak ada create-with-ID untuk UUID tak dikenal)
        repo.delete_students(db, [s1.id])
        db.commit()
        with pytest.raises(RoundTripImportError) as exc:
            repo.run_student_import(db, rows)
        assert any("tidak dikenal" in e for e in exc.value.errors)

        # 5) siswa baru dibuat dengan student_id KOSONG → UUID baru dari server
        rows_new = parse_roundtrip_csv(
            text.replace(f"{s1.id};;Budi Santoso", ";TOKEN_BARU_12345678;Budi Santoso"),
            active_slugs,
        )
        assert rows_new[0].student_id is None
        result = repo.run_student_import(db, rows_new)
        assert result["students_created"] == 1

        recreated = repo.find_user_by_raw_token(db, "TOKEN_BARU_12345678")
        assert recreated is not None
        assert recreated.id != s1.id  # UUID baru, bukan UUID lama
        assert recreated.display_name == "Budi Santoso"
        progress = {
            p.lesson_id: p for p in repo.list_progress_for_user(db, user_id=recreated.id)
        }
        assert progress[hello.id].state == "completed"
        assert progress[var.id].state == "scored"
        assert progress[var.id].score_earned == 3 and progress[var.id].score_total == 4

        # token lama sudah tidak berlaku
        assert repo.find_user_by_raw_token(db, STUDENT_TOKEN) is None

        # 6) upload file yang sama lagi → ditolak
        with pytest.raises(RoundTripImportError):
            repo.run_student_import(db, rows_new)
    finally:
        db.close()
