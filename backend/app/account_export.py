"""Stream an explicit export allowlist; never export passwords or authentication material."""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m

TABLES = (
    m.Upload,
    m.Transaction,
    m.Subscription,
    m.SubscriptionCharge,
    m.MerchantCategory,
    m.Budget,
    m.Recommendation,
    m.Alert,
    m.ChatMessage,
    m.StatementUsage,
    m.MailboxConnection,
    m.MailboxSync,
    m.ReceiptEvidence,
    m.PlanInterest,
)
PROFILE = (
    "email",
    "created_at",
    "alert_lead_days",
    "notification_email",
    "alerts_enabled",
    "live_opt_in",
)


def encode(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError("Unsupported export field")


def export_records(engine, user_id):
    """Every owned query is scoped to the authenticated caller; bounded cursor batches."""
    with Session(engine) as db:
        user = db.scalar(select(m.User).where(m.User.id == user_id))
        if user is None:
            return
        yield '{"profile":' + json.dumps(
            {name: getattr(user, name) for name in PROFILE}, default=encode
        )
        for model in TABLES:
            yield ',"' + model.__tablename__ + '":['
            first = True
            rows = db.scalars(
                select(model).where(model.user_id == user_id).execution_options(yield_per=100)
            )
            for row in rows:
                item = {
                    column.name: getattr(row, column.name) for column in model.__table__.columns
                    if column.name not in {"token_cipher", "verifier_cipher", "claim_token"}
                }
                yield ("" if first else ",") + json.dumps(item, default=encode)
                first = False
            yield "]"
        yield "}"
