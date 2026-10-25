"""Scoped, deterministic alert planning and eligibility reconciliation."""

from datetime import timedelta

from app import models as m
from app import repositories as repo
from app.services.renewals import sub_out
from app.services.summary import current_amount, equivalents, money, summarize


def generate(db, user_id, *, as_of, now):
    user = repo.get_user(db, user_id, lock=True)
    if user is None:
        return 0
    records = repo.list_owned(db, user_id, m.Alert, limit=None)
    existing = {(row.kind, row.event_key): row for row in records}
    plans = []
    subscriptions = repo.active_subscriptions(db, user_id)
    for sub in subscriptions:
        renewal = sub_out(sub, as_of=as_of)
        if sub.kind != "subscription" or sub.possibly_cancelled or renewal.possibly_cancelled:
            continue
        plans.append(
            dict(
                kind="renewal",
                event_key=f"renewal:{sub.id}:{renewal.next_expected}",
                subscription_id=sub.id,
                send_on=renewal.next_expected - timedelta(days=user.alert_lead_days),
                payload=dict(
                    merchant=sub.merchant,
                    amount=format(current_amount(sub), ".2f"),
                    currency=sub.currency,
                    renewal_date=renewal.next_expected.isoformat(),
                ),
            )
        )
    budgets = repo.list_owned(db, user_id, m.Budget, limit=1)
    total = summarize(db, user_id, period="month")["monthly_equivalent"]
    if budgets and total > budgets[0].monthly_limit:
        contributors = sorted(
            subscriptions, key=lambda s: (-equivalents(current_amount(s), s.cadence)[0], str(s.id))
        )[:3]
        plans.append(
            dict(
                kind="budget",
                event_key=f"budget:{as_of:%Y-%m}",
                subscription_id=None,
                send_on=as_of.replace(day=1),
                payload=dict(
                    budget=format(budgets[0].monthly_limit, ".2f"),
                    total=format(total, ".2f"),
                    overage=format(money(total - budgets[0].monthly_limit), ".2f"),
                    contributors=[
                        dict(
                            merchant=s.merchant,
                            kind=s.kind,
                            monthly_equivalent=format(
                                money(equivalents(current_amount(s), s.cadence)[0]), ".2f"
                            ),
                        )
                        for s in contributors
                    ],
                ),
            )
        )
    seen = set()
    created = 0
    for plan in plans:
        key = (plan["kind"], plan["event_key"])
        seen.add(key)
        record = existing.get(key)
        if record is None:
            record = repo.create_owned(db, user_id, m.Alert, **plan)
            created += 1
        if record.status in ("sent", "failed"):
            continue
        record.send_on = plan["send_on"]
        record.payload = {
            **plan["payload"],
            "generated_at": record.payload.get("generated_at", now.isoformat()),
        }
        record.recipient = user.notification_email
        reason = (
            "Alerts are disabled"
            if not user.alerts_enabled
            else "Email delivery suppressed after a bounce or complaint; update your address"
            if user.alerts_suppressed_at
            else "No notification email configured"
            if not user.notification_email
            else None
        )
        record.safe_failure_reason = reason if reason else record.safe_failure_reason
        if reason:
            record.status = "skipped"
        elif record.status == "skipped":
            record.status, record.safe_failure_reason = "pending", None
    for record in records:
        if (record.kind, record.event_key) not in seen and record.status not in ("sent", "failed"):
            record.status = "skipped"
            record.safe_failure_reason = (
                "Renewal is no longer eligible"
                if record.kind == "renewal"
                else "Budget is no longer exceeded or its period ended"
            )
    db.flush()
    return created
