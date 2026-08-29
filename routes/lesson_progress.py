"""Unified lesson progress endpoint (exercise + quiz) — single-point token validation.

POST /lesson-progress
  body: {token, lesson_name, type: 'exercise'|'quiz', ...type-specific fields}

GET  /lesson-progress/<lesson_name>
  query: ?token=...  -> progress state + composite + quiz attempt audit

Replaces the fragmented /track-progress (exercise) and /quiz-attempts/submit
(quiz) endpoints. Token validation happens ONCE at the top of the POST/GET
handlers. Route paths deliberately omit the /api prefix — the SvelteKit
hooks.server.ts proxy strips /api and forwards to Flask.

The OLD endpoints (routes/progress.py, routes/quiz_attempts.py) remain in place
and are removed in a separate task.
"""

import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from services import repositories as repo
from services.database import SessionLocal
from services.progress_status import parse_progress_status
from services.student_roundtrip import is_canonical_uuid
from config import LESSON_EXERCISE_WEIGHT, LESSON_QUIZ_WEIGHT, LESSON_DONE_MIN_PERCENT
from services.lesson_service import render_markdown_content, find_lesson_file, get_lesson_components

lesson_progress_bp = Blueprint("lesson_progress", __name__)

logger = logging.getLogger(__name__)

ALLOWED_REASONS = {"focus_lost", "spa_navigation", "page_unload", "user_exit", "completed"}
MAX_PAYLOAD_BYTES = 64 * 1024
MAX_SCORE_LENGTH = 32
MAX_AGENT_LENGTH = 255


