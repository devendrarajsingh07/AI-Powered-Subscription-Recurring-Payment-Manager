"""Pure advisory rules; stable subjects and facts, no inference of usage or LLMs."""

import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from app.services.summary import ZERO, equivalents, money


@dataclass(frozen=True)
class InsightInput:
    id: str
    merchant: str
    category: str
    cadence: str
    avg_amount: Decimal
    kind: str = "subscription"
    status: str = "active"
    last_used_at: date | None = None
    price_previous_amount: Decimal | None = None
    price_new_amount: Decimal | None = None
    price_detected_on: date | None = None


@dataclass(frozen=True)
class Insight:
    type: str
    subject_key: str
    subscription_id: str | None
    message: str
    facts: dict
    est_monthly_saving: Decimal | None = None
    extra_monthly_cost: Decimal | None = None
    percent_change: Decimal | None = None

    @property
    def facts_hash(self):
        return hashlib.sha256(json.dumps(self.facts, sort_keys=True).encode()).hexdigest()


def rules(
    inputs: list[InsightInput],
    *,
    as_of: date,
    yearly_threshold=Decimal("12000"),
    share_threshold=Decimal("0.35"),
    unused_days=60,
) -> list[Insight]:
    if not isinstance(yearly_threshold, Decimal) or not isinstance(share_threshold, Decimal):
        raise TypeError('Rule thresholds must be Decimal')
    active = sorted(
        (s for s in inputs if s.status == "active" and s.kind == "subscription"), key=lambda s: s.id
    )
    monthly = {s.id: equivalents(s.avg_amount, s.cadence)[0] for s in active}
    total = sum(monthly.values(), ZERO)
    midpoint = median(monthly.values()) if active else ZERO
    groups = defaultdict(list)
    results = []

    def member(s):
        return dict(
            subscription_id=s.id,
            merchant=s.merchant,
            category=s.category,
            cadence=s.cadence,
            avg_amount=format(s.avg_amount, ".2f"),
            monthly_equivalent=format(money(monthly[s.id]), ".2f"),
        )

    for sub in active:
        if sub.category in ("music", "streaming", "cloud"):
            groups[sub.category].append(sub)
        annual = equivalents(sub.avg_amount, sub.cadence)[1]
        high_share = (
            total > ZERO
            and monthly[sub.id] / total > share_threshold
            and monthly[sub.id] > midpoint
        )
        if annual > yearly_threshold or high_share:
            results.append(
                Insight(
                    "high_cost",
                    sub.id,
                    sub.id,
                    f"You may want to review {sub.merchant}: its yearly-equivalent cost is "
                    f"INR {money(annual):.2f} and meets your high-cost review rule. "
                    "No saving is estimated.",
                    dict(
                        members=[member(sub)],
                        yearly_threshold=str(yearly_threshold),
                        share_threshold=str(share_threshold),
                    ),
                )
            )
        previous, new = sub.price_previous_amount, sub.price_new_amount
        if (
            previous is not None
            and new is not None
            and previous > ZERO
            and new > previous * Decimal("1.05")
        ):
            extra = money(equivalents(new - previous, sub.cadence)[0])
            percent = money((new - previous) / previous * 100)
            results.append(
                Insight(
                    "price_increase",
                    sub.id,
                    sub.id,
                    f"You may want to review {sub.merchant}: "
                    f"the latest charge rose by {percent:.2f}%. "
                    f"The extra monthly-equivalent cost is INR {extra:.2f}; this is not a saving.",
                    dict(
                        members=[member(sub)],
                        previous_amount=str(previous),
                        new_amount=str(new),
                        detected_on=sub.price_detected_on.isoformat()
                        if sub.price_detected_on
                        else None,
                    ),
                    extra_monthly_cost=extra,
                    percent_change=percent,
                )
            )
        if sub.last_used_at and (as_of - sub.last_used_at).days > unused_days:
            results.append(
                Insight(
                    "possibly_unused",
                    sub.id,
                    sub.id,
                    f"You may want to review {sub.merchant}: you marked its last use as "
                    f"{sub.last_used_at.isoformat()}. Payments alone do not show usage. "
                    "No saving is estimated.",
                    dict(
                        members=[member(sub)],
                        last_used_at=sub.last_used_at.isoformat(),
                        unused_days=unused_days,
                    ),
                )
            )
    for category, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        most_expensive = max(members, key=lambda s: (monthly[s.id], s.id))
        saving = money(sum((monthly[s.id] for s in members if s.id != most_expensive.id), ZERO))
        results.append(
            Insight(
                "duplicate",
                f"category:{category}",
                None,
                f"You may want to review overlap in {category}: "
                + ", ".join(s.merchant for s in members)
                + ". Keeping one most-expensive plan gives an estimated monthly saving "
                f"of INR {saving:.2f}. "
                "Your needs may differ; subscription statuses are unchanged.",
                dict(category=category, members=[member(s) for s in members]),
                est_monthly_saving=saving,
            )
        )
    return sorted(results, key=lambda item: (item.type, item.subject_key))


def regenerate(db, user_id, *, as_of):
    from app import models as m
    from app import repositories as repo
    from app.config import get_settings

    if repo.get_user(db, user_id, lock=True) is None:
        return []
    inputs = [
        InsightInput(
            **{
                name: str(sub.id) if name == "id" else getattr(sub, name)
                for name in InsightInput.__dataclass_fields__
            }
        )
        for sub in repo.active_subscriptions(db, user_id)
    ]
    settings = get_settings()
    candidates = rules(
        inputs,
        as_of=as_of,
        yearly_threshold=settings.high_cost_yearly_inr,
        share_threshold=settings.high_cost_share,
        unused_days=settings.unused_days,
    )
    existing = {
        (row.type, row.subject_key): row
        for row in repo.list_owned(db, user_id, m.Recommendation, limit=None)
    }
    seen = set()
    for item in candidates:
        key = (item.type, item.subject_key)
        seen.add(key)
        record = existing.get(key)
        if record is None:
            record = repo.create_owned(
                db,
                user_id,
                m.Recommendation,
                type=item.type,
                subject_key=item.subject_key,
                message=item.message,
                facts_hash=item.facts_hash,
                facts=item.facts,
                est_monthly_saving=item.est_monthly_saving,
                subscription_id=uuid.UUID(item.subscription_id) if item.subscription_id else None,
                extra_monthly_cost=item.extra_monthly_cost,
                percent_change=item.percent_change,
            )
        elif record.facts_hash != item.facts_hash or record.status == "resolved":
            record.facts_hash, record.facts, record.message = (
                item.facts_hash,
                item.facts,
                item.message,
            )
            record.est_monthly_saving = item.est_monthly_saving
            record.extra_monthly_cost, record.percent_change = (
                item.extra_monthly_cost,
                item.percent_change,
            )
            record.status = record.decisions.get(item.facts_hash, "open")
    for key, record in existing.items():
        if key not in seen and record.status != "resolved":
            record.status = "resolved"
    db.flush()
    return candidates


def potential_savings(db, user_id):
    from app import models as m
    from app import repositories as repo

    rows = repo.list_owned(
        db,
        user_id,
        m.Recommendation,
        m.Recommendation.type == "duplicate",
        m.Recommendation.status == "open",
        limit=None,
    )
    return money(sum((row.est_monthly_saving or ZERO for row in rows), ZERO))
