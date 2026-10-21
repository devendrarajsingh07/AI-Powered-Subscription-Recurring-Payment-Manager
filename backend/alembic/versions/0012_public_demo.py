"""Disposable public demo accounts; additive only."""

import sqlalchemy as sa

from alembic import op

revision = "0012_public_demo"
down_revision = "0011_account_security"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("demo_expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_users_demo_expires_at", "users", ["demo_expires_at"])


def downgrade():
    op.drop_index("ix_users_demo_expires_at", table_name="users")
    op.drop_column("users", "demo_expires_at")
