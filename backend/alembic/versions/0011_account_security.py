"""Revocable account sessions, hashed action tokens and account-level throttling."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0011_account_security"
down_revision = "0010_shared_auth_limits"
branch_labels = depends_on = None


def owned():
    return [
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]


def expiry():
    return sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_table(
        "auth_sessions",
        *owned(),
        expiry(),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("id", "user_id", name="uq_auth_session_owner"),
    )
    op.create_table(
        "refresh_tokens",
        *owned(),
        expiry(),
        sa.Column("session_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["session_id", "user_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "account_tokens",
        *owned(),
        expiry(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "login_backoffs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("key_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        expiry(),
    )
    for table in ("auth_sessions", "refresh_tokens", "account_tokens", "login_backoffs"):
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_index(f"ix_{table}_expires_at", table, ["expires_at"])


def downgrade():
    for table in ("login_backoffs", "account_tokens", "refresh_tokens", "auth_sessions"):
        op.drop_table(table)
    op.drop_column("users", "auth_version")
    op.drop_column("users", "email_verified_at")
