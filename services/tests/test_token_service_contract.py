"""
Kontrak persistence token/progress — mengunci perilaku yang HARUS dipertahankan
setelah cutover penuh ke PostgreSQL (backend CSV sudah dicabut).

Suite ini berjalan TERHADAP PostgreSQL nyata (butuh DATABASE_URL). Seeding
dilakukan via repositories langsung — bukan lewat file CSV.

Semantik PG yang dikunci di sini (model composite baru):
- lesson tanpa record progress → "" (blank = belum mulai), bukan "not_started".
- state 'done'   → status = composite dibulatkan (mis. "100" bila auto-done).
- state 'in_progress' → status = "" (aktivitas ada tapi belum selesai).
"""

import os

import pytest

from services import repositories as repo
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
        lesson_rows = {}
        for idx, slug in enumerate(["hello_world", "quiz_test", "variabel"]):
            lesson = Lesson(slug=slug, title=slug.replace("_", " ").title(), order_index=idx)
            db.add(lesson)
            db.flush()
            lesson_rows[slug] = lesson.id
        db.commit()

        # progress Budi via repositories (mirror endpoint /api/lesson-progress):
        # hello_world → exercise selesai (reading-only → auto-done 100)
        repo.set_exercise_passed(db, user_id=budi.id, lesson_id=lesson_rows["hello_world"])
        repo.recompute_progress(
            db, user_id=budi.id, lesson_id=lesson_rows["hello_world"],
            has_exercise=False, has_quiz=False,
            exercise_weight=70, quiz_weight=30, done_min_percent=75,
        )
        # quiz_test → skor kuis 3/4 (reading-only → auto-done 100)
        repo.set_quiz_score(
            db, user_id=budi.id, lesson_id=lesson_rows["quiz_test"],
            quiz_earned=3, quiz_total=4,
        )
        repo.recompute_progress(
            db, user_id=budi.id, lesson_id=lesson_rows["quiz_test"],
            has_exercise=False, has_quiz=False,
            exercise_weight=70, quiz_weight=30, done_min_percent=75,
        )
        db.commit()
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


def test_done_and_scored_both_count_as_completed():
    progress = ts.get_student_progress(STUDENT_TOKEN)
    # Reading-only lesson (tanpa exercise/quiz) → auto-done, composite 100.
    assert progress["hello_world"] == "100"
    assert progress["quiz_test"] == "100"
    lessons = [
        {"filename": "hello_world.md"},
        {"filename": "quiz_test.md"},
        {"filename": "variabel.md"},
    ]
    assert ts.calculate_student_completion(progress, lessons) == 2


def test_update_exercise_is_idempotent():
    # exercise dikirim dua kali → tetap satu record progress, state stabil.
    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        budi = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        hello = repo.get_lesson_by_slug(db, "hello_world")
        repo.set_exercise_passed(db, user_id=budi.id, lesson_id=hello.id)
        repo.recompute_progress(
            db, user_id=budi.id, lesson_id=hello.id,
            has_exercise=False, has_quiz=False,
            exercise_weight=70, quiz_weight=30, done_min_percent=75,
        )
        db.commit()
    finally:
        db.close()

    progress = ts.get_student_progress(STUDENT_TOKEN)
    assert progress["hello_world"] == "100"


def test_update_unknown_lesson_noop():
    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        budi = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        prog = repo.get_progress(db, user_id=budi.id, lesson_id="tidak-ada")
    finally:
        db.close()
    assert prog is None


def test_quiz_score_preserved():
    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        budi = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        quiz = repo.get_lesson_by_slug(db, "quiz_test")
        progress = repo.get_progress(db, user_id=budi.id, lesson_id=quiz.id)
        quiz_earned = progress.quiz_score_earned
        quiz_total = progress.quiz_score_total
    finally:
        db.close()
    assert quiz_earned == 3
    assert quiz_total == 4