def _parse_ts(value, *, required: bool) -> datetime | None:
    """ISO-8601 timestamp -> datetime UTC-aware. Raise ValueError bila invalid."""
    if value in (None, ""):
        if required:
            raise ValueError
        return None
    if not isinstance(value, str):
        raise ValueError
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@lesson_progress_bp.route("/lesson-progress", methods=["POST"])
def submit_lesson_progress():
    if request.content_length is not None and request.content_length > MAX_PAYLOAD_BYTES:
        return jsonify({"success": False, "message": "Payload terlalu besar"}), 413

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Malformed JSON"}), 400

    token = str(data.get("token") or "").strip()
    lesson_name = str(data.get("lesson_name") or "").strip()
    progress_type = str(data.get("type") or "").strip()

    # ── validasi field dasar ─────────────────────────────────────────
    if not token or not lesson_name:
        return jsonify({"success": False, "message": "Token dan lesson wajib diisi"}), 400
    if progress_type not in ("exercise", "quiz"):
        return jsonify({"success": False, "message": "type harus 'exercise' atau 'quiz'"}), 400

    if SessionLocal is None:
        return jsonify({"success": False, "message": "PostgreSQL tidak aktif"}), 503

    db = SessionLocal()
    try:
        # ── SINGLE POINT OF TOKEN VALIDATION ──────────────────────────
        user = repo.get_user_by_token(db, token)
        if user is None:
            return jsonify({"success": False, "message": "Token tidak valid"}), 401
        lesson = repo.get_lesson_by_slug(db, lesson_name)
        if lesson is None:
            return jsonify({"success": False, "message": "Lesson tidak dikenal"}), 404

        has_exercise, has_quiz = get_lesson_components(lesson_name)

        if progress_type == "exercise":
            repo.set_exercise_passed(db, user_id=user.id, lesson_id=lesson.id)
            repo.recompute_progress(
                db,
                user_id=user.id,
                lesson_id=lesson.id,
                has_exercise=has_exercise,
                has_quiz=has_quiz,
                exercise_weight=LESSON_EXERCISE_WEIGHT,
                quiz_weight=LESSON_QUIZ_WEIGHT,
                done_min_percent=LESSON_DONE_MIN_PERCENT,
            )
            db.commit()
            return jsonify({"success": True, "idempotent": False})

        # ── progress_type == 'quiz' ── mirror submit_quiz_attempt ─────
        attempt_id = str(data.get("attempt_id") or "").strip()
        status = str(data.get("status") or "").strip()
        reason_raw = data.get("termination_reason")
        termination_reason = str(reason_raw).strip() if reason_raw not in (None, "") else None
        score = str(data.get("score") or "").strip()
        visibility_count = data.get("visibility_event_count", 0)
        user_agent = (request.headers.get("User-Agent") or "")[:MAX_AGENT_LENGTH]

        if not is_canonical_uuid(attempt_id):
            return jsonify({"success": False, "message": "attempt_id harus UUID canonical"}), 400
        if status not in ("submitted", "terminated"):
            return jsonify({"success": False, "message": "status harus submitted atau terminated"}), 400

        if termination_reason is None:
            if status != "submitted":
                return jsonify(
                    {"success": False, "message": "terminated wajib memiliki termination_reason"}
                ), 400
        else:
            if status != "terminated":
                return jsonify(
                    {
                        "success": False,
                        "message": "hanya status terminated yang boleh memiliki termination_reason",
                    }
                ), 400
            if termination_reason not in ALLOWED_REASONS:
                return jsonify(
                    {"success": False, "message": "termination_reason tidak dikenal"}
                ), 400
            if termination_reason == "focus_lost" and status != "terminated":
                return jsonify(
                    {"success": False, "message": "focus_lost wajib berstatus terminated"}
                ), 400

        if not score or len(score) > MAX_SCORE_LENGTH:
            return jsonify({"success": False, "message": "format skor tidak valid"}), 400
        try:
            state, earned, total = parse_progress_status(score)
        except ValueError:
            return jsonify({"success": False, "message": "format skor tidak dikenal"}), 400
        if state == "not_started":
            return jsonify({"success": False, "message": "skor tidak boleh not_started"}), 400

        try:
            occurred_at = _parse_ts(data.get("occurred_at"), required=True)
            started_at = _parse_ts(data.get("started_at"), required=False) or occurred_at
        except ValueError:
            return jsonify({"success": False, "message": "timestamp tidak valid"}), 400

        if (
            not isinstance(visibility_count, int)
            or isinstance(visibility_count, bool)
            or visibility_count < 0
            or visibility_count > 1000
        ):
            return jsonify({"success": False, "message": "visibility_event_count tidak valid"}), 400

        # answers: ringkasan per-soal [{question_id, selected_option_id, is_correct, category}]
        answers_raw = data.get("answers")
        answers_json = None
        if answers_raw is not None:
            if not isinstance(answers_raw, list):
                return jsonify({"success": False, "message": "answers harus berupa list"}), 400
            try:
                answers_json = json.dumps(answers_raw)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "answers tidak dapat diserialisasi"}), 400

        try:
            attempt, created = repo.finalize_quiz_attempt(
                db,
                attempt_id=attempt_id,
                user_id=user.id,
                lesson_id=lesson.id,
                status=status,
                termination_reason=termination_reason,
                score_earned=earned,
                score_total=total,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                visibility_event_count=visibility_count,
                user_agent=user_agent,
                answers_json=answers_json,
            )
        except ValueError as exc:
            db.rollback()
            return jsonify({"success": False, "message": str(exc)}), 409

        # Update progress HANYA untuk attempt yang benar-benar baru — retry
        # idempotent tidak menulis ulang progress maupun row attempt.
        if created:
            repo.set_quiz_score(
                db,
                user_id=user.id,
                lesson_id=lesson.id,
                quiz_earned=earned,
                quiz_total=total,
            )
            repo.recompute_progress(
                db,
                user_id=user.id,
                lesson_id=lesson.id,
                has_exercise=has_exercise,
                has_quiz=has_quiz,
                exercise_weight=LESSON_EXERCISE_WEIGHT,
                quiz_weight=LESSON_QUIZ_WEIGHT,
                done_min_percent=LESSON_DONE_MIN_PERCENT,
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(
            {"success": False, "message": "Attempt konflik — satu percobaan per kuis"}
        ), 409
    except Exception:  # noqa: BLE001 — jangan bocorkan exception internal
        db.rollback()
        logger.exception("lesson-progress submit gagal")
        return jsonify({"success": False, "message": "Gagal menyimpan progress"}), 500
    finally:
        db.close()

    logger.info(
        "Lesson progress (quiz) disimpan: user_id=%s lesson=%s status=%s created=%s",
        user.id, lesson_name, status, created,
    )
    return jsonify(
        {
            "success": True,
            "idempotent": not created,
            "attempt_id": attempt.id,
        }
    )


@lesson_progress_bp.route("/lesson-progress/<lesson_name>", methods=["GET"])
def get_lesson_progress(lesson_name: str):
    """Ambil progress lesson + audit attempt kuis (review-after-refresh).

    Auth: student_token via query param `token` (siswa hanya lihat miliknya).
    Response: state, exercise_passed, quiz_score_*, composite_percent, serta
    field audit attempt (attempt_id, status, termination_reason, attempt_score,
    started_at, finished_at, answers).
    """
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"success": False, "message": "Token wajib"}), 400
    if SessionLocal is None:
        return jsonify({"success": False, "message": "PostgreSQL tidak aktif"}), 503

    db = SessionLocal()
    try:
        user = repo.get_user_by_token(db, token)
        if user is None:
            return jsonify({"success": False, "message": "Token tidak valid"}), 401
        lesson = repo.get_lesson_by_slug(db, lesson_name)
        if lesson is None:
            return jsonify({"success": False, "message": "Lesson tidak dikenal"}), 404

        progress = repo.get_progress(db, user_id=user.id, lesson_id=lesson.id)
        attempt = repo.get_quiz_attempt_for_user_lesson(
            db, user_id=user.id, lesson_id=lesson.id
        )

        try:
            answers = json.loads(attempt.answers_json) if attempt and attempt.answers_json else []
        except (json.JSONDecodeError, TypeError):
            answers = []

        composite_percent = None
        if progress is not None and progress.composite_percent is not None:
            composite_percent = round(progress.composite_percent, 2)

        attempt_score = None
        if attempt is not None and attempt.score_earned is not None and attempt.score_total is not None:
            attempt_score = f"{attempt.score_earned}/{attempt.score_total}"

        return jsonify(
            {
                "success": True,
                "lesson_name": lesson_name,
                "state": progress.state if progress else "not_started",
                "exercise_passed": progress.exercise_passed if progress else None,
                "quiz_score_earned": progress.quiz_score_earned if progress else None,
                "quiz_score_total": progress.quiz_score_total if progress else None,
                "composite_percent": composite_percent,
                "attempt_id": attempt.id if attempt else None,
                "attempt_status": attempt.status if attempt else None,
                "termination_reason": attempt.termination_reason if attempt else None,
                "attempt_score": attempt_score,
                "attempt_started_at": attempt.started_at.isoformat() if attempt and attempt.started_at else None,
                "attempt_finished_at": attempt.finished_at.isoformat() if attempt and attempt.finished_at else None,
                "answers": answers,
            }
        )
    except Exception:  # noqa: BLE001
        logger.exception("get_lesson_progress gagal")
        return jsonify({"success": False, "message": "Gagal mengambil progress"}), 500
    finally:
        db.close()
