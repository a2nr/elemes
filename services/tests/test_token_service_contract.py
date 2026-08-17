"""
Kontrak persistence token/progress — mengunci perilaku yang HARUS dipertahankan
setelah cutover penuh ke PostgreSQL (backend CSV sudah dicabut).

Suite ini berjalan TERHADAP PostgreSQL nyata (butuh DATABASE_URL). Seeding
dilakukan via repositories langsung — bukan lewat file CSV.

Semantik PG yang dikunci di sini:
- lesson tanpa record progress → "" (blank = belum mulai), bukan "not_started".
- skor terstruktur → status "3/4".
"""

import os

import pytest

from services import token_service as ts
from services.tests.conftest import STUDENT2_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"), reason="butuh PostgreSQL nyata"
    ),
    pytest.mark.integration,
]


@pytest.fixture(autouse=True)
def _seed_database():
    """Reset + seed data uji: 1 guru, 2 siswa, 3 lesson, progress Budi."""
    from sqlalchemy import text

    from services import repositories as repo
    from services.database import SessionLocal
    from services.models import Lesson

    db = SessionLocal()
    try:
        db.execute(
            text(
                "TRUNCATE quiz_attempts, student_progress, access_tokens, lessons, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        teacher = repo.create_user(db, display_name="Pak Guru", role="teacher")
        repo.create_access_token(db, user_id=teacher.id, raw_token=TEACHER_TOKEN)
        budi = repo.create_user(db, display_name="Budi Santoso", role="student")
        repo.create_access_token(db, user_id=budi.id, raw_token=STUDENT_TOKEN)
        siti = repo.create_user(db, display_name="Siti Aminah", role="student")
        repo.create_access_token(db, user_id=siti.id, raw_token=STUDENT2_TOKEN)
        for idx, slug in enumerate(["hello_world", "quiz_test", "variabel"]):
            db.add(Lesson(slug=slug, title=slug.replace("_", " ").title(), order_index=idx))
        db.commit()

        # progress Budi (seperti baris CSV lama)
        ts.update_student_progress(STUDENT_TOKEN, "hello_world", "completed")
        ts.update_student_progress(STUDENT_TOKEN, "quiz_test", "3/4")
    finally:
        db.close()


def test_valid_token_returns_student_info():
    info = ts.validate_token(TEACHER_TOKEN)
    assert info is not None
    assert info["student_name"] == "Pak Guru"
    assert info["is_teacher"] is True


def test_valid_student_token_not_teacher():
    info = ts.validate_token(STUDENT_TOKEN)
    assert info is not None
    assert info["is_teacher"] is False


def test_unknown_token_rejected():
    assert ts.validate_token("TOKEN_TIDAK_ADA") is None


def test_teacher_role_is_explicit_in_db():
    assert ts.is_teacher_token(TEACHER_TOKEN) is True
    assert ts.is_teacher_token(STUDENT_TOKEN) is False


def test_missing_progress_is_effectively_not_started():
    # Siswa tanpa record progress: semua lesson blank ("") — bukan completed.
    progress = ts.get_student_progress(STUDENT2_TOKEN)
    assert progress is not None
    assert progress["hello_world"] == ""
    assert not progress["quiz_test"]


def test_completed_and_scored_both_count_as_completed():
    progress = ts.get_student_progress(STUDENT_TOKEN)
    assert progress["hello_world"] == "completed"
    assert progress["quiz_test"] == "3/4"
    lessons = [
        {"filename": "hello_world.md"},
        {"filename": "quiz_test.md"},
        {"filename": "variabel.md"},
    ]
    assert ts.calculate_student_completion(progress, lessons) == 2


def test_update_progress_is_idempotent():
    assert ts.update_student_progress(STUDENT_TOKEN, "hello_world", "completed") is True
    assert ts.update_student_progress(STUDENT_TOKEN, "hello_world", "completed") is True
    progress = ts.get_student_progress(STUDENT_TOKEN)
    assert progress["hello_world"] == "completed"


def test_update_unknown_lesson_returns_false():
    assert ts.update_student_progress(STUDENT_TOKEN, "tidak_ada", "completed") is False


def test_update_scored_status_preserved():
    assert ts.update_student_progress(STUDENT_TOKEN, "quiz_test", "3/4") is True
    progress = ts.get_student_progress(STUDENT_TOKEN)
    assert progress["quiz_test"] == "3/4"
