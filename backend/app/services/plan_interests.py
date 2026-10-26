"""Independent voluntary declarations only. Never import or query financial/mailbox models."""

from sqlalchemy import delete, func, select

from app.account_security import audit
from app.models import PlanInterest
from app.repositories import create_owned, list_owned, lock_ingestion

VERSION = "voluntary-interest-v1"
DISCLOSURE = (
    "Optional synthetic declaration of interest in provider-approved group offers. "
    "No offers, discounts or provider partnerships currently exist. This never uses your "
    "emails, transactions or subscriptions. Nothing is shared with a provider. "
    "Withdraw any time. This is separate from mailbox consent."
)


def preferences(db, user_id):
    return list_owned(db, user_id, PlanInterest, limit=3, order_by=PlanInterest.category)


def replace(db, user_id, categories):
    lock_ingestion(db, user_id)
    db.execute(delete(PlanInterest).where(PlanInterest.user_id == user_id))
    for category in categories:
        create_owned(db, user_id, PlanInterest, category=category, consent_version=VERSION)
    audit(db, user_id, "plan_interest_changed")
    db.commit()
    return preferences(db, user_id)


def cohorts(db):
    """Internal operator only; low-count groups are suppressed, never sent to partners."""
    return [
        {"category": category, "count": count}
        for category, count in db.execute(
            select(PlanInterest.category, func.count())
            .where(PlanInterest.consent_version == VERSION)
            .group_by(PlanInterest.category)
        )
        if count >= 10
    ]
