"""
Kontrak route progress:
- perilaku tracking/report yang dipertahankan (via endpoint lesson-progress terpadu);
- kontrak security: report tanpa raw token, reset via student_id, log tanpa raw token.

Integrasi PostgreSQL (butuh DATABASE_URL) — backend CSV sudah dicabut.
"""

import logging
import os
import uuid

import pytest

from services.tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"), reason="butuh PostgreSQL nyata"
    ),
    pytest.mark.integration,
]


@pytest.fixture(autouse=True)
def _seed(seed_demo_users):
    yield


def _post_exercise(client, lesson="hello_world"):
    return client.post(
        "/api/lesson-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": lesson, "type": "exercise"},
    )


def _post_quiz(client, score, answers=None, lesson="hello_world"):
    return client.post(
        "/api/lesson-progress",
        json={
            "token": STUDENT_TOKEN,
            "lesson_name": lesson,
            "type": "quiz",
            "attempt_id": str(uuid.uuid4()),
            "status": "submitted",
            "termination_reason": None,
            "score": score,
            "occurred_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:00:00Z",
            "visibility_event_count": 0,
            "answers": answers or [],
        },
    )


def test_lesson_progress_exercise_updates(client):
    resp = _post_exercise(client)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_lesson_progress_invalid_token(client):
    resp = client.post(
        "/api/lesson-progress",
        json={"token": "TOKEN_SALAH", "lesson_name": "hello_world", "type": "exercise"},
    )
    assert resp.status_code == 401


def test_lesson_progress_requires_fields(client):
    resp = client.post("/api/lesson-progress", json={"token": STUDENT_TOKEN})
    assert resp.status_code == 400


def test_student_forbidden_from_report(client):
    resp = client.get(f"/progress-report.json?token={STUDENT_TOKEN}")
    assert resp.status_code == 403


