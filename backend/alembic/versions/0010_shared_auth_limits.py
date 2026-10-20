"""Shared anonymous/scoped fixed-window abuse counters."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0010_shared_auth_limits"
down_revision = "0009_beta_foundation"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("key_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_buckets_user_id", "rate_limit_buckets", ["user_id"])
    op.create_index("ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"])


def downgrade():
    op.drop_table("rate_limit_buckets")
