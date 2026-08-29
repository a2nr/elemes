"""Flow komposit end-to-end via /lesson-progress.

Skenario utama:
- Lesson dengan BOTH exercise (tab c) DAN quiz → exercise + quiz 3/4
  → composite 92.5 (> 75) → state='done';
- exercise saja tanpa quiz → state='in_progress' (composite 70 < 75) → belum done;
- quiz 0/4 setelah exercise → composite 70 < 75 → state='in_progress'.

Lesson dibuat via marker markdown (---INITIAL_CODE--- untuk tab c, dan
---INITIAL_QUIZ--- untuk tab quiz) supaya _lesson_components() di route
mendeteksi has_exercise=True dan has_quiz=True.

Integrasi PostgreSQL (butuh DATABASE_URL).
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

LESSON_BOTH = "lesson_both"


@pytest.fixture()
def lesson_both_content(tmp_path, monkeypatch):
    """Lesson markdown dengan tab exercise (c) + tab quiz."""
    md = tmp_path / f"{LESSON_BOTH}.md"
    md.write_text(
        "# Lesson Both\n\n"
        "---INITIAL_CODE---\n```c\nvoid setup(){}\n```\n"
        "---INITIAL_QUIZ---\n"
        "# Kuis\n\n"
        "1. Berapa 1+1?\n"
        "- [x] 2\n- [ ] 3\n\n"
        "> Kunci: 2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("services.lesson_service.CONTENT_DIR", str(tmp_path))
    return md


@pytest.fixture(autouse=True)
def _seed(seed_demo_users, lesson_both_content):
    """Seed lesson row di DB + pastikan content lesson tersedia."""
    from sqlalchemy import text

    from services import repositories as repo
    from services.database import SessionLocal

    if SessionLocal is None:
        pytest.skip("butuh PostgreSQL nyata")
    db = SessionLocal()
    try:
        # seed_demo_users sudah meng-truncate; tambahkan lesson baru.
        db.execute(
            text(
                "INSERT INTO lessons (id, slug, title, order_index) "
                "VALUES (:id, :slug, :title, :order) "
                "ON CONFLICT (slug) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "slug": LESSON_BOTH, "title": "Lesson Both", "order": 5},
        )
        db.commit()
    finally:
        db.close()
    yield


def _quiz_payload(attempt_id: str, score: str, status: str = "submitted") -> dict:
    return {
        "token": STUDENT_TOKEN,
        "lesson_name": LESSON_BOTH,
        "type": "quiz",
        "attempt_id": attempt_id,
        "status": status,
        "termination_reason": None if status == "submitted" else "focus_lost",
        "score": score,
        "occurred_at": "2026-01-01T00:00:00",
        "started_at": "2026-01-01T00:00:00",
        "visibility_event_count": 0,
        "answers": [],
    }


def _post_exercise(client):
    return client.post(
        "/lesson-progress",
        json={"token": STUDENT_TOKEN, "lesson_name": LESSON_BOTH, "type": "exercise"},
    )


def _fetch(client):
    return client.get(f"/lesson-progress/{LESSON_BOTH}?token={STUDENT_TOKEN}")


def test_exercise_then_quiz_makes_done(client):
    _post_exercise(client)
    resp = client.post(
        "/lesson-progress",
        json=_quiz_payload(str(uuid.uuid4()), "3/4"),
    )
    assert resp.status_code == 200

    body = _fetch(client).get_json()
    assert body["state"] == "done"
    assert body["composite_percent"] == 92.5


def test_exercise_only_not_done_without_quiz(client):
    _post_exercise(client)
    body = _fetch(client).get_json()
    assert body["state"] == "in_progress"
    assert body["exercise_passed"] is True


def test_low_quiz_below_threshold_not_done(client):
    _post_exercise(client)
    resp = client.post(
        "/lesson-progress",
        json=_quiz_payload(str(uuid.uuid4()), "0/4"),
    )
    assert resp.status_code == 200

    body = _fetch(client).get_json()
    assert body["state"] == "in_progress"
    assert body["composite_percent"] == 70.0


def test_reading_flow_returns_audit_answer_fields(client):
    """GET setelah quiz mengembalikan audit answers (untuk review-after-refresh)."""
    ans = [
        {
            "question_id": "q1",
            "selected_option_id": "opt2",
            "is_correct": True,
            "category": "evaluasi",
            "type": "mcq",
        }
    ]
    resp = client.post(
        "/lesson-progress",
        json={
            **_quiz_payload(str(uuid.uuid4()), "4/4"),
            "answers": ans,
        },
    )
    assert resp.status_code == 200

    body = _fetch(client).get_json()
    assert body["success"] is True
    assert body["answers"] == ans
