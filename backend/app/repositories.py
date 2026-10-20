"""Only scoped access to user-owned records. No caller/model can override ownership."""

import uuid
from collections import defaultdict
from hashlib import sha256

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import models as m
from app.services.categories import kind_for_category
from app.services.detector import Detection, Transaction, detect_recurring
from app.services.normalizer import normalize_merchant


def get_user(db: Session, user_id: uuid.UUID, *, lock: bool = False):
    query = select(m.User).where(m.User.id == user_id)
    return db.scalar(query.with_for_update(key_share=True) if lock else query)


def lock_ingestion(db, user_id):
    """Serialize submission policy, independently of the longer detection row lock."""
    key = int.from_bytes(sha256(str(user_id).encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def get_owned(db, user_id, model, object_id):
    return db.scalar(select(model).where(model.user_id == user_id, model.id == object_id))


def list_owned(db, user_id, model, *conditions, offset=0, limit=100, order_by=None):
    query = select(model).where(model.user_id == user_id, *conditions)
    if order_by is not None:
        query = query.order_by(order_by, model.id)
    else:
        query = query.order_by(model.id)
    return list(db.scalars(query.offset(offset).limit(limit)))


def count_owned(db, user_id, model, *conditions):
    return db.scalar(
        select(func.count()).select_from(model).where(model.user_id == user_id, *conditions)
    )


def create_owned(db, user_id, model, **values):
    if "user_id" in values:
        raise ValueError("Ownership cannot be overridden")
    record = model(user_id=user_id, **values)
    db.add(record)
    db.flush()
    return record


def update_upload(db, user_id, upload_id, *, inflight_only=False, **values):
    statement = update(m.Upload).where(m.Upload.user_id == user_id, m.Upload.id == upload_id)
    if inflight_only:
        statement = statement.where(m.Upload.status.in_(["pending", "processing"]))
    return db.execute(statement.values(**values)).rowcount


def insert_transactions(db, user_id, upload_id, transactions):
    values = [
        dict(
            id=uuid.uuid4(),
            user_id=user_id,
            upload_id=upload_id,
            date=tx.date,
            raw_description=tx.raw_description,
            merchant_normalized=normalize_merchant(tx.raw_description),
            amount=tx.amount,
            type=tx.type,
            currency=tx.currency,
        )
        for tx in transactions
    ]
    if not values:
        return 0
    statement = (
        insert(m.Transaction)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_transaction_dedupe")
        .returning(m.Transaction.id)
    )
    return len(list(db.scalars(statement)))


def category_cache(db, user_id, merchant, category, *, source, confirmed):
    existing = db.scalar(
        select(m.MerchantCategory).where(
            m.MerchantCategory.user_id == user_id, m.MerchantCategory.merchant == merchant
        )
    )
    if existing:
        if source == "user" or (existing.source != "user" and not existing.suggestion_attempted):
            existing.category, existing.source, existing.confirmed = category, source, confirmed
        return existing
    return create_owned(
        db,
        user_id,
        m.MerchantCategory,
        merchant=merchant,
        category=category,
        source=source,
        confirmed=confirmed,
    )


def redetect(db, user_id, *, as_of):
    records = list(
        db.scalars(
            select(m.Transaction).where(
                m.Transaction.user_id == user_id, m.Transaction.type == "debit"
            )
        )
    )
    transactions = [
        Transaction(tx.date, tx.raw_description, tx.amount, tx.type, tx.currency, tx.id)
        for tx in records
    ]
    detections = detect_recurring(transactions, as_of=as_of)
    persist_detections(db, user_id, detections, as_of=as_of)
    return len(detections)


def persist_detections(db, user_id, detections: list[Detection], *, as_of):
    existing = list(db.scalars(select(m.Subscription).where(m.Subscription.user_id == user_id)))
    links = defaultdict(set)
    for sub_id, tx_id in db.execute(
        select(m.SubscriptionCharge.subscription_id, m.SubscriptionCharge.transaction_id).where(
            m.SubscriptionCharge.user_id == user_id
        )
    ):
        links[sub_id].add(tx_id)
    used = set()
    for detection in detections:
        charge_ids = {tx.id for tx in detection.charges}
        eligible = [
            sub
            for sub in existing
            if sub.id not in used
            and sub.merchant == detection.merchant
            and sub.currency == detection.currency
            and sub.cadence == detection.cadence
        ]
        eligible.sort(key=lambda sub: (-len(links[sub.id] & charge_ids), str(sub.id)))
        record = eligible[0] if eligible and links[eligible[0].id] & charge_ids else None
        if record is None:
            anchor = min(str(tx_id) for tx_id in charge_ids)
            identity = sha256(
                f"{detection.merchant}|{detection.currency}|{detection.cadence}|{anchor}".encode()
            ).hexdigest()
            record = create_owned(
                db,
                user_id,
                m.Subscription,
                identity_key=identity,
                merchant=detection.merchant,
                category=detection.category,
                kind=detection.kind,
                currency=detection.currency,
                cadence=detection.cadence,
                avg_amount=detection.avg_amount,
                confidence=detection.confidence,
                regularity=detection.regularity,
                amount_cv=detection.amount_cv,
                occurrences=detection.occurrences,
                last_charge=detection.last_charge,
                next_expected=detection.next_expected,
            )
        used.add(record.id)
        for name in (
            "avg_amount",
            "confidence",
            "regularity",
            "amount_cv",
            "occurrences",
            "last_charge",
            "next_expected",
            "possibly_cancelled",
            "missed_cycles",
        ):
            setattr(record, name, getattr(detection, name))
        cache = category_cache(
            db,
            user_id,
            detection.merchant,
            detection.category,
            source="rule",
            confirmed=not detection.requires_confirmation,
        )
        if not record.category_overridden:
            record.category = cache.category if cache.source == "user" else detection.category
            record.kind = (
                kind_for_category(cache.category) if cache.source == "user" else detection.kind
            )
        record.requires_confirmation = record.category == "unknown" and not record.user_confirmed
        price = detection.price_increase
        same_price = price and (
            record.price_previous_amount == price.previous_median
            and record.price_new_amount == price.latest_amount
        )
        detected_on = record.price_detected_on if same_price else as_of
        record.price_previous_amount = price.previous_median if price else None
        record.price_new_amount = price.latest_amount if price else None
        record.price_detected_on = detected_on if price else None
        db.execute(
            delete(m.SubscriptionCharge).where(
                m.SubscriptionCharge.user_id == user_id,
                m.SubscriptionCharge.subscription_id == record.id,
            )
        )
        db.add_all(
            [
                m.SubscriptionCharge(
                    user_id=user_id, subscription_id=record.id, transaction_id=tx_id
                )
                for tx_id in charge_ids
            ]
        )
    db.flush()


def subscription_charges(db, user_id, subscription_id):
    return list(
        db.scalars(
            select(m.Transaction)
            .join(m.SubscriptionCharge, m.SubscriptionCharge.transaction_id == m.Transaction.id)
            .where(
                m.Transaction.user_id == user_id,
                m.SubscriptionCharge.user_id == user_id,
                m.SubscriptionCharge.subscription_id == subscription_id,
            )
            .order_by(m.Transaction.date, m.Transaction.id)
        )
    )


def linked_transactions(db, user_id, *, since, until):
    linked = select(m.SubscriptionCharge.transaction_id).where(
        m.SubscriptionCharge.user_id == user_id
    )
    return list(
        db.scalars(
            select(m.Transaction).where(
                m.Transaction.user_id == user_id,
                m.Transaction.id.in_(linked),
                m.Transaction.date >= since,
                m.Transaction.date <= until,
            )
        )
    )


def active_subscriptions(db, user_id):
    return list(
        db.scalars(
            select(m.Subscription).where(
                m.Subscription.user_id == user_id, m.Subscription.status == "active"
            )
        )
    )


def all_unconfirmed(db, user_id, *, offset, limit):
    return list_owned(
        db,
        user_id,
        m.MerchantCategory,
        m.MerchantCategory.confirmed.is_(False),
        offset=offset,
        limit=limit,
    )


def confirm_category(db, user_id, merchant, category):
    cache = category_cache(db, user_id, merchant, category, source="user", confirmed=True)
    db.execute(
        update(m.Subscription)
        .where(m.Subscription.user_id == user_id, m.Subscription.merchant == merchant)
        .values(
            category=category,
            kind=kind_for_category(category),
            category_overridden=True,
            requires_confirmation=False,
        )
    )
    return cache


def delete_data(db, user_id):
    counts = {}
    for table in reversed(m.Base.metadata.sorted_tables):
        if "user_id" in table.c:
            counts[table.name] = db.scalar(
                select(func.count()).select_from(table).where(table.c.user_id == user_id)
            )
    db.execute(delete(m.User).where(m.User.id == user_id))
    counts["users"] = 1
    return counts


def recover_uploads(db, user_id):
    return db.execute(
        update(m.Upload)
        .where(m.Upload.user_id == user_id, m.Upload.status.in_(["pending", "processing"]))
        .values(
            status="failed",
            stage="failed",
            error_message="Processing was interrupted; please upload again.",
        )
    ).rowcount


def purge_statement_previews(db, user_id, now):
    return db.execute(
        delete(m.StatementPreview).where(
            m.StatementPreview.user_id == user_id, m.StatementPreview.expires_at <= now
        )
    ).rowcount


def statement_usage(db, user_id, day):
    row = db.scalar(
        select(m.StatementUsage).where(
            m.StatementUsage.user_id == user_id, m.StatementUsage.day == day
        )
    )
    if row is None:
        row = create_owned(
            db,
            user_id,
            m.StatementUsage,
            day=day,
            attempts=0,
            failures=0,
            flagged_rows=0,
            edited_rows=0,
        )
    return row
