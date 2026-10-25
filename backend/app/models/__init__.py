"""PostgreSQL domain schema. Alembic owns schema creation and changes."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def choices(name, *values):
    return Enum(*values, name=name, native_enum=False, create_constraint=True)


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Owned(Identity):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_version: Mapped[int] = mapped_column(Integer, server_default="0")
    demo_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    alert_lead_days: Mapped[int] = mapped_column(Integer, server_default="3")
    notification_email: Mapped[str | None] = mapped_column(String(254))
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    live_opt_in: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Set by a provider bounce/complaint event for the current notification address.
    alerts_suppressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alerts_suppressed_reason: Mapped[str | None] = mapped_column(String(16))
    # Accepted legal draft version; recorded when supplied, required only if the flag is on.
    terms_version: Mapped[str | None] = mapped_column(String(32))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("alert_lead_days BETWEEN 1 AND 30", name="ck_alert_lead"),
        CheckConstraint(
            "alerts_suppressed_reason IS NULL OR alerts_suppressed_reason IN "
            "('hard_bounce', 'complaint')",
            name="ck_alert_suppression_reason",
        ),
    )


class Upload(Owned, Base):
    __tablename__ = "uploads"
    source: Mapped[str] = mapped_column(String(16), server_default="upload")
    source_type: Mapped[str] = mapped_column(String(16), server_default="csv")
    excluded_count: Mapped[int] = mapped_column(Integer, server_default="0")
    demo_as_of: Mapped[date | None] = mapped_column(Date)
    demo_defaults: Mapped[dict | None] = mapped_column(JSONB)
    filename: Mapped[str] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(
        choices("upload_status", "pending", "processing", "done", "failed"), default="pending"
    )
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    processed_rows: Mapped[int] = mapped_column(Integer, server_default="0")
    total_rows: Mapped[int] = mapped_column(Integer, server_default="0")
    inserted_count: Mapped[int] = mapped_column(Integer, server_default="0")
    duplicate_count: Mapped[int] = mapped_column(Integer, server_default="0")
    malformed_count: Mapped[int] = mapped_column(Integer, server_default="0")
    detected_count: Mapped[int] = mapped_column(Integer, server_default="0")
    warnings: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    error_message: Mapped[str | None] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_upload_owner"),)


class StatementPreview(Owned, Base):
    __tablename__ = "statement_previews"
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), server_default="pending")
    stage: Mapped[str] = mapped_column(String(64), server_default="queued")
    source_type: Mapped[str] = mapped_column(String(16), server_default="pdf_text")
    processed_pages: Mapped[int] = mapped_column(Integer, server_default="0")
    total_pages: Mapped[int] = mapped_column(Integer, server_default="0")
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(255))
    upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_preview_owner"),
        ForeignKeyConstraint(
            ["upload_id", "user_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
    )


class StatementUsage(Owned, Base):
    __tablename__ = "statement_usage"
    day: Mapped[date] = mapped_column(Date)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    failures: Mapped[int] = mapped_column(Integer, server_default="0")
    flagged_rows: Mapped[int] = mapped_column(Integer, server_default="0")
    edited_rows: Mapped[int] = mapped_column(Integer, server_default="0")
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_statement_usage_day"),)


class Transaction(Owned, Base):
    __tablename__ = "transactions"
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    date: Mapped[date] = mapped_column(Date)
    raw_description: Mapped[str] = mapped_column(Text)
    merchant_normalized: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    type: Mapped[str] = mapped_column(choices("transaction_type", "debit", "credit"))
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_transaction_owner"),
        ForeignKeyConstraint(
            ["upload_id", "user_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
        UniqueConstraint(
            "user_id", "date", "raw_description", "amount", name="uq_transaction_dedupe"
        ),
        Index("ix_transactions_merchant_date", "user_id", "merchant_normalized", "date"),
        CheckConstraint("amount > 0", name="ck_transaction_amount"),
    )


class Subscription(Owned, Base):
    __tablename__ = "subscriptions"
    identity_key: Mapped[str] = mapped_column(String(64))
    merchant: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(choices("recurring_kind", "subscription", "fixed_bill"))
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    cadence: Mapped[str] = mapped_column(
        choices("cadence", "weekly", "monthly", "quarterly", "yearly")
    )
    avg_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    billing_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    regularity: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    amount_cv: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    occurrences: Mapped[int] = mapped_column(Integer)
    last_charge: Mapped[date] = mapped_column(Date)
    next_expected: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        choices("subscription_status", "active", "cancelled", "dismissed"), default="active"
    )
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    category_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[date | None] = mapped_column(Date)
    possibly_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    missed_cycles: Mapped[int] = mapped_column(Integer, default=0)
    price_previous_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_new_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_detected_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_subscription_owner"),
        UniqueConstraint("user_id", "identity_key", name="uq_subscription_identity"),
        CheckConstraint("avg_amount > 0", name="ck_subscription_amount"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_confidence"),
    )


class SubscriptionCharge(Base):
    __tablename__ = "subscription_charges"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["subscription_id", "user_id"],
            ["subscriptions.id", "subscriptions.user_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            ondelete="CASCADE",
        ),
    )


class MerchantCategory(Owned, Base):
    __tablename__ = "merchant_categories"
    merchant: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(choices("category_source", "rule", "llm", "user"))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    suggestion_attempted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    __table_args__ = (UniqueConstraint("user_id", "merchant", name="uq_merchant_category"),)


class Budget(Owned, Base):
    __tablename__ = "budgets"
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_budget_user"),
        CheckConstraint("monthly_limit >= 0", name="ck_budget_limit"),
    )


class Recommendation(Owned, Base):
    __tablename__ = "recommendations"
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    type: Mapped[str] = mapped_column(
        choices(
            "recommendation_type", "duplicate", "high_cost", "price_increase", "possibly_unused"
        )
    )
    message: Mapped[str] = mapped_column(Text)
    est_monthly_saving: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    subject_key: Mapped[str] = mapped_column(String(100), default=lambda: uuid.uuid4().hex)
    facts_hash: Mapped[str] = mapped_column(String(64), default="legacy")
    facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    decisions: Mapped[dict] = mapped_column(JSONB, default=dict)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    percent_change: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(
        choices("recommendation_status", "open", "accepted", "dismissed", "resolved"),
        default="open",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("user_id", "type", "subject_key", name="uq_recommendation_subject"),
        ForeignKeyConstraint(
            ["subscription_id", "user_id"],
            ["subscriptions.id", "subscriptions.user_id"],
            ondelete="CASCADE",
        ),
    )


class Alert(Owned, Base):
    __tablename__ = "alerts"
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(choices("alert_kind", "renewal", "budget"))
    send_on: Mapped[date] = mapped_column(Date)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(choices("alert_channel", "email"), default="email")
    payload: Mapped[dict] = mapped_column(JSONB)
    event_key: Mapped[str] = mapped_column(String(100), default=lambda: uuid.uuid4().hex)
    recipient: Mapped[str | None] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(
        choices("alert_status", "pending", "retrying", "sent", "skipped", "failed"),
        default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_failure_reason: Mapped[str | None] = mapped_column(String(255))
    delivery_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (
        ForeignKeyConstraint(
            ["subscription_id", "user_id"],
            ["subscriptions.id", "subscriptions.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_id", "kind", "event_key", name="uq_alert_event"),
        Index(
            "uq_alert_budget_month",
            "user_id",
            "send_on",
            unique=True,
            postgresql_where=text("kind = 'budget'"),
        ),
        CheckConstraint(
            "kind != 'budget' OR (subscription_id IS NULL AND EXTRACT(DAY FROM send_on) = 1)",
            name="ck_budget_alert_month",
        ),
        CheckConstraint(
            "kind != 'renewal' OR subscription_id IS NOT NULL", name="ck_renewal_subscription"
        ),
    )


class ChatMessage(Owned, Base):
    __tablename__ = "chat_messages"
    role: Mapped[str] = mapped_column(choices("chat_role", "user", "assistant", "tool"))
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[dict | list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    verified: Mapped[bool | None] = mapped_column(Boolean)


class RegistrationInvite(Owned, Base):
    """Owned by the issuing account. Only the operator CLI can create/revoke invites."""

    __tablename__ = "registration_invites"
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    email_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecurityEvent(Identity, Base):
    """No free-form metadata: never persist credentials, IPs or financial content here."""

    __tablename__ = "security_events"
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateLimitBucket(Identity, Base):
    """Shared fixed windows. Anonymous IP buckets have no user; keys are HMAC digests."""

    __tablename__ = "rate_limit_buckets"
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    key_digest: Mapped[str] = mapped_column(String(64), unique=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuthSession(Owned, Base):
    __tablename__ = "auth_sessions"
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_auth_session_owner"),)


class RefreshToken(Owned, Base):
    __tablename__ = "refresh_tokens"
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "user_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="CASCADE",
        ),
    )


class AccountToken(Owned, Base):
    __tablename__ = "account_tokens"
    kind: Mapped[str] = mapped_column(String(16))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginBackoff(Identity, Base):
    __tablename__ = "login_backoffs"
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    key_digest: Mapped[str] = mapped_column(String(64), unique=True)
    failures: Mapped[int] = mapped_column(Integer, server_default="0")
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DurableJob(Owned, Base):
    """Opaque bounded input; the worker never stores a PDF password."""

    __tablename__ = "durable_jobs"
    upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    preview_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    encrypted_input: Mapped[bytes | None] = mapped_column(LargeBinary)
    as_of: Mapped[date] = mapped_column(Date)
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["upload_id", "user_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["preview_id", "user_id"],
            ["statement_previews.id", "statement_previews.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("num_nonnulls(upload_id, preview_id) = 1", name="ck_job_subject"),
        CheckConstraint("kind IN ('csv', 'extraction')", name="ck_job_kind"),
        CheckConstraint(
            "status IN ('staging', 'queued', 'running', 'done', 'dead_letter', 'cancelled')",
            name="ck_job_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5", name="ck_job_attempts"
        ),
        CheckConstraint("octet_length(encrypted_input) <= 14680064", name="ck_job_input_size"),
        Index("ix_job_claim", "status", "available_at", "lease_until"),
    )


class ChatLease(Owned, Base):
    __tablename__ = "chat_leases"
    claim_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    minute_count: Mapped[int] = mapped_column(Integer, server_default="0")
    minute_reset: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    daily_count: Mapped[int] = mapped_column(Integer, server_default="0")
    daily_day: Mapped[date] = mapped_column(Date, server_default=text("CURRENT_DATE"))
    __table_args__ = (UniqueConstraint("user_id", name="uq_chat_lease_user"),)


class LlmSwitch(Base):
    """Singleton operator kill switch shared by all instances. System-wide, content-free."""

    __tablename__ = "llm_switch"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default="1")
    offline_forced: Mapped[bool] = mapped_column(Boolean, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("id = 1", name="ck_llm_switch_singleton"),)


class LlmUsage(Base):
    """Global per-day counters for live-provider caps and metrics. Counts only, no content."""

    __tablename__ = "llm_usage"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, server_default="0")
    tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    fallbacks: Mapped[int] = mapped_column(Integer, server_default="0")
    errors: Mapped[int] = mapped_column(Integer, server_default="0")


class SupportReport(Owned, Base):
    """Free text problem reports. Statements, account numbers and amounts are refused upstream."""

    __tablename__ = "support_reports"
    category: Mapped[str] = mapped_column(
        choices("support_category", "bug", "data_issue", "account", "other")
    )
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
