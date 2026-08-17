"""Kontrak route quiz attempt (anti-cheat / focus-loss):

- finalisasi normal (submitted) & termination (focus_lost) → satu row
  quiz_attempts + update student_progress dalam satu transaksi;
- idempotency: retry attempt_id sama → 200 tanpa row ganda dan reason
  pertama dipertahankan;
- konflik: attempt_id dipakai attempt lain → 409; attempt baru untuk
  (user, lesson) yang sudah punya attempt → 409 (one-attempt);
- validasi ketat status/reason/timestamp/score;
- raw token tidak pernah muncul di response.

Integrasi PostgreSQL (butuh DATABASE_URL) — backend CSV sudah dicabut.
"""

import os
import uuid

import pytest
from sqlalchemy import func, select

from services import repositories as repo
from services.database import SessionLocal
from services.models import QuizAttempt, StudentProgress
from services.tests.conftest import STUDENT_TOKEN

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"), reason="butuh PostgreSQL nyata"
    ),
    pytest.mark.integration,
]

LESSON = "hello_world"


def _attempt_id() -> str:
    return str(uuid.uuid4())


def _payload(overrides: dict | None = None) -> dict:
    data = {
        "attempt_id": _attempt_id(),
        "token": STUDENT_TOKEN,
        "lesson_name": LESSON,
        "status": "terminated",
        "termination_reason": "focus_lost",
        "score": "2/4",
        "occurred_at": "2026-08-09T14:04:44.000Z",
        "started_at": "2026-08-09T14:03:00.000Z",
        "visibility_event_count": 1,
        "answers": [],
    }
    if overrides:
        data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _seed(seed_demo_users):
    yield


def _attempt_rows(db):
    return db.scalar(select(func.count()).select_from(QuizAttempt)) or 0


def _student_id(db):
    user = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
    assert user is not None
    return user.id


def test_submit_completed_creates_attempt_and_progress(client):
    resp = client.post(
        "/quiz-attempts/submit",
        json=_payload({"status": "submitted", "termination_reason": None, "score": "4/4"}),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["idempotent"] is False
    assert "attempt_id" in body

    db = SessionLocal()
    try:
        assert _attempt_rows(db) == 1
        attempt = db.get(QuizAttempt, body["attempt_id"])
        assert attempt is not None
        assert attempt.status == "submitted"
        assert attempt.termination_reason is None
        assert attempt.score_earned == 4 and attempt.score_total == 4
        progress = db.scalar(
            select(StudentProgress).where(StudentProgress.user_id == _student_id(db))
        )
        assert progress is not None
        assert progress.state == "scored"
    finally:
        db.close()


def test_submit_focus_lost_terminated(client):
    resp = client.post("/quiz-attempts/submit", json=_payload())
    assert resp.status_code == 200
    body = resp.get_json()

    db = SessionLocal()
    try:
        attempt = db.get(QuizAttempt, body["attempt_id"])
        assert attempt is not None
        assert attempt.status == "terminated"
        assert attempt.termination_reason == "focus_lost"
        assert attempt.visibility_event_count == 1
    finally:
        db.close()


def test_submit_retry_same_attempt_id_idempotent(client):
    payload = _payload()
    first = client.post("/quiz-attempts/submit", json=payload)
    assert first.status_code == 200

    # Retry (mis. beacon + fetch ganda) → sukses, tanpa row kedua,
    # reason pertama tetap dipertahankan.
    second = client.post("/quiz-attempts/submit", json=payload)
    assert second.status_code == 200
    body = second.get_json()
    assert body["success"] is True
    assert body["idempotent"] is True

    db = SessionLocal()
    try:
        assert _attempt_rows(db) == 1
        attempt = db.get(QuizAttempt, payload["attempt_id"])
        assert attempt.termination_reason == "focus_lost"
        assert attempt.visibility_event_count == 1
    finally:
        db.close()


def test_submit_second_attempt_new_id_same_lesson_rejected(client):
    """One-attempt policy: unique (user_id, lesson_id) menolak attempt kedua."""
    first = client.post("/quiz-attempts/submit", json=_payload())
    assert first.status_code == 200

    second = client.post(
        "/quiz-attempts/submit", json=_payload({"attempt_id": _attempt_id()})
    )
    assert second.status_code == 409

    db = SessionLocal()
    try:
        assert _attempt_rows(db) == 1
    finally:
        db.close()


def test_submit_attempt_id_already_used_by_other_lesson_conflict(client):
    from services.models import Lesson

    db = SessionLocal()
    try:
        db.add(Lesson(slug="variabel", title="Variabel", order_index=1))
        db.commit()
    finally:
        db.close()

    attempt_id = _attempt_id()
    ok = client.post("/quiz-attempts/submit", json=_payload({"attempt_id": attempt_id}))
    assert ok.status_code == 200

    conflict = client.post(
        "/quiz-attempts/submit",
        json=_payload({"attempt_id": attempt_id, "lesson_name": "variabel"}),
    )
    assert conflict.status_code == 409
    assert conflict.get_json()["success"] is False

    db = SessionLocal()
    try:
        assert _attempt_rows(db) == 1
        assert repo.get_quiz_attempt_by_id(db, attempt_id).lesson.slug == LESSON
    finally:
        db.close()


def test_submit_invalid_status_rejected(client):
    resp = client.post("/quiz-attempts/submit", json=_payload({"status": "cheated"}))
    assert resp.status_code == 400


def test_submit_focus_lost_must_be_terminated(client):
    resp = client.post(
        "/quiz-attempts/submit",
        json=_payload({"status": "submitted", "termination_reason": "focus_lost", "score": "4/4"}),
    )
    assert resp.status_code == 400


def test_submit_completed_requires_null_reason(client):
    resp = client.post(
        "/quiz-attempts/submit",
        json=_payload({"status": "submitted", "termination_reason": "user_exit"}),
    )
    assert resp.status_code == 400


def test_submit_invalid_reason_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", json=_payload({"termination_reason": "minimize_app"})
    )
    assert resp.status_code == 400


