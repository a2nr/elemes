"""quiz_attempts: audit one-attempt kuis (status + termination reason)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("termination_reason", sa.String(30), nullable=True),
        sa.Column("score_earned", sa.Integer(), nullable=True),
        sa.Column("score_total", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "visibility_event_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.CheckConstraint(
            "status IN ('submitted','terminated')", name="ck_quiz_attempts_status"
        ),
        sa.CheckConstraint(
            "termination_reason IS NULL OR termination_reason IN "
            "('focus_lost','spa_navigation','page_unload','user_exit','completed')",
            name="ck_quiz_attempts_reason",
        ),
        sa.CheckConstraint(
            "(status = 'terminated' AND termination_reason IS NOT NULL) OR "
            "(status = 'submitted' AND termination_reason IS NULL)",
            name="ck_quiz_attempts_status_reason",
        ),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_quiz_attempts_user_lesson"),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_finished_at", "quiz_attempts", ["finished_at"])


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_finished_at", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
