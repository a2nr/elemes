"""quiz_attempts: kolom is_preview + one-attempt policy hanya untuk attempt real

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "is_preview", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.drop_constraint(
        "uq_quiz_attempts_user_lesson", "quiz_attempts", type_="unique"
    )
    op.create_index(
        "uq_quiz_attempts_user_lesson_real",
        "quiz_attempts",
        ["user_id", "lesson_id"],
        unique=True,
        postgresql_where=sa.text("is_preview = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_quiz_attempts_user_lesson_real", table_name="quiz_attempts")
    # CATATAN: downgrade gagal bila ada >1 row untuk (user_id, lesson_id) yang
    # sama (mis. preview + real, atau sisa preview lama). Jalankan dulu:
    #   DELETE FROM quiz_attempts WHERE is_preview = true;
    op.create_unique_constraint(
        "uq_quiz_attempts_user_lesson", "quiz_attempts", ["user_id", "lesson_id"]
    )
    op.drop_column("quiz_attempts", "is_preview")
