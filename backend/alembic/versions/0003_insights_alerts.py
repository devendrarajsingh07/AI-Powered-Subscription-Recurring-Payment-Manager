"""Stable insight decisions and renewal-cycle delivery identity."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0003_insights_alerts"
down_revision = "0002_domain"
branch_labels = depends_on = None


def upgrade():
    for name, type_, default in (
        ("subject_key", sa.String(100), "''"),
        ("facts_hash", sa.String(64), "'legacy'"),
        ("facts", pg.JSONB(), "'{}'::jsonb"),
        ("decisions", pg.JSONB(), "'{}'::jsonb"),
    ):
        op.add_column(
            "recommendations",
            sa.Column(name, type_, nullable=False, server_default=sa.text(default)),
        )
        op.alter_column("recommendations", name, server_default=None)
    op.execute("UPDATE recommendations SET subject_key = 'legacy:' || id::text")
    op.add_column("recommendations", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.add_column(
        "recommendations",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column("recommendations", sa.Column("extra_monthly_cost", sa.Numeric(24, 2)))
    op.add_column("recommendations", sa.Column("percent_change", sa.Numeric(20, 2)))
    op.alter_column("recommendations", "est_monthly_saving", type_=sa.Numeric(24, 2), nullable=True)
    op.drop_constraint("recommendation_status", "recommendations", type_="check")
    op.create_check_constraint(
        "recommendation_status",
        "recommendations",
        "status IN ('open','accepted','dismissed','resolved')",
    )
    op.create_unique_constraint(
        "uq_recommendation_subject", "recommendations", ["user_id", "type", "subject_key"]
    )
    op.add_column(
        "alerts", sa.Column("event_key", sa.String(100), nullable=False, server_default="")
    )
    op.alter_column("alerts", "event_key", server_default=None)
    op.execute("UPDATE alerts SET event_key = 'legacy:' || id::text")
    op.execute(
        "UPDATE alerts SET event_key = 'budget:' || to_char(send_on, 'YYYY-MM') "
        "WHERE kind = 'budget'"
    )
    op.add_column("alerts", sa.Column("recipient", sa.String(254)))
    op.add_column(
        "alerts", sa.Column("status", sa.String(8), nullable=False, server_default="pending")
    )
    op.alter_column("alerts", "status", server_default=None)
    op.execute("UPDATE alerts SET status = 'sent' WHERE sent_at IS NOT NULL")
    op.create_check_constraint(
        "alert_status", "alerts", "status IN ('pending','retrying','sent','skipped','failed')"
    )
    op.add_column(
        "alerts", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.alter_column("alerts", "attempt_count", server_default=None)
    for name in ("last_attempt_at", "next_attempt_at"):
        op.add_column("alerts", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("alerts", sa.Column("safe_failure_reason", sa.String(255)))
    op.drop_index("uq_alert_identity", table_name="alerts")
    op.create_unique_constraint("uq_alert_event", "alerts", ["user_id", "kind", "event_key"])
    op.create_index(
        "uq_alert_budget_month",
        "alerts",
        ["user_id", "send_on"],
        unique=True,
        postgresql_where=sa.text("kind = 'budget'"),
    )


def downgrade():
    op.drop_index("uq_alert_budget_month", table_name="alerts")
    op.drop_constraint("uq_alert_event", "alerts", type_="unique")
    op.drop_constraint("alert_status", "alerts", type_="check")
    # Legacy identity cannot represent two cycles with the same mutable send date.
    # Refuse an unrepresentable downgrade rather than silently deleting delivery history.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM alerts GROUP BY user_id, kind, "
        "subscription_id, send_on HAVING count(*) > 1) THEN RAISE EXCEPTION "
        "'Downgrade cannot represent multiple renewal cycles sharing a send date'; END IF; END $$"
    )
    op.create_index(
        "uq_alert_identity",
        "alerts",
        ["user_id", "kind", "subscription_id", "send_on"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )
    for name in (
        "safe_failure_reason",
        "next_attempt_at",
        "last_attempt_at",
        "attempt_count",
        "status",
        "recipient",
        "event_key",
    ):
        op.drop_column("alerts", name)
    op.drop_constraint("uq_recommendation_subject", "recommendations", type_="unique")
    op.drop_constraint("recommendation_status", "recommendations", type_="check")
    op.execute("UPDATE recommendations SET status='dismissed' WHERE status='resolved'")
    op.create_check_constraint(
        "recommendation_status", "recommendations", "status IN ('open','accepted','dismissed')"
    )
    op.execute("UPDATE recommendations SET est_monthly_saving=0 WHERE est_monthly_saving IS NULL")
    op.alter_column(
        "recommendations", "est_monthly_saving", type_=sa.Numeric(12, 2), nullable=False
    )
    for name in (
        "percent_change",
        "extra_monthly_cost",
        "updated_at",
        "accepted_at",
        "decisions",
        "facts",
        "facts_hash",
        "subject_key",
    ):
        op.drop_column("recommendations", name)
