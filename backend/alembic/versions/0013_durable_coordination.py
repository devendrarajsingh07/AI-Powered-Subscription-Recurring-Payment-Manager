"""Encrypted owned jobs and shared chat leases. Additive; no runtime schema creation."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_durable_coordination"
down_revision = "0012_public_demo"
branch_labels = depends_on = None


def upgrade():
    op.create_unique_constraint("uq_preview_owner", "statement_previews", ["id", "user_id"])
    op.create_table(
        "durable_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), unique=True),
        sa.Column("preview_id", postgresql.UUID(as_uuid=True), unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("encrypted_input", sa.LargeBinary()),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_code", sa.String(32)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["upload_id", "user_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["preview_id", "user_id"],
            ["statement_previews.id", "statement_previews.user_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("num_nonnulls(upload_id, preview_id) = 1", name="ck_job_subject"),
        sa.CheckConstraint("kind IN ('csv', 'extraction')", name="ck_job_kind"),
        sa.CheckConstraint(
            "status IN ('staging', 'queued', 'running', 'done', 'dead_letter', 'cancelled')",
            name="ck_job_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5", name="ck_job_attempts"
        ),
        sa.CheckConstraint("octet_length(encrypted_input) <= 14680064", name="ck_job_input_size"),
    )
    op.create_index("ix_durable_jobs_user_id", "durable_jobs", ["user_id"])
    op.create_index("ix_durable_jobs_expires_at", "durable_jobs", ["expires_at"])
    op.create_index("ix_job_claim", "durable_jobs", ["status", "available_at", "lease_until"])
    op.create_table(
        "chat_leases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minute_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "minute_reset", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("daily_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("daily_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_chat_lease_user"),
    )
    op.create_index("ix_chat_leases_user_id", "chat_leases", ["user_id"])
    op.create_index("ix_chat_leases_expires_at", "chat_leases", ["expires_at"])


def downgrade():
    op.drop_table("chat_leases")
    op.drop_table("durable_jobs")
    op.drop_constraint("uq_preview_owner", "statement_previews", type_="unique")
