"""
Token & progress facade — kontrak publik yang dipakai routes.

Mendelegasikan ke satu-satunya storage backend aktif: PostgreSQL
(services.storage.postgres_backend). Backend CSV sudah dicabut setelah
cutover penuh — routes TIDAK boleh tahu detail backend, cukup import sini.
"""

from services.storage import get_backend_module


def _backend():
    return get_backend_module()


def validate_token(token):
    """Valid token → {'student_name', 'is_teacher'} | None."""
    return _backend().validate_token(token)


def is_teacher_token(token):
    return _backend().is_teacher_token(token)


def get_student_progress(token):
    """Dict {lesson_slug: status} | None."""
    return _backend().get_student_progress(token)


def update_student_progress(token, lesson_name, status="completed"):
    return _backend().update_student_progress(token, lesson_name, status)


def reset_student_progress(student_id, lesson_name):
    """Reset progress siswa by student_id (id anonim dari report — bukan token)."""
    return _backend().reset_progress(student_id, lesson_name)


def get_all_students_progress(all_lessons_func):
    """(students, ordered_lessons) — tanpa token mentah di student dict."""
    return _backend().get_all_students_progress(all_lessons_func)


def calculate_student_completion(student_data, all_lessons):
    """Helper murni bersama (parity kedua backend)."""
    from services.storage.completion import calculate_student_completion as _calc

    return _calc(student_data, all_lessons)
