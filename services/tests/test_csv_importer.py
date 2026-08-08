"""
CSV importer — parse & validasi (unit, host) + import ke PostgreSQL
(integrasi — skip bila DATABASE_URL tidak diset).
"""

import os
from pathlib import Path

import pytest

from services.csv_importer import (
    parse_csv,
    run_import,
    validate_and_plan,
)

FIXTURES = Path(__file__).parent / "fixtures"
DB_REQUIRED = os.environ.get("DATABASE_URL", "").strip()


# ── parse ──────────────────────────────────────────────────────────


def test_parse_valid_fixture():
    rows = parse_csv(FIXTURES / "tokens_valid.csv")
    assert len(rows) == 3
    assert rows[0]["token"] == "TOKEN_GURU_001"
    assert rows[1]["nama_siswa"] == "Budi Santoso"


def test_parse_missing_file():
    with pytest.raises(FileNotFoundError):
        parse_csv(FIXTURES / "tidak_ada.csv")


def test_parse_empty_csv(tmp_path):
    f = tmp_path / "kosong.csv"
    f.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_csv(f)


# ── validasi & plan ────────────────────────────────────────────────


def test_plan_valid_fixture():
    plan = validate_and_plan(parse_csv(FIXTURES / "tokens_valid.csv"))
    assert plan.ok
    assert len(plan.users) == 3
    assert plan.users[0].role == "teacher"
    assert plan.users[1].role == "student"
    assert plan.lesson_slugs == ["hello_world", "quiz_test", "variabel"]

    budi = plan.users[1]
    assert budi.progress["hello_world"].state == "completed"
    assert budi.progress["quiz_test"].state == "scored"
    assert budi.progress["quiz_test"].score_earned == 3
    assert budi.progress["quiz_test"].score_total == 4
    assert budi.progress["variabel"].state == "not_started"


def test_plan_invalid_fixture_errors():
    plan = validate_and_plan(parse_csv(FIXTURES / "tokens_invalid.csv"))
    assert not plan.ok
    joined = "\n".join(plan.errors)
    # status tidak dikenal, token duplikat, nama kosong, skor earned>total, token kosong
    assert "selesai" in joined
    assert "Duplikat" in joined or "duplikat" in joined
    assert "nama_siswa kosong" in joined
    assert "4/2" in joined
    assert "token kosong" in joined


def test_plan_empty_rows():
    plan = validate_and_plan([])
    assert not plan.ok


def test_plan_dry_run_no_write(monkeypatch):
    plan = validate_and_plan(parse_csv(FIXTURES / "tokens_valid.csv"))
    called = []

    class FakeSession:
        def commit(self):
            called.append("commit")

        def rollback(self):
            called.append("rollback")

    report = run_import(FakeSession(), plan, dry_run=True)
    assert called == []
    assert report.users_created == 3
    # sparse model: not_started/blank TIDAK membuat progress row
    # (guru 3 + budi 2 + siti 0 = 5 materialized)
    assert report.progress_upserted == 5


# ── integrasi (PostgreSQL nyata) ───────────────────────────────────


@pytest.mark.skipif(not DB_REQUIRED, reason="butuh DATABASE_URL (PostgreSQL nyata)")
def test_import_to_db_and_idempotent():
    from services import repositories
    from services.database import SessionLocal
    from services.token_hashing import hash_token

    plan = validate_and_plan(parse_csv(FIXTURES / "tokens_valid.csv"))
    db = SessionLocal()
    try:
        first = run_import(db, plan, dry_run=False)
        assert first.ok, first.errors
        assert first.users_created == 3
        assert first.tokens_created == 3
        assert first.lessons_created == 3
        # sparse: 5 progress rows materialized (bukan 9 — not_started tidak di-insert)
        assert first.progress_upserted == 5

        # legacy '3/4' tersimpan terstruktur
        user = repositories.find_user_by_raw_token(db, "TOKEN_SISWA_001")
        assert user is not None and user.role == "student"
        teacher = repositories.find_user_by_raw_token(db, "TOKEN_GURU_001")
        assert teacher is not None and teacher.role == "teacher"

        # idempotent: run kedua tidak bikin duplikat
        second = run_import(db, plan, dry_run=False)
        assert second.ok, second.errors
        assert second.users_created == 0
        assert second.tokens_created == 0
        assert second.lessons_created == 0
        assert second.progress_upserted == 5

        from sqlalchemy import func, select

        from services.models import AccessToken, StudentProgress, User

        assert db.scalar(select(func.count()).select_from(User)) == 3
        assert db.scalar(select(func.count()).select_from(AccessToken)) == 3
        assert db.scalar(select(func.count()).select_from(StudentProgress)) == 5
        # sparse model: tidak boleh ada row state='not_started'
        assert (
            db.scalar(
                select(func.count()).select_from(StudentProgress).where(
                    StudentProgress.state == "not_started"
                )
            )
            == 0
        )

        scored = db.scalar(
            select(StudentProgress).where(
                StudentProgress.user_id == user.id,
                StudentProgress.state == "scored",
            )
        )
        assert scored is not None
        assert scored.score_earned == 3 and scored.score_total == 4

        # hash tersimpan, bukan plaintext
        digest = hash_token("TOKEN_SISWA_001")
        assert db.scalar(
            select(AccessToken.id).where(AccessToken.token_hash == digest)
        ) is not None
        assert (
            db.scalar(select(func.count()).select_from(AccessToken).where(
                AccessToken.token_hash == "TOKEN_SISWA_001"
            ))
            == 0
        )
    finally:
        db.close()
