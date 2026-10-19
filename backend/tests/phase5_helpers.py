import uuid
from datetime import date, timedelta
from decimal import Decimal

from app import models as m
from app import repositories as repo

DAY = date(2026, 10, 18)


def plan(db, user_id, *, amount="100.00", **values):
    data = dict(
        identity_key=uuid.uuid4().hex,
        merchant="synthetic plan",
        category="software",
        kind="subscription",
        currency="INR",
        cadence="monthly",
        avg_amount=Decimal(amount),
        confidence=Decimal("0.95"),
        regularity=Decimal(1),
        amount_cv=Decimal(0),
        occurrences=3,
        last_charge=DAY - timedelta(days=27),
        next_expected=DAY + timedelta(days=3),
        status="active",
        user_confirmed=True,
        requires_confirmation=False,
    )
    data.update(values)
    return repo.create_owned(db, user_id, m.Subscription, **data)


def owner(db, *, notification_email="notify@example.org", enabled=True):
    user = m.User(
        email=f"synthetic-{uuid.uuid4().hex}@example.org",
        password_hash="unused-synthetic",
        notification_email=notification_email,
        alerts_enabled=enabled,
        alert_lead_days=3,
    )
    db.add(user)
    db.flush()
    return user
