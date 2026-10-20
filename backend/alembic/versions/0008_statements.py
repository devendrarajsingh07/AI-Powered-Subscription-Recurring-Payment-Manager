"""Ephemeral, scoped extraction previews and content-free quota counters."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0008_statements"
down_revision = "0007_provider_consent"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "uploads", sa.Column("source_type", sa.String(16), nullable=False, server_default="csv")
    )
    op.add_column(
        "uploads", sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_table(
        "statement_previews",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("stage", sa.String(64), nullable=False, server_default="queued"),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="pdf_text"),
        sa.Column("processed_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.String(255)),
        sa.Column("upload_id", pg.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["upload_id", "user_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_statement_previews_user_id", "statement_previews", ["user_id"])
    op.create_index("ix_statement_previews_expires_at", "statement_previews", ["expires_at"])
    op.create_table(
        "statement_usage",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flagged_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edited_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "day", name="uq_statement_usage_day"),
    )
    op.create_index("ix_statement_usage_user_id", "statement_usage", ["user_id"])


def downgrade():
    op.drop_table("statement_usage")
    op.drop_table("statement_previews")
    op.drop_column("uploads", "excluded_count")
    op.drop_column("uploads", "source_type")
