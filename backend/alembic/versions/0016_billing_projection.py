"""Persist billing projections independently of transient price-increase notices.

Additive nullable column; downgrade removes it without changing charge history or decisions.
Backfill is frozen here so later changes to application services do not alter old migrations.
"""

from bisect import insort
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision = "0016_billing_projection"
down_revision = "0015_email_lifecycle"
branch_labels = depends_on = None


def upgrade():
    op.add_column("subscriptions", sa.Column("billing_amount", sa.Numeric(12, 2)))
    db = op.get_bind()
    owners = db.execute(sa.text("SELECT id, user_id, cadence FROM subscriptions")).all()
    for subscription_id, user_id, cadence in owners:
        amounts = db.execute(
            sa.text(
                "SELECT t.amount FROM subscription_charges c JOIN transactions t "
                "ON t.id = c.transaction_id AND t.user_id = c.user_id "
                "WHERE c.subscription_id = :id AND c.user_id = :user_id "
                "ORDER BY t.date, t.amount, t.raw_description"
            ),
            {"id": subscription_id, "user_id": user_id},
        ).scalars()
        previous, established, latest = [], False, None
        increased, increase_streak = False, 0
        minimum = 2 if cadence == "yearly" else 3
        for amount in amounts:
            increased = False
            if len(previous) >= minimum - 1:
                middle = len(previous) // 2
                median = (
                    previous[middle]
                    if len(previous) % 2
                    else (previous[middle - 1] + previous[middle]) / 2
                )
                increased = amount > median * Decimal("1.05")
            increase_streak = increase_streak + 1 if increased else 0
            # Repeated higher charges establish a price even with FX/usage variation.
            # A single spike does not permanently replace the averaging policy.
            established |= increase_streak >= 2
            insort(previous, amount)
            latest = amount
        if established or increased:
            db.execute(
                sa.text(
                    "UPDATE subscriptions SET billing_amount = :amount "
                    "WHERE id = :id AND user_id = :user_id"
                ),
                {"amount": latest, "id": subscription_id, "user_id": user_id},
            )


def downgrade():
    op.drop_column("subscriptions", "billing_amount")
