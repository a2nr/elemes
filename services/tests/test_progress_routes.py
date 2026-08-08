"""
Kontrak route progress:
- perilaku tracking/report yang dipertahankan;
- kontrak security BARU yang belum terpenuhi implementasi CSV (RED):
  report tanpa raw token, reset via student_id, log tanpa raw token.
"""

import logging

import pytest

from services.tests.conftest import STUDENT_TOKEN, TEACHER_TOKEN


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
    assert data["students"]
    assert data["lessons"]


def test_report_contains_no_raw_access_token(client):
    """RED (sekarang): payload report masih menyertakan kolom token."""
    resp = client.get(f"/progress-report.json?token={TEACHER_TOKEN}")
    assert resp.status_code == 200
    for student in resp.get_json()["students"]:
        assert "token" not in student
        assert "digest" not in student


def test_reset_progress_by_student_id(client):
    """RED lama (student_token) diganti kontrak baru: reset via student_id anonim."""
    import hashlib

    from services.storage import active_backend_name

    if active_backend_name() == "csv":
        student_id = hashlib.sha256(STUDENT_TOKEN.encode()).hexdigest()
    else:
        # PG: student_id = user.id; diuji di test integrasi (butuh DB hidup)
        pytest.skip("reset by user.id diuji pada test integrasi PostgreSQL")

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
