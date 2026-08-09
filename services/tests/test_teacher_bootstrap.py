"""
Test bootstrap guru canonical (`services/teacher_bootstrap.py` + CLI).

Unit (tanpa DB):
- Validasi nama/token.
- CLI exit code 2 bila DATABASE_URL tidak tersedia.

Integrasi (PostgreSQL nyata, skip tanpa DATABASE_URL):
- create saat belum ada guru; idempotent; rotasi token mempertahankan UUID;
  penolakan token siswa; fail-closed >1 guru; reactivate token revoked;
  rollback saat create token gagal; output tanpa secret.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from services.teacher_bootstrap import TeacherBootstrapError, upsert_teacher

from .conftest import STUDENT_TOKEN, TEACHER_TOKEN

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "bootstrap_teacher.py"


# ── unit: validasi (tanpa DB) ────────────────────────────────────────────

def test_validation_empty_name():
    with pytest.raises(TeacherBootstrapError, match="Nama guru"):
        upsert_teacher(None, display_name="   ", raw_token="TOKEN_X")


def test_validation_empty_token():
    with pytest.raises(TeacherBootstrapError, match="Token guru"):
        upsert_teacher(None, display_name="Pak Guru", raw_token="")


def test_validation_name_too_long():
    with pytest.raises(TeacherBootstrapError, match="terlalu panjang"):
        upsert_teacher(None, display_name="G" * 256, raw_token="TOKEN_X")


def test_cli_exit_2_without_database():
    """Tanpa DATABASE_URL, CLI harus gagal dengan exit code 2 (bukan crash)."""
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    proc = subprocess.run(
        [sys.executable, str(CLI), "Pak Guru"],
        input="TOKEN_APA_SAJA\n",
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "database" in (proc.stderr or "").lower()


# ── integrasi (PostgreSQL nyata) ─────────────────────────────────────────

needs_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="butuh PostgreSQL nyata"
)


def _db():
    from services.database import SessionLocal

    assert SessionLocal is not None
    return SessionLocal()


def _counts(db):
    from sqlalchemy import func, select

    from services.models import AccessToken, User

    return {
        "teachers": db.scalar(
            select(func.count()).select_from(User).where(User.role == "teacher")
        ),
        "students": db.scalar(
            select(func.count()).select_from(User).where(User.role == "student")
        ),
        "tokens": db.scalar(select(func.count()).select_from(AccessToken)),
        "active_tokens": db.scalar(
            select(func.count())
            .select_from(AccessToken)
            .where(AccessToken.revoked_at.is_(None))
        ),
    }


@needs_db
class TestTeacherBootstrapDB:
    """Skenario database — hanya jalan saat DATABASE_URL tersedia."""

    def test_create_when_no_teacher(self):
        db = _db()
        try:
            result = upsert_teacher(db, display_name="Pak Guru", raw_token=TEACHER_TOKEN)
            assert result["action"] == "created"
            counts = _counts(db)
            assert counts["teachers"] == 1
            assert counts["tokens"] == 1
            assert counts["active_tokens"] == 1
        finally:
            db.close()

    def test_idempotent_same_token_and_name(self):
        db = _db()
        try:
            upsert_teacher(db, display_name="Pak Guru", raw_token=TEACHER_TOKEN)
            result = upsert_teacher(db, display_name="Pak Guru", raw_token=TEACHER_TOKEN)
            assert result["action"] == "unchanged"
            counts = _counts(db)
            assert counts["teachers"] == 1
            assert counts["tokens"] == 1
            assert counts["active_tokens"] == 1
        finally:
            db.close()

    def test_update_keeps_uuid_and_rotates_token(self):
        db = _db()
        try:
            first = upsert_teacher(db, display_name="Guru Lama", raw_token=TEACHER_TOKEN)
            assert first["action"] == "created"

            from services import repositories as repo
            from services.models import AccessToken, User
            from sqlalchemy import select

            teacher = db.scalar(select(User).where(User.role == "teacher"))
            teacher_id = teacher.id
            old_token_row = db.scalar(
                select(AccessToken).where(AccessToken.user_id == teacher_id)
            )

            result = upsert_teacher(db, display_name="Guru Baru", raw_token="TOKEN_GURU_ROTASI")
            assert result["action"] == "updated"
            assert "token" in result["message"]

            counts = _counts(db)
            assert counts["teachers"] == 1  # jumlah guru tetap satu
            assert counts["tokens"] == 2  # 1 revoked + 1 aktif
            assert counts["active_tokens"] == 1

            teacher = db.scalar(select(User).where(User.role == "teacher"))
            assert teacher.id == teacher_id  # UUID dipertahankan
            assert teacher.display_name == "Guru Baru"
            assert repo.find_user_by_raw_token(db, "TOKEN_GURU_ROTASI").id == teacher_id
            # token lama sudah di-revoke
            db.refresh(old_token_row)
            assert old_token_row.revoked_at is not None
        finally:
            db.close()

    def test_reactivate_revoked_token_no_duplicate(self):
        db = _db()
        try:
            upsert_teacher(db, display_name="Guru", raw_token=TEACHER_TOKEN)
            # Rotasi: token lama di-revoke
            upsert_teacher(db, display_name="Guru", raw_token="TOKEN_GURU_ROTASI")
            counts_after_rotate = _counts(db)
            assert counts_after_rotate["tokens"] == 2

            # Pakai lagi token lama → harus reactivate baris lama, bukan insert baru
            result = upsert_teacher(db, display_name="Guru", raw_token=TEACHER_TOKEN)
            assert result["action"] == "updated"
            counts = _counts(db)
            assert counts["tokens"] == 2  # tidak ada baris duplikat digest
            assert counts["active_tokens"] == 1
        finally:
            db.close()

    def test_reject_student_token(self):
        db = _db()
        try:
            upsert_teacher(db, display_name="Pak Guru", raw_token=TEACHER_TOKEN)

            from services import repositories as repo

            s = repo.create_user(db, display_name="Budi", role="student")
            repo.create_access_token(db, user_id=s.id, raw_token=STUDENT_TOKEN)
            db.commit()

            with pytest.raises(TeacherBootstrapError, match="siswa"):
                upsert_teacher(db, display_name="Pak Guru", raw_token=STUDENT_TOKEN)

            # nama & token guru tidak berubah
            from services.models import AccessToken, User
            from sqlalchemy import select

            teacher = db.scalar(select(User).where(User.role == "teacher"))
            assert teacher.display_name == "Pak Guru"
            active = db.scalar(
                select(AccessToken).where(
                    AccessToken.user_id == teacher.id,
                    AccessToken.revoked_at.is_(None),
                )
            )
            assert active.token_hash == repo.hash_token(TEACHER_TOKEN)
        finally:
            db.close()

    def test_reject_student_token_when_no_teacher_yet(self):
        db = _db()
        try:
            from services import repositories as repo

            s = repo.create_user(db, display_name="Budi", role="student")
            repo.create_access_token(db, user_id=s.id, raw_token=STUDENT_TOKEN)
            db.commit()

            with pytest.raises(TeacherBootstrapError, match="siswa"):
                upsert_teacher(db, display_name="Pak Guru", raw_token=STUDENT_TOKEN)
            counts = _counts(db)
            assert counts["teachers"] == 0
        finally:
            db.close()

    def test_fail_closed_multiple_teachers(self):
        db = _db()
        try:
            from services import repositories as repo
            from services.models import User
            from sqlalchemy import select

            t1 = repo.create_user(db, display_name="Guru A", role="teacher")
            repo.create_access_token(db, user_id=t1.id, raw_token=TEACHER_TOKEN)
            t2 = repo.create_user(db, display_name="Guru B", role="teacher")
            repo.create_access_token(db, user_id=t2.id, raw_token="TOKEN_GURU_LAIN")
            db.commit()

            with pytest.raises(TeacherBootstrapError, match="lebih dari satu"):
                upsert_teacher(db, display_name="Guru", raw_token="TOKEN_BARU")

            # tidak ada guru yang dihapus/diubah
            teachers = list(db.scalars(select(User).where(User.role == "teacher")))
            assert len(teachers) == 2
        finally:
            db.close()

    def test_rollback_on_token_create_failure(self, monkeypatch):
        db = _db()
        try:
            upsert_teacher(db, display_name="Guru Lama", raw_token=TEACHER_TOKEN)

            import services.teacher_bootstrap as tb

            def boom(db_, *, user_id, raw_token):
                raise RuntimeError("simulasi kegagalan")

            monkeypatch.setattr(tb, "create_access_token", boom)

            from services.models import User
            from sqlalchemy import select

            with pytest.raises(RuntimeError):
                upsert_teacher(db, display_name="Guru Baru", raw_token="TOKEN_BARU")

            # rollback: nama lama tetap tersimpan
            teacher = db.scalar(select(User).where(User.role == "teacher"))
            assert teacher.display_name == "Guru Lama"
        finally:
            db.close()

    def test_result_contains_no_secret(self):
        db = _db()
        try:
            result = upsert_teacher(db, display_name="Pak Guru", raw_token=TEACHER_TOKEN)
            text = str(result)
            assert TEACHER_TOKEN not in text
        finally:
            db.close()

    def test_cli_success_via_stdin(self):
        """CLI: nama dari argv, token dari stdin → exit 0 tanpa secret di stdout."""
        env = os.environ.copy()
        proc = subprocess.run(
            [sys.executable, str(CLI), "Pak Guru"],
            input=f"{TEACHER_TOKEN}\n",
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            env=env,
            timeout=60,
        )
        assert proc.returncode == 0
        assert TEACHER_TOKEN not in proc.stdout
        assert TEACHER_TOKEN not in proc.stderr
