"""Demo provenance and reversible demo defaults."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0006_demo"
down_revision = "0005_chat"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "uploads", sa.Column("source", sa.String(16), nullable=False, server_default="upload")
    )
    op.add_column("uploads", sa.Column("demo_as_of", sa.Date()))
    op.add_column("uploads", sa.Column("demo_defaults", pg.JSONB()))


def downgrade():
    op.drop_column("uploads", "demo_defaults")
    op.drop_column("uploads", "demo_as_of")
    op.drop_column("uploads", "source")
