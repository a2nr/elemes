"""
Kontrak persistence token/progress — mengunci perilaku yang HARUS dipertahankan
ketika storage diganti dari CSV ke PostgreSQL.

Bagian ini dijalankan terhadap storage aktif (awalnya CSV). Setelah Task 9,
suite yang sama dijalankan terhadap kedua backend.
"""

from services import token_service as ts
from services.tests.conftest import STUDENT2_TOKEN, STUDENT_TOKEN, TEACHER_TOKEN


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


def test_teacher_role_is_first_data_row_only():
    assert ts.is_teacher_token(TEACHER_TOKEN) is True
    assert ts.is_teacher_token(STUDENT_TOKEN) is False


def test_missing_progress_is_effectively_not_started():
    # Kolom lesson yang tidak pernah tercatat tidak boleh dianggap completed.
    progress = ts.get_student_progress(STUDENT2_TOKEN)
    assert progress is not None
    # hello_world = not_started (kolom ada, nilainya not_started)
    assert progress["hello_world"] == "not_started"
    # quiz_test = blank → falsy
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