def test_teacher_can_access_report(client):
    resp = client.get(f"/progress-report.json?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    data = resp.get_json()
    # Guru + 2 siswa harus muncul sebagai row
    assert len(data["students"]) == 3
    assert data["lessons"]


def test_teacher_appears_in_progress_report(client):
    resp = client.get(f"/progress-report.json?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["students"]) == 3  # 1 guru + 2 siswa
    roles = {row["nama_siswa"]: row["role"] for row in data["students"]}
    assert roles["Pak Guru"] == "teacher"
    assert roles["Budi Santoso"] == "student"
    assert roles["Siti Aminah"] == "student"


def test_report_contains_no_raw_access_token(client):
    resp = client.get(f"/progress-report.json?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    for student in resp.get_json()["students"]:
        assert "token" not in student
        assert "digest" not in student


def test_reset_progress_by_student_id(client):
    """Kontrak: reset via student_id anonim (user.id), bukan student_token."""
    from services import repositories as repo
    from services.database import SessionLocal

    # pastikan ada progress yang bisa di-reset (lewat endpoint terpadu)
    assert _post_exercise(client).status_code == 200

    db = SessionLocal()
    try:
        budi = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        student_id = budi.id
    finally:
        db.close()

    resp = client.post(
        "/reset-progress",
        json={
            "teacher_token": TEACHER_TOKEN,
            "student_id": student_id,
            "lesson_name": "hello_world",
        },
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # kontrak lama (student_token) harus ditolak
    legacy = client.post(
        "/reset-progress",
        json={
            "teacher_token": TEACHER_TOKEN,
            "student_token": STUDENT_TOKEN,
            "lesson_name": "hello_world",
        },
    )
    assert legacy.status_code == 400
    assert legacy.get_json()["success"] is False


def test_raw_token_not_in_logs(client, caplog):
    with caplog.at_level(logging.INFO):
        _post_exercise(client)
    assert STUDENT_TOKEN not in caplog.text


def test_pg_report_includes_teacher_and_students(client):
    """Report PostgreSQL memuat semua user: guru + siswa sebagai row terpisah.

    Data (Pak Guru/Budi/Siti + lesson hello_world) berasal dari fixture
    `seed_demo_users` — tidak di-seed ulang di sini karena token_hash
    deterministik (HMAC+pepper) menabrak unique constraint.
    """
    client.set_cookie("student_token", TEACHER_TOKEN)
    resp = client.get("/progress-report.json")
    assert resp.status_code == 200
    data = resp.get_json()
    names = [st["nama_siswa"] for st in data["students"]]
    assert "Pak Guru" in names
    assert "Budi Santoso" in names
    assert "Siti Aminah" in names
    # guru punya role teacher, siswa punya role student
    roles = {st["nama_siswa"]: st["role"] for st in data["students"]}
    assert roles["Pak Guru"] == "teacher"
    assert roles["Budi Santoso"] == "student"
    # field yang dipertahankan untuk frontend
    for st in data["students"]:
        assert st["id"]
        assert "completed_count" in st
        assert "hello_world" in st
        assert "hello_world_composite" in st


def test_quiz_breakdown_excludes_flashcards(client):
    """Breakdown eval/diag HANYA menghitung MCQ — flashcard netral.

    Regresi guard untuk bug `eval:4/6`: flashcard ber-kategori 'evaluasi'
    tidak boleh menambah penyebut eval (yang seharusnya = jumlah MCQ evaluasi).
    """
    answers = [
        {
            "question_id": "mcq-1",
            "selected_option_id": "o-a",
            "is_correct": True,
            "category": "evaluasi",
            "type": "mcq",
        },
        {
            "question_id": "mcq-2",
            "selected_option_id": "o-b",
            "is_correct": True,
            "category": "evaluasi",
            "type": "mcq",
        },
        {
            "question_id": "fc-1",
            "selected_option_id": None,
            "is_correct": False,
            "category": "evaluasi",
            "type": "flashcard",
        },
    ]
    resp = _post_quiz(client, "2/2", answers=answers)
    assert resp.status_code == 200

    client.set_cookie("student_token", TEACHER_TOKEN)
    report = client.get("/progress-report.json")
    assert report.status_code == 200
    students = {st["nama_siswa"]: st for st in report.get_json()["students"]}
    budi = students["Budi Santoso"]
    assert "hello_world" in budi, "status sel utama tetap dipertahankan"
    assert budi["hello_world_eval"] == "2/2", (
        f"eval breakdown harus 2/2 (MCQ saja), flashcard netral — dapat {budi['hello_world_eval']!r}"
    )
    assert budi["hello_world_diag"] == "0/0", "diag 0/0 (tidak ada MCQ diagnostik)"


def test_quiz_combined_eval_diag_score_saved(client):
    """Attempt campuran 4 eval + 2 diag menghasilkan score 3/6 di endpoint lesson-progress."""
    answers = [
        {"question_id": "eval-1", "selected_option_id": "o-a", "is_correct": True, "category": "evaluasi", "type": "mcq"},
        {"question_id": "eval-2", "selected_option_id": "o-b", "is_correct": True, "category": "evaluasi", "type": "mcq"},
        {"question_id": "eval-3", "selected_option_id": "o-c", "is_correct": False, "category": "evaluasi", "type": "mcq"},
        {"question_id": "eval-4", "selected_option_id": "o-d", "is_correct": False, "category": "evaluasi", "type": "mcq"},
        {"question_id": "diag-1", "selected_option_id": "o-e", "is_correct": True, "category": "diagnostik", "type": "mcq"},
        {"question_id": "diag-2", "selected_option_id": "o-f", "is_correct": False, "category": "diagnostik", "type": "mcq"},
    ]
    # Client frontend menghitung 3/6 (gabungan 2 eval + 1 diag benar dari total 6 MCQ)
    resp = _post_quiz(client, "3/6", answers=answers)
    assert resp.status_code == 200

    get_resp = client.get(f"/lesson-progress/hello_world?token={STUDENT_TOKEN}")
    assert get_resp.status_code == 200
    data = get_resp.get_json()
    assert data["quiz_score_earned"] == 3
    assert data["quiz_score_total"] == 6


def test_progress_report_reflects_done_state_in_completed_count(client):
    """Progress report JSON menghitung completed_count untuk siswa yang memiliki progress 'done'."""
    from services.database import SessionLocal
    from services import repositories as repo
    from services.models import Lesson

    db = SessionLocal()
    try:
        budi = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        l1 = repo.get_lesson_by_slug(db, "hello_world")
        l2 = Lesson(slug="variabel_test", title="Variabel Test", order_index=1)
        db.add(l2)
        db.commit()

        repo.set_progress(db, user_id=budi.id, lesson_id=l1.id, state="done")
        repo.set_progress(db, user_id=budi.id, lesson_id=l2.id, state="done")
        db.commit()
    finally:
        db.close()

    client.set_cookie("student_token", TEACHER_TOKEN)
    resp = client.get("/progress-report.json")
    assert resp.status_code == 200
    data = resp.get_json()
    budi_entry = next(s for s in data["students"] if s["nama_siswa"] == "Budi Santoso")
    assert budi_entry["completed_count"] == 2


def test_export_progress_csv_requires_teacher(client):
    """GET /progress-report/export-csv butuh otentikasi role guru."""
    # Tanpa token -> 401
    resp = client.get("/progress-report/export-csv")
    assert resp.status_code == 401

    # Token siswa -> 403
    resp = client.get(f"/progress-report/export-csv?token={STUDENT_TOKEN}")
    assert resp.status_code == 403


def test_export_progress_csv_contains_composite_scores(client):
    """GET /progress-report/export-csv menghasilkan CSV berisi nilai komposit per lesson."""
    import csv
    import io
    from services.database import SessionLocal
    from services import repositories as repo
    from services.models import Lesson

    db = SessionLocal()
    try:
        budi = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        l1 = repo.get_lesson_by_slug(db, "hello_world")
        l2 = Lesson(slug="variabel_test", title="Variabel Test", order_index=1)
        db.add(l2)
        db.commit()

        # Budi: hello_world composite = 93.0, variabel_test composite = 70.0
        p1 = repo.set_progress(db, user_id=budi.id, lesson_id=l1.id, state="done")
        p1.composite_percent = 92.5
        p2 = repo.set_progress(db, user_id=budi.id, lesson_id=l2.id, state="done")
        p2.composite_percent = 70.0
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/progress-report/export-csv?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type

    text = resp.data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    fieldnames = reader.fieldnames

    # Header harus memuat nama_siswa, slug lesson, dan completed_count
    assert "nama_siswa" in fieldnames
    assert "hello_world" in fieldnames
    assert "completed_count" in fieldnames
    # Tidak boleh ada internal metadata fields seperti _attempt_status dsb
    assert not any(f.endswith("_attempt_status") for f in fieldnames)
    assert not any(f.endswith("_diag_unmastered") for f in fieldnames)

    rows = list(reader)
    budi_row = next(r for r in rows if r["nama_siswa"] == "Budi Santoso")
    assert budi_row["hello_world"] == "92" or budi_row["hello_world"] == "93"  # round(92.5) == 92 or 93
    assert budi_row["variabel_test"] == "70"
    assert budi_row["completed_count"] == "2"

    # Siswa lain yang belum mencoba harus bernilai kosong "" untuk kolom nilai
    siti_row = next(r for r in rows if r["nama_siswa"] == "Siti Aminah")
    assert siti_row["hello_world"] == ""
    assert siti_row["completed_count"] == "0"


