"""Email suppression, legal-draft acceptance record and content-restricted problem reports."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0015_email_lifecycle"
down_revision = "0014_llm_controls"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("alerts_suppressed_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("alerts_suppressed_reason", sa.String(16)))
    op.add_column("users", sa.Column("terms_version", sa.String(32)))
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_alert_suppression_reason",
        "users",
        "alerts_suppressed_reason IS NULL OR alerts_suppressed_reason IN "
        "('hard_bounce', 'complaint')",
    )
    op.create_table(
        "support_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "bug",
                "data_issue",
                "account",
                "other",
                name="support_category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_support_reports_user_id", "support_reports", ["user_id"])


def downgrade():
    op.drop_table("support_reports")
    op.drop_constraint("ck_alert_suppression_reason", "users", type_="check")
    for column in (
        "terms_accepted_at",
        "terms_version",
        "alerts_suppressed_reason",
        "alerts_suppressed_at",
    ):
        op.drop_column("users", column)
