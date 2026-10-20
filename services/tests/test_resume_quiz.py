"""
Kontrak route resume-quiz-attempt (izin guru melanjutkan attempt terminated):

- teacher-only via teacher_token + student_id (bukan token siswa);
- hanya attempt `terminated` yang bisa di-resume (submitted ditolak);
- setelah resume: gate one-attempt terbuka (has_quiz_attempt False) dan
  siswa dapat menyelesaikan ulang kuis dengan attempt_id SAMA — row attempt
  ditimpa sekali, resumed_at di-clear, progress di-update; retry idempotent;
- report guru menampilkan field `{slug}_resumed_at`.

Integrasi PostgreSQL (butuh DATABASE_URL) — backend CSV sudah dicabut.
"""

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

LESSON = "hello_world"


@pytest.fixture(autouse=True)
def _seed(seed_demo_users):
    yield


def _post_quiz(client, attempt_id, *, status, reason, score, answers=None):
    return client.post(
        "/lesson-progress",
        json={
            "token": STUDENT_TOKEN,
            "lesson_name": LESSON,
            "type": "quiz",
            "attempt_id": attempt_id,
            "status": status,
            "termination_reason": reason,
            "score": score,
            "occurred_at": "2026-08-09T14:04:44.000Z",
            "started_at": "2026-08-09T14:03:00.000Z",
            "visibility_event_count": 1,
            "answers": answers or [],
        },
    )


def _post_resume(client, student_id, lesson=LESSON):
    return client.post(
        "/resume-quiz-attempt",
        json={
            "teacher_token": TEACHER_TOKEN,
            "student_id": student_id,
            "lesson_name": lesson,
        },
    )


def _student_id():
    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        return repo.find_user_by_raw_token(db, STUDENT_TOKEN).id
    finally:
        db.close()


# ── auth & validasi ─────────────────────────────────────────────


def test_resume_requires_teacher(client):
    resp = client.post(
        "/resume-quiz-attempt",
        json={
            "teacher_token": STUDENT_TOKEN,
            "student_id": _student_id(),
            "lesson_name": LESSON,
        },
    )
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_resume_requires_fields(client):
    resp = client.post(
        "/resume-quiz-attempt",
        json={"teacher_token": TEACHER_TOKEN, "student_id": _student_id()},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_resume_unknown_student_fails(client):
    resp = _post_resume(client, str(uuid.uuid4()))
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False


def test_resume_unknown_lesson_fails(client):
    resp = _post_resume(client, _student_id(), lesson="lesson_tidak_ada")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False


# ── syarat attempt ──────────────────────────────────────────────


def test_resume_without_attempt_fails(client):
    resp = _post_resume(client, _student_id())
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False


def test_resume_submitted_attempt_rejected(client):
    """Attempt submitted (selesai normal) tidak perlu & tidak bisa di-resume."""
    attempt_id = str(uuid.uuid4())
    assert _post_quiz(client, attempt_id, status="submitted", reason=None, score="4/4").status_code == 200

    resp = _post_resume(client, _student_id())
    assert resp.status_code == 200
    assert resp.get_json()["success"] is False


# ── perilaku sukses ─────────────────────────────────────────────


def test_resume_terminated_attempt_succeeds(client):
    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200

    resp = _post_resume(client, _student_id())
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # resumed_at terisi di DB
    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        user = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        lesson = repo.get_lesson_by_slug(db, LESSON)
        attempt = repo.get_quiz_attempt_for_user_lesson(db, user_id=user.id, lesson_id=lesson.id)
        assert attempt is not None
        assert attempt.resumed_at is not None
    finally:
        db.close()

    # gate one-attempt terbuka
    from services.token_service import has_quiz_attempt

    assert has_quiz_attempt(STUDENT_TOKEN, LESSON) is False


def test_resume_idempotent(client):
    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="page_unload", score="1/4"
    ).status_code == 200

    assert _post_resume(client, _student_id()).get_json()["success"] is True
    # Resume ulang tetap sukses (tanpa batas, keputusan desain 3a)
    assert _post_resume(client, _student_id()).get_json()["success"] is True


# ── roundtrip penuh: resume → selesaikan ulang → idempotent ────


