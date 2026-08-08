"""
Token & progress facade — kontrak publik yang dipakai routes.

Mendelegasikan ke storage backend aktif (STORAGE_BACKEND):
  - csv        → services.storage.csv_backend (perilaku historis)
  - postgresql → services.storage.postgres_backend (source of truth baru)

Routes TIDAK boleh tahu backend mana yang aktif — cukup import dari sini.
"""

from services.storage import active_backend_name, get_backend_module


def _backend():
    return get_backend_module()


def validate_token(token):
    """Valid token → {'student_name', 'is_teacher'} | None."""
    return _backend().validate_token(token)


def is_teacher_token(token):
    return _backend().is_teacher_token(token)


def get_teacher_token():
    """Raw token guru — hanya meaningful utk backend CSV; PG → None."""
    return _backend().get_teacher_token()


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


def initialize_tokens_file(lesson_names):
    """Hanya relevan utk backend CSV (buat file bila belum ada)."""
    if active_backend_name() == "csv":
        from services.storage.csv_backend import initialize_tokens_file as _init

        return _init(lesson_names)
    return None


def _get_tokens():
    """Internal (CSV cache) — dipakai test kontrak; PG mengembalikan ({}, [])."""
    backend = _backend()
    if hasattr(backend, "_get_tokens"):
        return backend._get_tokens()
    return {}, []
