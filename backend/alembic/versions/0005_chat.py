"""Consent, scoped conversations and cached suggestion attempts."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0005_chat"
down_revision = "0004_delivery_snapshot"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("live_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("chat_messages", sa.Column("conversation_id", pg.UUID(), nullable=True))
    op.execute("UPDATE chat_messages SET conversation_id=id")
    op.alter_column("chat_messages", "conversation_id", nullable=False)
    op.add_column("chat_messages", sa.Column("verified", sa.Boolean()))
    op.add_column(
        "merchant_categories",
        sa.Column(
            "suggestion_attempted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade():
    op.drop_column("merchant_categories", "suggestion_attempted")
    op.drop_column("chat_messages", "verified")
    op.drop_column("chat_messages", "conversation_id")
    op.drop_column("users", "live_opt_in")
