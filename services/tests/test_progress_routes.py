"""
Kontrak route progress:
- perilaku tracking/report yang dipertahankan;
- kontrak security BARU yang belum terpenuhi implementasi CSV (RED):
  report tanpa raw token, reset via student_id, log tanpa raw token.

Integrasi PostgreSQL (butuh DATABASE_URL) — backend CSV sudah dicabut.
"""

import logging
import os

import pytest

from services.tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="butuh PostgreSQL nyata"
)


@pytest.fixture(autouse=True)
def _seed(seed_demo_users):
    yield


def test_track_progress_updates(client):
    resp = client.post(
        "/track-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": "hello_world", "status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_track_progress_invalid_token(client):
    resp = client.post(
        "/track-progress",
        json={"token": "TOKEN_SALAH", "lesson_name": "hello_world"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False


def test_track_progress_requires_fields(client):
    resp = client.post("/track-progress", json={"token": STUDENT_TOKEN})
    assert resp.get_json()["success"] is False


def test_student_forbidden_from_report(client):
    resp = client.get(f"/progress-report.json?token={STUDENT_TOKEN}")
    assert resp.status_code == 403


def test_teacher_can_access_report(client):
    resp = client.get(f"/progress-report.json?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    data = resp.get_json()
    # Guru + 2 siswa harusmuncul sebagai row
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
    """RED (sekarang): payload report masih menyertakan kolom token."""
    resp = client.get(f"/progress-report.json?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    for student in resp.get_json()["students"]:
        assert "token" not in student
        assert "digest" not in student


def test_reset_progress_by_student_id(client):
    """Kontrak baru: reset via student_id anonim (user.id), bukan student_token."""
    from services import repositories as repo
    from services import token_service as ts
    from services.database import SessionLocal

    # pastikan ada progress yang bisa di-reset
    assert ts.update_student_progress(STUDENT_TOKEN, "hello_world", "completed") is True

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
    """RED (sekarang): routes/progress.py mencatat token mentah."""
    with caplog.at_level(logging.INFO):
        client.post(
            "/track-progress",
            json={"token": STUDENT_TOKEN, "lesson_name": "hello_world", "status": "completed"},
        )
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


def test_quiz_breakdown_excludes_flashcards(client):
	"""Breakdown eval/diag HANYA menghitung MCQ — flashcard netral.

	Regresi guard untuk bug `eval:4/6`: flashcard ber-kategori 'evaluasi'
	tidak boleh menambah penyebut eval (yang seharusnya = jumlah MCQ evaluasi).
	"""
	from services import token_service as ts

	# Seed attempt untuk Budi: 2 MCQ evaluasi benar + 1 flashcard 'evaluasi'.
	# Skor resmi (statusString) hanya MCQ → "2/2". Breakdown eval harus 2/2,
	# bukan 2/3 (yang akan terjadi kalau flashcard ikut dihitung).
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
	import uuid

	ts.update_student_progress(STUDENT_TOKEN, "hello_world", "2/2")
	resp = client.post(
		"/quiz-attempts/submit",
		json={
			"attempt_id": str(uuid.uuid4()),
			"token": STUDENT_TOKEN,
			"lesson_name": "hello_world",
			"status": "submitted",
			"termination_reason": None,
			"score": "2/2",
			"occurred_at": "2026-01-01T00:00:00Z",
			"started_at": "2026-01-01T00:00:00Z",
			"visibility_event_count": 0,
			"answers": answers,
		},
	)
	assert resp.status_code == 200

	client.set_cookie("student_token", TEACHER_TOKEN)
	report = client.get("/progress-report.json")
	assert report.status_code == 200
	students = {st["nama_siswa"]: st for st in report.get_json()["students"]}
	budi = students["Budi Santoso"]
	assert budi["hello_world"] == "2/2"
	assert budi["hello_world_eval"] == "2/2", (
		f"eval breakdown harus 2/2 (MCQ saja), flashcard netral — dapat {budi['hello_world_eval']!r}"
	)
	assert budi["hello_world_diag"] == "0/0", "diag 0/0 (tidak ada MCQ diagnostik)"
