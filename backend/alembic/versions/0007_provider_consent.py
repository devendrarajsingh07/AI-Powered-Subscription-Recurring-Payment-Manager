"""A new recipient requires fresh explicit live-provider consent."""

from alembic import op

revision = "0007_provider_consent"
down_revision = "0006_demo"
branch_labels = depends_on = None


def upgrade():
    op.execute("UPDATE users SET live_opt_in = false")


def downgrade():
    # Revoked consent cannot safely be inferred or restored on a downgrade.
    pass
