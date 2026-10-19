"""Persist delivery claims for recovery after an outbox publication crash."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0004_delivery_snapshot"
down_revision = "0003_insights_alerts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("alerts", sa.Column("delivery_snapshot", pg.JSONB(), nullable=True))


def downgrade():
    op.drop_column("alerts", "delivery_snapshot")
