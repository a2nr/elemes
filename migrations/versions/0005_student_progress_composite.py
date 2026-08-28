"""student_progress composite score columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-28

Menambah kolom composite evaluation ke student_progress:
- exercise_passed (Boolean)
- quiz_score_earned (Integer)
- quiz_score_total (Integer)
- composite_percent (Float)

Backfill data legacy:
- state='completed' → exercise_passed=true
- state='scored'    → quiz_score_earned=score_earned, quiz_score_total=score_total
Legacy 'completed'/'scored' diubah ke 'in_progress' (akan di-recompute jadi
'done' oleh logika composite di backend). Constraint ck_student_progress_state
diperluas dari 3-state menjadi 5-state ('not_started','in_progress',
'completed','scored','done').
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_progress",
        sa.Column("exercise_passed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "student_progress",
        sa.Column("quiz_score_earned", sa.Integer(), nullable=True),
    )
    op.add_column(
        "student_progress",
        sa.Column("quiz_score_total", sa.Integer(), nullable=True),
    )
    op.add_column(
        "student_progress",
        sa.Column("composite_percent", sa.Float(), nullable=True),
    )

    # Backfill: completed → exercise lulus; scored → ambil skor kuis lama.
    op.execute(
        "UPDATE student_progress SET exercise_passed = true "
        "WHERE state = 'completed'"
    )
    op.execute(
        "UPDATE student_progress "
        "SET quiz_score_earned = score_earned, quiz_score_total = score_total "
        "WHERE state = 'scored'"
    )
    # Legacy 'completed'/'scored' belum punya composite → turunkan ke
    # 'in_progress' agar backend menghitung ulang jadi 'done'/'in_progress'.
    op.execute(
        "UPDATE student_progress SET state = 'in_progress' "
        "WHERE state IN ('completed', 'scored')"
    )

    # Perluas constraint state menjadi 5-state.
    op.drop_constraint(
        "ck_student_progress_state", "student_progress", type_="check"
    )
    op.create_check_constraint(
        "ck_student_progress_state",
        "student_progress",
        "state IN ('not_started','in_progress','completed','scored','done')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_student_progress_state", "student_progress", type_="check"
    )
    op.create_check_constraint(
        "ck_student_progress_state",
        "student_progress",
        "state IN ('not_started','completed','scored')",
    )
    op.drop_column("student_progress", "composite_percent")
    op.drop_column("student_progress", "quiz_score_total")
    op.drop_column("student_progress", "quiz_score_earned")
    op.drop_column("student_progress", "exercise_passed")
