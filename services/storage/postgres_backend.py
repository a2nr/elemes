"""
Storage backend PostgreSQL — implementasi kontrak token/progress
melalui repositories (SQLAlchemy). Token mentah tidak pernah disimpan;
validasi via HMAC-SHA256 digest + role eksplisit di tabel users.
"""

import logging

from sqlalchemy import select

from services import repositories as repo
from services.database import SessionLocal
from services.models import User
from services.repositories import (
    count_completed_lessons,
    find_user_by_raw_token,
    get_lesson_by_slug,
    get_user_by_token,
    list_lessons,
    list_progress_for_user,
    set_progress,
)

logger = logging.getLogger(__name__)


def calculate_student_completion(student_data, all_lessons):
    """Kontrak kompatibel — PG memakai COUNT DB, helper ini disediakan utk parity API."""
    from services.storage.completion import calculate_student_completion as _calc

    return _calc(student_data, all_lessons)


def _status_to_string(progress) -> str:
    """Render progress DB ke format kontrak lama: 'completed' | 'not_started' | '3/4'."""
    if progress is None:
        return ""
    if progress.state == "scored":
        return f"{progress.score_earned}/{progress.score_total}"
    return progress.state


def _parse_status(status: str):
    """Normalisasi status input → (state, score_earned, score_total) | None."""
    status = (status or "").strip()
    if status in ("", "not_started"):
        return ("not_started", None, None)
    if status == "completed":
        return ("completed", None, None)
    parts = status.split("/")
    if len(parts) == 2:
        try:
            earned, total = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        if total > 0 and 0 <= earned <= total:
            return ("scored", earned, total)
    return None


def validate_token(token):
    if not token or SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        user = get_user_by_token(db, token)
        db.commit()
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()
    if user is None:
        return None
    return {
        'student_name': user.display_name,
        'is_teacher': user.role == "teacher",
    }


def is_teacher_token(token):
    info = validate_token(token)
    return bool(info and info["is_teacher"])


def get_teacher_token():
    """Raw teacher token TIDAK dapat direkonstruksi dari DB (hanya hash ada).

    Tidak ada route yang memakai nilai ini; dikembalikan None demi kontrak.
    """
    return None


def get_student_progress(token):
    """Dict {lesson_slug: status} — lesson tanpa record → '' (blank, not_started)."""
    if not token or SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        user = find_user_by_raw_token(db, token)
        if user is None:
            return None
        lessons = list_lessons(db)
        rows = {p.lesson_id: p for p in list_progress_for_user(db, user_id=user.id)}
        return {
            lesson.slug: _status_to_string(rows.get(lesson.id))
            for lesson in lessons
        }
    finally:
        db.close()


def update_student_progress(token, lesson_name, status="completed"):
    if SessionLocal is None:
        return False
    parsed = _parse_status(status)
    if parsed is None:
        logging.warning("Status tidak dikenal untuk lesson %s: %r", lesson_name, status)
        return False
    state, earned, total = parsed
    db = SessionLocal()
    try:
        user = find_user_by_raw_token(db, token)
        if user is None:
            return False
        lesson = get_lesson_by_slug(db, lesson_name)
        if lesson is None:
            return False
        set_progress(
            db,
            user_id=user.id,
            lesson_id=lesson.id,
            state=state,
            score_earned=earned,
            score_total=total,
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def reset_progress(student_id, lesson_name):
    """Reset via student_id = user.id (PG) — teacher tidak perlu token siswa."""
    if SessionLocal is None:
        return False
    db = SessionLocal()
    try:
        user = repo.get_user_by_id(db, student_id)
        if user is None:
            return False
        lesson = get_lesson_by_slug(db, lesson_name)
        if lesson is None:
            return False
        set_progress(db, user_id=user.id, lesson_id=lesson.id, state="not_started")
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def get_all_students_progress(all_lessons_func):
    """Semua siswa (guru ikut, urutan created_at) + ordered_lessons dari registry.

    Student dict TIDAK mengandung token mentah (kontrak keamanan).
    """
    if SessionLocal is None:
        return [], []
    db = SessionLocal()
    try:
        lessons = list_lessons(db)
        all_lessons_dict = {}
        for lesson in all_lessons_func():
            lesson_key = lesson['filename'].replace('.md', '')
            all_lessons_dict[lesson_key] = lesson

        ordered_lessons = []
        for lesson in lessons:
            slug = lesson.slug
            if slug in all_lessons_dict:
                ordered_lessons.append(all_lessons_dict[slug])
            else:
                ordered_lessons.append({
                    'filename': f"{slug}.md",
                    'title': lesson.title,
                    'description': 'Lesson information not available',
                })

        users = list(db.scalars(select(User).order_by(User.created_at)))
        students = []
        for user in users:
            rows = {p.lesson_id: p for p in list_progress_for_user(db, user_id=user.id)}
            student = {'nama_siswa': user.display_name, 'id': user.id}
            for lesson in lessons:
                student[lesson.slug] = _status_to_string(rows.get(lesson.id))
            student['completed_count'] = count_completed_lessons(db, user_id=user.id)
            students.append(student)
        return students, ordered_lessons
    finally:
        db.close()
