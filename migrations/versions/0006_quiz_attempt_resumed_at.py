"""quiz_attempts: resumed_at — izin guru melanjutkan attempt terminated

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-08

Kolom `resumed_at` menandai attempt terminated yang diizinkan guru untuk
dilanjutkan siswa (kendala tak terduga, mis. false-positive focus loss,
browser crash). NULL = attempt normal (one-attempt gate aktif). Terisi =
gate terbuka dan siswa melanjutkan dari jawaban tersimpan; kolom di-clear
saat attempt difinalisasi ulang agar one-attempt normal berlaku lagi.
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_attempts",
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quiz_attempts", "resumed_at")
