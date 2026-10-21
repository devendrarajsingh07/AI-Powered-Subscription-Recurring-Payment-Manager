"""Global live-AI kill switch and daily caps. Additive; system-wide, content-free counters."""

import sqlalchemy as sa

from alembic import op

revision = "0014_llm_controls"
down_revision = "0013_durable_coordination"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "llm_switch",
        sa.Column("id", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("offline_forced", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name="ck_llm_switch_singleton"),
    )
    op.create_table(
        "llm_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fallbacks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade():
    op.drop_table("llm_usage")
    op.drop_table("llm_switch")
