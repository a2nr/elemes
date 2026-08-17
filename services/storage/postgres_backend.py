"""
Storage backend PostgreSQL — implementasi kontrak token/progress
melalui repositories (SQLAlchemy). Token mentah tidak pernah disimpan;
validasi via HMAC-SHA256 digest + role eksplisit di tabel users.
"""

import logging
import json

from sqlalchemy import select

from services import repositories as repo
from services.database import SessionLocal
from services.models import User
from services.progress_status import format_progress_status, parse_progress_status
from services.repositories import (
    count_completed_lessons,
    find_user_by_raw_token,
    get_lesson_by_slug,
    get_user_by_token,
    list_lessons,
    list_progress_for_user,
    list_quiz_attempts_for_user,
    set_progress,
)

logger = logging.getLogger(__name__)


def calculate_student_completion(student_data, all_lessons):
    """Kontrak kompatibel — PG memakai COUNT DB, helper ini disediakan utk parity API."""
    from services.storage.completion import calculate_student_completion as _calc

    return _calc(student_data, all_lessons)


def _status_to_string(progress) -> str:
    """Render progress DB ke kontrak legacy (helper bersama progress_status)."""
    return format_progress_status(progress)


def _parse_status(status: str):
    """Normalisasi status input → (state, score_earned, score_total) | None."""
    try:
        return parse_progress_status(status)
    except ValueError:
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
    """Reset via student_id = user.id (PG) — teacher tidak perlu token siswa.

    Reset menghapus audit attempt (one-attempt) bersama progress agar siswa
    dapat mengulang kuis setelah reset guru.
    """
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
        repo.delete_quiz_attempts(db, user_id=user.id, lesson_id=lesson.id)
        set_progress(db, user_id=user.id, lesson_id=lesson.id, state="not_started")
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def get_all_students_progress(all_lessons_func):
    """Semua user (siswa + guru) + ordered_lessons dari registry.

    Guru ikut ditampilkan sebagai row di report /progress agar bisa di-review
    materinya (dan di-reset progresnya sendiri). Field `role` menandai
    apakah row tersebut guru atau siswa. Student dict TIDAK mengandung token
    mentah (kontrak keamanan).
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

        # Semua user (tanpa filter role) — guru ikut sebagai row, urutan
        # deterministik (created_at, id) agar stable untuk UI/export.
        users = list(
            db.scalars(
                select(User)
                .order_by(User.created_at, User.id)
            )
        )
        students = []
        for user in users:
            rows = {p.lesson_id: p for p in list_progress_for_user(db, user_id=user.id)}
            attempts = {
                a.lesson_id: a for a in list_quiz_attempts_for_user(db, user_id=user.id)
            }
            student = {'nama_siswa': user.display_name, 'id': user.id, 'role': user.role}
            for lesson in lessons:
                student[lesson.slug] = _status_to_string(rows.get(lesson.id))
                # Metadata anti-cheat — field TERPISAH, tidak mengubah kontrak
                # status lama. `has_violation` hanya untuk reason focus_lost.
                attempt = attempts.get(lesson.id)
                student[f"{lesson.slug}_attempt_status"] = attempt.status if attempt else ""
                student[f"{lesson.slug}_termination_reason"] = (
                    attempt.termination_reason if attempt else ""
                )
                student[f"{lesson.slug}_has_violation"] = bool(
                    attempt and attempt.termination_reason == "focus_lost"
                )
                student[f"{lesson.slug}_attempt_finished_at"] = (
                    attempt.finished_at.isoformat() if attempt and attempt.finished_at else ""
                )
                # Breakdown kategori (evaluasi / diagnostik) dari answers_json attempt —
                # untuk report guru. Sama seperti FE calculateQuizResult: breakdown
                # HANYA dihitung untuk soal MCQ; flashcard netral (tidak masuk eval
                # maupun diag) supaya penyebut eval = jumlah MCQ evaluasi, konsisten
                # dengan skor resmi (statusString) yang juga cuma MCQ.
                if attempt and attempt.answers_json:
                    try:
                        answers = json.loads(attempt.answers_json)
                    except (json.JSONDecodeError, TypeError):
                        answers = []
                    eval_correct = 0
                    eval_total = 0
                    diag_correct = 0
                    diag_total = 0
                    for ans in answers:
                        # Flashcard netral: abaikan dari breakdown eval/diag.
                        if ans.get('type') == 'flashcard':
                            continue
                        cat = ans.get('category', 'evaluasi')
                        if cat == 'diagnostik':
                            diag_total += 1
                            if ans.get('is_correct'):
                                diag_correct += 1
                        else:
                            eval_total += 1
                            if ans.get('is_correct'):
                                eval_correct += 1
                    student[f"{lesson.slug}_eval"] = f"{eval_correct}/{eval_total}"
                    student[f"{lesson.slug}_diag"] = f"{diag_correct}/{diag_total}"
                    student[f"{lesson.slug}_diag_unmastered"] = json.dumps(
                        [
                            a.get('question_id', '')
                            for a in answers
                            if a.get('type') != 'flashcard'
                            and a.get('category') == 'diagnostik'
                            and not a.get('is_correct')
                        ]
                    )
                else:
                    student[f"{lesson.slug}_eval"] = ""
                    student[f"{lesson.slug}_diag"] = ""
                    student[f"{lesson.slug}_diag_unmastered"] = "[]"
            student['completed_count'] = count_completed_lessons(db, user_id=user.id)
            students.append(student)
        return students, ordered_lessons
    finally:
        db.close()

