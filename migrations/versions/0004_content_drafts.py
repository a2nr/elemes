"""content_drafts: buffer editor konten sebelum publish ke file .md

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "author_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("target_path", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_mtime", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft','published')", name="ck_content_drafts_status"
        ),
    )
    op.create_index("ix_content_drafts_author_id", "content_drafts", ["author_id"])
    # Satu draft aktif per target_path — cegah dua sesi bentrok tanpa sadar.
    op.execute(
        "CREATE UNIQUE INDEX uq_content_drafts_active_path "
        "ON content_drafts (target_path) WHERE status = 'draft'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_content_drafts_active_path")
    op.drop_index("ix_content_drafts_author_id", table_name="content_drafts")
    op.drop_table("content_drafts")