def test_resume_then_resubmit_updates_attempt_and_progress(client):
    """Siswa menyelesaikan ulang kuis dengan attempt_id SAMA setelah resume.

    Row attempt ditimpa sekali (status submitted, skor baru), resumed_at
    di-clear, dan progress quiz di-update. Retry payload sama → idempotent.
    """
    attempt_id = str(uuid.uuid4())
    answers_v1 = [
        {"question_id": "q1", "selected_option_id": "o-a", "is_correct": True, "category": "evaluasi", "type": "mcq"},
        {"question_id": "q2", "selected_option_id": None, "is_correct": False, "category": "evaluasi", "type": "mcq"},
    ]
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4", answers=answers_v1
    ).status_code == 200
    assert _post_resume(client, _student_id()).get_json()["success"] is True

    # Siswa menyelesaikan ulang: semua soal benar
    answers_v2 = [
        {"question_id": "q1", "selected_option_id": "o-a", "is_correct": True, "category": "evaluasi", "type": "mcq"},
        {"question_id": "q2", "selected_option_id": "o-b", "is_correct": True, "category": "evaluasi", "type": "mcq"},
    ]
    resp = _post_quiz(
        client, attempt_id, status="submitted", reason=None, score="4/4", answers=answers_v2
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["idempotent"] is False

    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        user = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        lesson = repo.get_lesson_by_slug(db, LESSON)
        attempt = repo.get_quiz_attempt_for_user_lesson(db, user_id=user.id, lesson_id=lesson.id)
        assert attempt.status == "submitted"
        assert attempt.termination_reason is None
        assert attempt.score_earned == 4
        assert attempt.score_total == 4
        assert attempt.resumed_at is None, "resumed_at harus ter-clear setelah finalisasi ulang"

        progress = repo.get_progress(db, user_id=user.id, lesson_id=lesson.id)
        assert progress.quiz_score_earned == 4
        assert progress.quiz_score_total == 4
    finally:
        db.close()

    # Retry payload sama → idempotent, row tidak ditimpa lagi
    retry = _post_quiz(
        client, attempt_id, status="submitted", reason=None, score="4/4", answers=answers_v2
    )
    assert retry.get_json()["idempotent"] is True


def test_resume_then_terminate_again_allows_second_resume(client):
    """Siswa fokus-lost lagi saat sesi lanjutan → terminated lagi → resume ulang."""
    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200
    assert _post_resume(client, _student_id()).get_json()["success"] is True

    # Sesi lanjutan dihentikan lagi (fokus-lost kedua)
    again = _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="3/4"
    )
    assert again.status_code == 200
    assert again.get_json()["idempotent"] is False

    from services import repositories as repo
    from services.database import SessionLocal

    db = SessionLocal()
    try:
        user = repo.find_user_by_raw_token(db, STUDENT_TOKEN)
        lesson = repo.get_lesson_by_slug(db, LESSON)
        attempt = repo.get_quiz_attempt_for_user_lesson(db, user_id=user.id, lesson_id=lesson.id)
        assert attempt.status == "terminated"
        assert attempt.score_earned == 3
        assert attempt.resumed_at is None
    finally:
        db.close()

    # Guru boleh resume ulang (tanpa batas)
    assert _post_resume(client, _student_id()).get_json()["success"] is True


# ── report guru ─────────────────────────────────────────────────


def test_report_includes_resumed_at(client):
    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200

    # Sebelum resume: kosong
    client.set_cookie("student_token", TEACHER_TOKEN)
    report = client.get("/progress-report.json")
    budi = next(s for s in report.get_json()["students"] if s["nama_siswa"] == "Budi Santoso")
    assert budi[f"{LESSON}_resumed_at"] == ""

    # Setelah resume: terisi ISO timestamp
    assert _post_resume(client, _student_id()).get_json()["success"] is True
    report = client.get("/progress-report.json")
    budi = next(s for s in report.get_json()["students"] if s["nama_siswa"] == "Budi Santoso")
    assert budi[f"{LESSON}_resumed_at"] != ""


# ── sinyal UI siswa & gate setelah re-finalisasi ────────────────