def test_submit_invalid_score_rejected(client):
    resp = client.post("/quiz-attempts/submit", json=_payload({"score": "9/4"}))
    assert resp.status_code == 400


def test_submit_malformed_attempt_id_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", json=_payload({"attempt_id": "bukan-uuid"})
    )
    assert resp.status_code == 400


def test_submit_invalid_timestamp_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", json=_payload({"occurred_at": "kemarin-sore"})
    )
    assert resp.status_code == 400


def test_submit_negative_visibility_count_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", json=_payload({"visibility_event_count": -1})
    )
    assert resp.status_code == 400


def test_submit_malformed_json_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", data="{rusak", content_type="application/json"
    )
    assert resp.status_code == 400


def test_submit_invalid_token_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", json=_payload({"token": "TOKEN_SALAH"})
    )
    assert resp.status_code == 401


def test_submit_unknown_lesson_rejected(client):
    resp = client.post(
        "/quiz-attempts/submit", json=_payload({"lesson_name": "tidak_ada"})
    )
    assert resp.status_code == 404


def test_submit_flashcards_only_score_completed(client):
    resp = client.post(
        "/quiz-attempts/submit",
        json=_payload({"status": "submitted", "termination_reason": None, "score": "completed"}),
    )
    assert resp.status_code == 200
    body = resp.get_json()

    db = SessionLocal()
    try:
        attempt = db.get(QuizAttempt, body["attempt_id"])
        assert attempt.status == "submitted"
        assert attempt.score_earned is None and attempt.score_total is None
        progress = db.scalar(
            select(StudentProgress).where(StudentProgress.user_id == _student_id(db))
        )
        assert progress.state == "completed"
    finally:
        db.close()


def test_submit_response_contains_no_raw_token(client):
    resp = client.post("/quiz-attempts/submit", json=_payload())
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert STUDENT_TOKEN not in text


def test_submit_error_does_not_leak_internal_details(client):
    resp = client.post(
        "/quiz-attempts/submit",
        json=_payload({"attempt_id": "bukan-uuid"}),
    )
    assert resp.status_code == 400
    assert "traceback" not in resp.get_data(as_text=True).lower()
