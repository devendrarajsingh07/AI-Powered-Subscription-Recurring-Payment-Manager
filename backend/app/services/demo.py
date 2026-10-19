"""Synthetic CSV travels through the ordinary upload pipeline. No fixture detections."""

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select

from app import models as m
from app import repositories as repo
from app.config import get_settings
from app.services.alerts import generate
from app.services.insights import regenerate
from app.services.summary import summarize
from scripts.gen_sample_data import generate_dataset

MAPPING = {key: key for key in ("date", "description", "amount", "type")}


def ensure_enabled():
    cfg = get_settings()
    if not cfg.demo_enabled or cfg.environment == "production":
        raise HTTPException(404, {"code": "not_found", "message": "Demo loading is disabled"})


def dataset(as_of):
    rows, truth = generate_dataset(as_of=as_of)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode(), truth


def prepare(db, user_id, *, as_of):
    ensure_enabled()
    repo.lock_ingestion(db, user_id)
    repo.get_user(db, user_id, lock=True)
    existing = repo.list_owned(db, user_id, m.Upload, m.Upload.source == "demo", limit=None)
    if existing:
        return existing[0], False
    if repo.count_owned(db, user_id, m.Upload) or repo.count_owned(db, user_id, m.Transaction):
        raise HTTPException(
            409,
            {
                "code": "demo_requires_empty",
                "message": "Use an empty account for demo data; existing uploads were kept.",
            },
        )
    return repo.create_owned(
        db, user_id, m.Upload, filename="subtrack-demo.csv", source="demo", demo_as_of=as_of
    ), True


def finalize(db, user_id, upload_id, *, as_of):
    upload = repo.get_owned(db, user_id, m.Upload, upload_id)
    if upload.source != "demo":
        return
    user = repo.get_user(db, user_id, lock=True)
    defaults = {}
    if not repo.list_owned(db, user_id, m.Budget):
        amount = summarize(db, user_id, period="month")["monthly_equivalent"] - Decimal("100.00")
        amount = max(Decimal("0.00"), amount)
        repo.create_owned(db, user_id, m.Budget, monthly_limit=amount)
        defaults["budget"] = str(amount)
    if not user.notification_email:
        user.notification_email = "demo@example.org"
        defaults["notification_email"] = user.notification_email
    upload.demo_defaults = defaults
    db.flush()
    generate(db, user_id, as_of=as_of, now=datetime.now(timezone.utc))


def remove(db, user_id, *, as_of):
    """Delete provenance-linked records; preserve real charges and user-edited preferences."""
    repo.get_user(db, user_id, lock=True)
    uploads = repo.list_owned(db, user_id, m.Upload, m.Upload.source == "demo", limit=None)
    if any(u.status in ("pending", "processing") for u in uploads):
        raise HTTPException(
            409, {"code": "demo_busy", "message": "Wait for demo processing to finish"}
        )
    ids = [u.id for u in uploads]
    affected = list(
        db.scalars(
            select(m.SubscriptionCharge.subscription_id).where(
                m.SubscriptionCharge.user_id == user_id,
                m.SubscriptionCharge.transaction_id.in_(
                    select(m.Transaction.id).where(
                        m.Transaction.user_id == user_id, m.Transaction.upload_id.in_(ids)
                    )
                ),
            )
        )
    )
    counts = {
        "uploads": len(ids),
        "transactions": repo.count_owned(
            db, user_id, m.Transaction, m.Transaction.upload_id.in_(ids)
        ),
    }
    for upload in uploads:
        defaults = upload.demo_defaults or {}
        for budget in repo.list_owned(db, user_id, m.Budget):
            if str(budget.monthly_limit) == defaults.get("budget"):
                db.delete(budget)
        user = repo.get_user(db, user_id)
        if user.notification_email == defaults.get("notification_email"):
            user.notification_email = None
        db.delete(upload)
    db.flush()
    for sub in repo.list_owned(
        db, user_id, m.Subscription, m.Subscription.id.in_(affected), limit=None
    ):
        if not repo.count_owned(
            db, user_id, m.SubscriptionCharge, m.SubscriptionCharge.subscription_id == sub.id
        ):
            db.delete(sub)
    db.flush()
    # Cache entries without any remaining real merchant are no longer needed.
    db.execute(
        delete(m.MerchantCategory).where(
            m.MerchantCategory.user_id == user_id,
            ~m.MerchantCategory.merchant.in_(
                select(m.Transaction.merchant_normalized).where(m.Transaction.user_id == user_id)
            ),
        )
    )
    if ids and not repo.count_owned(db, user_id, m.Transaction):
        from app.services.notifier import ConsoleNotifier

        ConsoleNotifier(get_settings().outbox_dir).purge(user_id)
        for model in (m.Recommendation, m.Alert, m.ChatMessage):
            db.execute(delete(model).where(model.user_id == user_id))
    regenerate(db, user_id, as_of=as_of)
    generate(db, user_id, as_of=as_of, now=datetime.now(timezone.utc))
    return counts