def test_lesson_data_quiz_resumable_flag(client):
    """Endpoint data lesson membawa `quiz_resumable` yang dipakai UI siswa."""
    import pathlib

    from services import lesson_service

    content_dir = pathlib.Path(os.environ["CONTENT_DIR"])
    (content_dir / f"{LESSON}.md").write_text("# Hello World\n\nMateri.\n", encoding="utf-8")
    for fn in (
        lesson_service.find_lesson_file,
        lesson_service.get_lessons,
        lesson_service.get_lesson_names,
        lesson_service.get_lessons_with_learning_objectives,
    ):
        fn.cache_clear()

    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200

    # Sebelum resume: gate aktif, belum resumable
    resp = client.get(f"/lesson/{LESSON}.json?token={STUDENT_TOKEN}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_quiz_attempt"] is True
    assert data["quiz_resumable"] is False

    assert _post_resume(client, _student_id()).get_json()["success"] is True

    # Setelah resume: gate terbuka + sinyal resume
    resp = client.get(f"/lesson/{LESSON}.json?token={STUDENT_TOKEN}")
    data = resp.get_json()
    assert data["has_quiz_attempt"] is False
    assert data["quiz_resumable"] is True


def test_has_quiz_attempt_closed_after_resubmit(client):
    """Setelah siswa menyelesaikan ulang, gate one-attempt aktif kembali."""
    from services.token_service import has_quiz_attempt

    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200
    assert _post_resume(client, _student_id()).get_json()["success"] is True
    assert has_quiz_attempt(STUDENT_TOKEN, LESSON) is False

    assert _post_quiz(
        client, attempt_id, status="submitted", reason=None, score="4/4"
    ).status_code == 200
    assert has_quiz_attempt(STUDENT_TOKEN, LESSON) is True


def test_reset_while_resumed_still_works(client):
    """Guru me-reset attempt yang sedang di-resume — attempt dihapus, progress bersih."""
    from services.token_service import has_quiz_attempt

    attempt_id = str(uuid.uuid4())
    assert _post_quiz(
        client, attempt_id, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200
    assert _post_resume(client, _student_id()).get_json()["success"] is True

    resp = client.post(
        "/reset-progress",
        json={
            "teacher_token": TEACHER_TOKEN,
            "student_id": _student_id(),
            "lesson_name": LESSON,
        },
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # Attempt hilang + progress not_started
    assert has_quiz_attempt(STUDENT_TOKEN, LESSON) is False
    get_resp = client.get(f"/lesson-progress/{LESSON}?token={STUDENT_TOKEN}")
    data = get_resp.get_json()
    assert data["attempt_id"] is None
    assert data["state"] == "not_started"


def test_resubmit_different_attempt_id_while_resumed_conflicts(client):
    """Attempt_id BARU saat (user, lesson) masih punya attempt → 409 one-attempt."""
    first = str(uuid.uuid4())
    assert _post_quiz(
        client, first, status="terminated", reason="focus_lost", score="2/4"
    ).status_code == 200
    assert _post_resume(client, _student_id()).get_json()["success"] is True

    second = str(uuid.uuid4())
    resp = _post_quiz(client, second, status="submitted", reason=None, score="4/4")
    assert resp.status_code == 409


def test_resume_attempt_without_answers(client):
    """Attempt legacy tanpa answers_json → resume tetap jalan (answers kosong)."""
    attempt_id = str(uuid.uuid4())
    # Payload TANPA field "answers" → answers_json NULL
    resp = client.post(
        "/lesson-progress",
        json={
            "token": STUDENT_TOKEN,
            "lesson_name": LESSON,
            "type": "quiz",
            "attempt_id": attempt_id,
            "status": "terminated",
            "termination_reason": "page_unload",
            "score": "1/4",
            "occurred_at": "2026-08-09T14:04:44.000Z",
            "started_at": "2026-08-09T14:03:00.000Z",
            "visibility_event_count": 1,
        },
    )
    assert resp.status_code == 200

    assert _post_resume(client, _student_id()).get_json()["success"] is True

    get_resp = client.get(f"/lesson-progress/{LESSON}?token={STUDENT_TOKEN}")
    data = get_resp.get_json()
    assert data["answers"] == []
    assert data["attempt_resumed_at"] is not None
