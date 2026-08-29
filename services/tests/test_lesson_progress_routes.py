"""Kontrak route lesson-progress terpadu (unified exercise + quiz):

- type='exercise' → menandai exercise_passed=true + recompute composite;
- type='quiz'     → finalisasi idempoten quiz_attempt (anti-cheat) + set skor
                    quiz + recompute composite;
- token divalidasi sekali di sini (titik tunggal), lesson wajib dikenal;
- type selain exercise/quiz ditolak; field quiz divalidasi ketat;
- idempotency: retry attempt_id sama → 200 tanpa row ganda (idempotent=true);
- beacon (sendBeacon application/json) diterima.

Integrasi PostgreSQL (butuh DATABASE_URL) — backend CSV sudah dicabut.
"""

import os
import uuid

import pytest

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
        "token": STUDENT_TOKEN,
        "lesson_name": LESSON,
        "type": "quiz",
        "attempt_id": _attempt_id(),
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


# ── type = exercise ─────────────────────────────────────────────

def test_exercise_marks_exercise_passed(client):
    resp = client.post(
        "/lesson-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": LESSON, "type": "exercise"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_exercise_invalid_token_rejected(client):
    resp = client.post(
        "/lesson-progress",
        json={"token": "TOKEN_SALAH", "lesson_name": LESSON, "type": "exercise"},
    )
    assert resp.status_code == 401


def test_exercise_unknown_lesson_rejected(client):
    resp = client.post(
        "/lesson-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": "tidak_ada", "type": "exercise"},
    )
    assert resp.status_code == 404


# ── common validation ───────────────────────────────────────────

def test_missing_token_rejected(client):
    resp = client.post(
        "/lesson-progress",
        json={"lesson_name": LESSON, "type": "exercise"},
    )
    assert resp.status_code == 400


def test_missing_lesson_rejected(client):
    resp = client.post(
        "/lesson-progress",
        json={"token": STUDENT_TOKEN, "type": "exercise"},
    )
    assert resp.status_code == 400


def test_missing_type_rejected(client):
    resp = client.post(
        "/lesson-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": LESSON},
    )
    assert resp.status_code == 400


def test_invalid_type_rejected(client):
    resp = client.post(
        "/lesson-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": LESSON, "type": "biasa"},
    )
    assert resp.status_code == 400


# ── type = quiz (anti-cheat & idempotency) ──────────────────────

def test_quiz_submit_creates_attempt(client):
    resp = client.post(
        "/lesson-progress",
        json=_payload({"status": "submitted", "termination_reason": None, "score": "4/4"}),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["idempotent"] is False
    assert "attempt_id" in body


def test_quiz_retry_same_attempt_id_idempotent(client):
    payload = _payload()
    first = client.post("/lesson-progress", json=payload)
    assert first.status_code == 200
    assert first.get_json()["idempotent"] is False

    second = client.post("/lesson-progress", json=payload)
    assert second.status_code == 200
    assert second.get_json()["idempotent"] is True


def test_quiz_focus_lost_terminated_accepted(client):
    resp = client.post("/lesson-progress", json=_payload())
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_quiz_beacon_format_accepted(client):
    """sendBeacon mengirim application/json; pastikan Flask menanganinya."""
    import json as _json

    payload = _json.dumps(
        _payload({"status": "terminated", "termination_reason": "page_unload", "score": "0/4"})
    )
    resp = client.post(
        "/lesson-progress",
        data=payload,
        content_type="application/json",
    )
    assert resp.status_code == 200


def test_quiz_invalid_status_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"status": "cheated"})
    )
    assert resp.status_code == 400


def test_quiz_focus_lost_must_be_terminated(client):
    resp = client.post(
        "/lesson-progress",
        json=_payload({"status": "submitted", "termination_reason": "focus_lost", "score": "4/4"}),
    )
    assert resp.status_code == 400


def test_quiz_submitted_requires_null_reason(client):
    resp = client.post(
        "/lesson-progress",
        json=_payload({"status": "submitted", "termination_reason": "user_exit"}),
    )
    assert resp.status_code == 400


def test_quiz_invalid_reason_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"termination_reason": "minimize_app"})
    )
    assert resp.status_code == 400


def test_quiz_invalid_score_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"score": "9/4"})
    )
    assert resp.status_code == 400


def test_quiz_malformed_attempt_id_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"attempt_id": "bukan-uuid"})
    )
    assert resp.status_code == 400


def test_quiz_invalid_timestamp_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"occurred_at": "kemarin-sore"})
    )
    assert resp.status_code == 400


def test_quiz_negative_visibility_count_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"visibility_event_count": -1})
    )
    assert resp.status_code == 400


def test_quiz_malformed_json_rejected(client):
    resp = client.post(
        "/lesson-progress", data="{rusak", content_type="application/json"
    )
    assert resp.status_code == 400


def test_quiz_invalid_token_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"token": "TOKEN_SALAH"})
    )
    assert resp.status_code == 401


def test_quiz_unknown_lesson_rejected(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"lesson_name": "tidak_ada"})
    )
    assert resp.status_code == 404


def test_quiz_response_contains_no_raw_token(client):
    resp = client.post("/lesson-progress", json=_payload())
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert STUDENT_TOKEN not in text


def test_quiz_error_does_not_leak_internal_details(client):
    resp = client.post(
        "/lesson-progress", json=_payload({"attempt_id": "bukan-uuid"})
    )
    assert resp.status_code == 400
    assert "traceback" not in resp.get_data(as_text=True).lower()


# ── GET /lesson-progress/<lesson_name> (review-after-refresh) ──

def test_get_progress_requires_token(client):
    resp = client.get(f"/lesson-progress/{LESSON}")
    assert resp.status_code == 400


def test_get_progress_invalid_token_rejected(client):
    resp = client.get(f"/lesson-progress/{LESSON}?token=TOKEN_SALAH")
    assert resp.status_code == 401


def test_get_progress_unknown_lesson_rejected(client):
    resp = client.get("/lesson-progress/tidak_ada?token=" + STUDENT_TOKEN)
    assert resp.status_code == 404


def test_get_progress_returns_audit_after_quiz(client):
    payload = _payload({"status": "submitted", "termination_reason": None, "score": "3/4"})
    client.post("/lesson-progress", json=payload)

    resp = client.get(f"/lesson-progress/{LESSON}?token={STUDENT_TOKEN}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["attempt_id"] == payload["attempt_id"]
    assert body["attempt_score"] == "3/4"
    assert body["answers"] == []
