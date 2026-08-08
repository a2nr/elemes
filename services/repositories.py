"""
Repository layer — seluruh akses data PostgreSQL lewat SQLAlchemy session.

Dipanggil oleh service/facade; session & commit dikelola pemanggil
(mis. get_db() per request). Kontrak perilaku dijamin test integrasi
terhadap PostgreSQL nyata (test_repositories.py) dan suite kontrak
(test_token_service_contract.py) yang sama untuk kedua backend.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.models import AccessToken, Lesson, StudentProgress, User
from services.token_hashing import hash_token


def _uuid() -> str:
    return str(uuid4())


# ── users & access_tokens ─────────────────────────────────────────


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_user_by_token(db: Session, raw_token: str) -> User | None:
    """Lookup user dari token mentah. Update last_used_at (tanpa commit)."""
    digest = hash_token(raw_token)
    token = db.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == digest,
            AccessToken.revoked_at.is_(None),
        )
    )
    if token is None:
        return None
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    token.last_used_at = datetime.now(timezone.utc)
    return user


def find_user_by_raw_token(db: Session, raw_token: str) -> User | None:
    """Lookup user dari token mentah TANPA side-effect (untuk importer/verifikasi)."""
    digest = hash_token(raw_token)
    token = db.scalar(select(AccessToken).where(AccessToken.token_hash == digest))
    if token is None:
        return None
    return db.get(User, token.user_id)


def create_user(db: Session, *, display_name: str, role: str, is_active: bool = True) -> User:
    user = User(display_name=display_name, role=role, is_active=is_active)
    db.add(user)
    db.flush()
    return user


def create_access_token(
    db: Session, *, user_id: str, raw_token: str
) -> AccessToken:
    token = AccessToken(id=_uuid(), user_id=user_id, token_hash=hash_token(raw_token))
    db.add(token)
    db.flush()
    return token


def revoke_token(db: Session, *, user_id: str, raw_token: str) -> bool:
    digest = hash_token(raw_token)
    token = db.scalar(
        select(AccessToken).where(
            AccessToken.token_hash == digest,
            AccessToken.user_id == user_id,
        )
    )
    if token is None:
        return False
    token.revoked_at = datetime.now(timezone.utc)
    return True


def revoke_all_tokens(db: Session, *, user_id: str) -> int:
    tokens = list(
        db.scalars(
            select(AccessToken).where(
                AccessToken.user_id == user_id,
                AccessToken.revoked_at.is_(None),
            )
        )
    )
    for token in tokens:
        token.revoked_at = datetime.now(timezone.utc)
    return len(tokens)


# ── lessons ────────────────────────────────────────────────────────


def list_lessons(db: Session) -> list[Lesson]:
    return list(db.scalars(select(Lesson).order_by(Lesson.order_index, Lesson.slug)))


def list_active_lessons(db: Session) -> list[Lesson]:
    return list(
        db.scalars(select(Lesson).where(Lesson.is_active.is_(True)).order_by(Lesson.order_index, Lesson.slug))
    )


def get_lesson_by_slug(db: Session, slug: str) -> Lesson | None:
    return db.scalar(select(Lesson).where(Lesson.slug == slug))


def upsert_lesson(db: Session, *, slug: str, title: str, order_index: int) -> Lesson:
    lesson = get_lesson_by_slug(db, slug)
    if lesson is None:
        lesson = Lesson(slug=slug, title=title, order_index=order_index)
        db.add(lesson)
    else:
        lesson.title = title
        lesson.order_index = order_index
        lesson.is_active = True
    db.flush()
    return lesson


def deactivate_missing_lessons(db: Session, active_slugs: set[str]) -> int:
    """Lesson yang tidak ada lagi di Markdown → is_active=False (bukan dihapus)."""
    lessons = list(db.scalars(select(Lesson).where(Lesson.is_active.is_(True))))
    changed = 0
    for lesson in lessons:
        if lesson.slug not in active_slugs:
            lesson.is_active = False
            changed += 1
    return changed


# ── student_progress ───────────────────────────────────────────────


def get_progress(db: Session, *, user_id: str, lesson_id: str) -> StudentProgress | None:
    return db.scalar(
        select(StudentProgress).where(
            StudentProgress.user_id == user_id,
            StudentProgress.lesson_id == lesson_id,
        )
    )


def list_progress_for_user(db: Session, *, user_id: str) -> list[StudentProgress]:
    return list(
        db.scalars(select(StudentProgress).where(StudentProgress.user_id == user_id))
    )


def set_progress(
    db: Session,
    *,
    user_id: str,
    lesson_id: str,
    state: str,
    score_earned: int | None = None,
    score_total: int | None = None,
) -> StudentProgress | None:
    """Upsert progress (sparse model).

    - state='not_started' → HAPUS row bila ada; tidak ada row = not_started.
    - state='scored' wajib membawa score_earned & score_total.
    """
    if state == "not_started":
        progress = get_progress(db, user_id=user_id, lesson_id=lesson_id)
        if progress is not None:
            db.delete(progress)
            db.flush()
        return None
    if state == "scored":
        if score_earned is None or score_total is None:
            raise ValueError("state='scored' memerlukan score_earned & score_total")
    else:
        score_earned = None
        score_total = None

    progress = get_progress(db, user_id=user_id, lesson_id=lesson_id)
    if progress is None:
        progress = StudentProgress(
            id=_uuid(),
            user_id=user_id,
            lesson_id=lesson_id,
            state=state,
            score_earned=score_earned,
            score_total=score_total,
        )
        db.add(progress)
    else:
        progress.state = state
        progress.score_earned = score_earned
        progress.score_total = score_total
    db.flush()
    return progress


def count_completed_lessons(db: Session, *, user_id: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(StudentProgress)
            .where(
                StudentProgress.user_id == user_id,
                StudentProgress.state.in_(("completed", "scored")),
            )
        )
        or 0
    )
