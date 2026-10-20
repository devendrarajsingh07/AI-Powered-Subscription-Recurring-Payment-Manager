"""Hashed single-use invitations and content-free security audit events."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0009_beta_foundation"
down_revision = "0008_statements"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "registration_invites",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("email_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_registration_invites_user_id", "registration_invites", ["user_id"])
    op.create_index("ix_registration_invites_expires_at", "registration_invites", ["expires_at"])
    op.create_table(
        "security_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])


def downgrade():
    op.drop_table("security_events")
    op.drop_table("registration_invites")
