"""
Model SQLAlchemy 2.0 — source of truth schema migrasi CSV→PostgreSQL.

users           — identitas + role eksplisit (teacher/student)
access_tokens   — hash token (HMAC-SHA256 + pepper), bukan plaintext
lessons         — registry materi (konten tetap Markdown; DB hanya metadata)
student_progress— status per (user, lesson), unik; skor terstruktur utk state 'scored'
quiz_attempts   — audit one-attempt kuis (status/termination reason anti-cheat)
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.database import Base


def _uuid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('teacher','student')", name="ck_users_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tokens: Mapped[list["AccessToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    progress: Mapped[list["StudentProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AccessToken(Base):
    __tablename__ = "access_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_access_tokens_token_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="tokens")


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("slug", name="uq_lessons_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    progress: Mapped[list["StudentProgress"]] = relationship(back_populates="lesson")
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(back_populates="lesson")


class QuizAttempt(Base):
    """Satu attempt kuis per (user, lesson) — audit anti-cheat terpisah dari skor.

    - id dibuat klien saat startQuiz (UUID canonical) untuk korelasi/idempotency
      beacon & fetch; row dibuat pada saat finalisasi (sekali).
    - `status`: submitted (selesai normal) atau terminated (exit dini/penalti).
    - `termination_reason` hanya untuk terminated: focus_lost, spa_navigation,
      page_unload, user_exit, completed (reserved).
    - unique (user_id, lesson_id) = one-attempt policy.
    """

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_quiz_attempts_user_lesson"),
        CheckConstraint(
            "status IN ('submitted','terminated')", name="ck_quiz_attempts_status"
        ),
        CheckConstraint(
            "termination_reason IS NULL OR termination_reason IN "
            "('focus_lost','spa_navigation','page_unload','user_exit','completed')",
            name="ck_quiz_attempts_reason",
        ),
        CheckConstraint(
            "(status = 'terminated' AND termination_reason IS NOT NULL) OR "
            "(status = 'submitted' AND termination_reason IS NULL)",
            name="ck_quiz_attempts_status_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    termination_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    score_earned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    visibility_event_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Diagnosis device/browser saja — bukan dasar hukuman tambahan.
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Ringkasan per-soal (question_id -> selected_option_id, is_correct, category).
    # Digunakan frontend untuk render review-after-refresh + breakdown kategori;
    # tidak memengaruui skor resmi (evaluasi saja, lihat quiz-session.ts).
    answers_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="quiz_attempts")
    lesson: Mapped["Lesson"] = relationship(back_populates="quiz_attempts")


class StudentProgress(Base):
    __tablename__ = "student_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_student_progress_user_lesson"),
        CheckConstraint(
            "state IN ('not_started','completed','scored')", name="ck_student_progress_state"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started", server_default="not_started"
    )
    score_earned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="progress")
    lesson: Mapped["Lesson"] = relationship(back_populates="progress")


class ContentDraft(Base):
    """Buffer editor konten — isi mentah .md sebelum di-publish ke filesystem.

    `target_path` relatif terhadap CONTENT_DIR (mis. "dasar/hello_world.md").
    `base_mtime` = mtime file di disk saat draft dibuat/di-refresh dari file;
    dipakai deteksi konflik saat publish (file berubah di luar webapp, mis.
    lewat git pull manual, sejak draft dibuat). Partial unique index (lihat
    migrasi) menjamin cuma 1 draft aktif per file.
    """

    __tablename__ = "content_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_path: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_mtime: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
