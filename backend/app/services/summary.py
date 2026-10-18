"""Subscription projections and actual linked-charge trends. Decimal arithmetic only."""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app import repositories as repo

ZERO = Decimal("0")
CENT = Decimal("0.01")
FACTORS = {
    "weekly": Decimal(52),
    "monthly": Decimal(12),
    "quarterly": Decimal(4),
    "yearly": Decimal(1),
}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def equivalents(amount: Decimal, cadence: str) -> tuple[Decimal, Decimal]:
    if not isinstance(amount, Decimal):
        raise TypeError("Amounts must be Decimal")
    annual = amount * FACTORS[cadence]
    return annual / 12, annual


def summarize(db, user_id, *, period: str):
    subscriptions = repo.active_subscriptions(db, user_id)
    grouped = defaultdict(lambda: [ZERO, ZERO, 0])
    for sub in subscriptions:
        month, year = equivalents(sub.avg_amount, sub.cadence)
        values = grouped[sub.kind, sub.category]
        values[0] += month
        values[1] += year
        values[2] += 1
    kinds = {}
    for kind in ("subscription", "fixed_bill"):
        values = [value for (item_kind, _), value in grouped.items() if item_kind == kind]
        kinds[kind] = {
            "monthly_equivalent": money(sum((v[0] for v in values), ZERO)),
            "yearly_total": money(sum((v[1] for v in values), ZERO)),
            "count": sum(v[2] for v in values),
        }
    # Aggregate unrounded values, then round once to avoid per-product rounding error.
    monthly = money(sum((value[0] for value in grouped.values()), ZERO))
    yearly = money(sum((value[1] for value in grouped.values()), ZERO))
    return dict(
        period=period,
        currency="INR",
        monthly_equivalent=monthly,
        yearly_total=yearly,
        period_total=monthly if period == "month" else yearly,
        active_count=len(subscriptions),
        subscriptions=kinds["subscription"],
        fixed_bills=kinds["fixed_bill"],
        categories=[
            dict(
                kind=kind,
                category=category,
                monthly_equivalent=money(values[0]),
                yearly_total=money(values[1]),
                count=values[2],
            )
            for (kind, category), values in sorted(grouped.items())
        ],
    )


def trend(db, user_id, *, months: int, as_of: date):
    first_index = as_of.year * 12 + as_of.month - months
    first_year, first_month = divmod(first_index, 12)
    since = date(first_year, first_month + 1, 1)
    # Kind is attached by persisted charge links, even if the user later cancelled/dismissed.
    from app.models import Subscription

    kinds = {}
    for sub in repo.list_owned(db, user_id, Subscription, limit=None):
        for tx in repo.subscription_charges(db, user_id, sub.id):
            kinds[tx.id] = sub.kind
    totals = defaultdict(lambda: {"subscriptions": ZERO, "fixed_bills": ZERO})
    for tx in repo.linked_transactions(db, user_id, since=since, until=as_of):
        label = "fixed_bills" if kinds.get(tx.id) == "fixed_bill" else "subscriptions"
        totals[tx.date.strftime("%Y-%m")][label] += tx.amount
    points = []
    for i in range(months):
        year, month = divmod(first_index + i, 12)
        key = f"{year:04d}-{month + 1:02d}"
        values = totals[key]
        points.append(dict(month=key, **values, total=sum(values.values(), ZERO)))
    return dict(currency="INR", months=points)
