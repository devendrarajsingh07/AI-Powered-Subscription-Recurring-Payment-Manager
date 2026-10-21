"""Validated API contract. JSON monetary values are decimal strings in both directions."""

import re
import uuid
from datetime import date, datetime
from datetime import date as DateValue
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    SecretStr,
    StrictBool,
    StrictInt,
    WithJsonSchema,
    field_validator,
    model_validator,
)

Status = Literal["active", "cancelled", "dismissed"]
Cadence = Literal["weekly", "monthly", "quarterly", "yearly"]
Kind = Literal["subscription", "fixed_bill"]
Category = Literal[
    "streaming",
    "music",
    "cloud",
    "fitness",
    "telecom",
    "software",
    "news",
    "rent",
    "loan",
    "insurance",
    "utilities",
    "unknown",
]


def decimal_input(value):
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Money must be a decimal string")
    if isinstance(value, str) and not re.fullmatch(r"\d{1,10}(?:\.\d{1,2})?", value):
        raise ValueError("Use a nonnegative decimal string with at most two decimal places")
    return value


Money = Annotated[
    Decimal,
    BeforeValidator(decimal_input),
    Field(ge=0, max_digits=12, decimal_places=2),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {"type": "string", "pattern": r"^\d{1,10}(\.\d{1,2})?$", "examples": ["199.00"]}
    ),
]


# Aggregates may exceed the per-record NUMERIC(12,2) limit.
AggregateMoney = Annotated[
    Decimal,
    BeforeValidator(decimal_input),
    Field(ge=0),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": r"^\d+(\.\d{1,2})?$"}),
]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AuthConfig(Schema):
    public_demo_only: bool
    session_mode: Literal["strict", "demo"]
    notice: str
    legal_version: str = ""
    legal_acceptance_required: bool = False


class ErrorDetail(Schema):
    code: str
    message: str


class ErrorEnvelope(Schema):
    error: ErrorDetail


class Register(Schema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"email": "demo@example.org", "password": "ExampleSecure42!"}
        },
    )
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=72)
    invite_code: SecretStr | None = Field(default=None, min_length=32, max_length=128)
    accepted_terms_version: str | None = Field(default=None, max_length=32)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        password = value.get_secret_value()
        compact = re.sub(r"[^a-z0-9]", "", password.casefold())
        common = {
            stem + suffix
            for stem in ("password", "qwerty", "welcome", "letmein", "admin", "changeme")
            for suffix in ("", "123", "1234", "12345", "123456", "2025", "2026", "2027")
        }
        if compact in common:
            raise ValueError("Choose a less common password")
        classes = [r"[a-z]", r"[A-Z]", r"[0-9]", r"[^a-zA-Z0-9]"]
        if (
            len(password.encode()) > 72
            or sum(bool(re.search(pattern, password)) for pattern in classes) < 3
        ):
            raise ValueError(
                "Use at least 12 characters and three character classes; max 72 UTF-8 bytes"
            )
        return value


class Login(Schema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"email": "demo@example.org", "password": "ExampleSecure42!"}
        },
    )
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=72)
    normalize_email = field_validator("email", mode="before")(Register.normalize_email.__func__)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value):
        if len(value.get_secret_value().encode()) > 72:
            raise ValueError("Password exceeds 72 UTF-8 bytes")
        return value


class UserOut(Schema):
    id: uuid.UUID
    email: str
    created_at: datetime
    email_verified: bool = False
    verification_required: bool = False


class Token(Schema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    csrf_token: str | None = None


class EmailRequest(Schema):
    email: EmailStr
    normalize_email = field_validator("email", mode="before")(Register.normalize_email.__func__)


class AccountCode(Schema):
    token: SecretStr = Field(min_length=32, max_length=128)


class ResetPassword(AccountCode):
    password: SecretStr = Field(min_length=12, max_length=72)
    validate_password = field_validator("password")(Register.strong_password.__func__)


class MessageResult(Schema):
    message: str


class CsrfResult(Schema):
    csrf_token: str | None


class RowWarning(Schema):
    line: int
    reason: str


class Preview(Schema):
    columns: list[str]
    suggested_mapping: dict[str, str]
    rows: list[list[str]]
    row_count: int
    malformed_csv: bool
    delimiter: str
    date_formats: list[str]
    warnings: list[RowWarning]
    malformed_count: int
    remainder_notice: str


class UploadOut(Schema):
    source_type: Literal["csv", "pdf_text", "pdf_ocr", "image_ocr"] = "csv"
    excluded_count: int = 0
    source: Literal["upload", "demo"] = "upload"
    demo_as_of: date | None = None
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "00000000-0000-4000-8000-000000000001",
                "filename": "sample_transactions.csv",
                "row_count": 399,
                "status": "pending",
                "stage": "queued",
                "processed_rows": 0,
                "total_rows": 399,
                "inserted_count": 0,
                "duplicate_count": 0,
                "malformed_count": 0,
                "detected_count": 0,
                "warnings": [],
                "error_message": None,
                "uploaded_at": "2026-10-18T10:00:00Z",
            }
        },
    )
    id: uuid.UUID
    filename: str
    row_count: int
    status: Literal["pending", "processing", "done", "failed"]
    stage: str
    processed_rows: int
    total_rows: int
    inserted_count: int
    duplicate_count: int
    malformed_count: int
    detected_count: int
    warnings: list[RowWarning]
    error_message: str | None
    uploaded_at: datetime
    remainder_notice: str = (
        "Broken CSV quoting makes the remaining input unreadable. "
        "Valid preceding rows are retained; "
        "the unreadable remainder counts as one malformed record."
    )


class PriceIncreaseOut(Schema):
    previous_amount: Money
    new_amount: Money
    detected_on: date


class SubscriptionOut(Schema):
    id: uuid.UUID
    merchant: str
    category: Category
    kind: Kind
    currency: str
    cadence: Cadence
    avg_amount: Money
    confidence: Decimal
    regularity: Decimal
    amount_cv: Decimal
    occurrences: int
    last_charge: date
    next_expected: date
    status: Status
    user_confirmed: bool
    requires_confirmation: bool
    cancelled_at: datetime | None
    last_used_at: date | None
    possibly_cancelled: bool
    missed_cycles: int
    price_increase: PriceIncreaseOut | None = None


class ChargeOut(Schema):
    id: uuid.UUID
    date: date
    description: str
    amount: Money
    currency: str
    type: Literal["debit", "credit"]


class SubscriptionDetail(SubscriptionOut):
    charges: list[ChargeOut]
    charges_total: int
    charges_offset: int
    charges_limit: int


class SubscriptionPatch(Schema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"user_confirmed": True, "category": "music", "last_used_at": "2026-10-18"}
        },
    )
    user_confirmed: StrictBool | None = None
    status: Status | None = None
    category: Category | None = None
    last_used_at: date | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("Provide a subscription decision")
        if any(getattr(self, key) is None for key in self.model_fields_set - {"last_used_at"}):
            raise ValueError("Decision fields cannot be null")
        return self


class BudgetPut(Schema):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"monthly_limit": "2000.00"}}
    )
    monthly_limit: Money


class BudgetOut(Schema):
    monthly_limit: Money | None
    currency: Literal["INR"] = "INR"


class AlertSettings(Schema):
    lead_time_days: Annotated[StrictInt, Field(ge=1, le=30)] = 3
    notification_email: EmailStr | None = None
    enabled: StrictBool = True


class AlertSettingsOut(AlertSettings):
    delivery_mode: Literal["console", "smtp"]
    delivery_notice: str
    # Set after a provider bounce/complaint for the saved address; changing the address clears it.
    suppressed_reason: Literal["hard_bounce", "complaint"] | None = None


class SupportReportIn(Schema):
    model_config = ConfigDict(extra="forbid")
    category: Literal["bug", "data_issue", "account", "other"]
    message: str = Field(min_length=10, max_length=1000)


class SupportReportOut(Schema):
    id: uuid.UUID
    received: bool


class CategoryOut(Schema):
    id: uuid.UUID
    merchant: str
    category: Category
    source: Literal["rule", "llm", "user"]
    confirmed: bool
    suggestion_attempted: bool = False


class CategoryPatch(Schema):
    category: Category

    @field_validator("category")
    @classmethod
    def known_category(cls, value):
        if value == "unknown":
            raise ValueError("Choose a known category to confirm")
        return value


class Totals(Schema):
    monthly_equivalent: AggregateMoney
    yearly_total: AggregateMoney
    count: int


class CategoryTotal(Totals):
    category: Category
    kind: Kind


class Summary(Schema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "period": "month",
                "currency": "INR",
                "monthly_equivalent": "0.00",
                "yearly_total": "0.00",
                "period_total": "0.00",
                "active_count": 0,
                "subscriptions": {"monthly_equivalent": "0.00", "yearly_total": "0.00", "count": 0},
                "fixed_bills": {"monthly_equivalent": "0.00", "yearly_total": "0.00", "count": 0},
                "categories": [],
            }
        },
    )
    period: Literal["month", "year"]
    currency: Literal["INR"] = "INR"
    monthly_equivalent: AggregateMoney
    yearly_total: AggregateMoney
    period_total: AggregateMoney
    active_count: int
    subscriptions: Totals
    fixed_bills: Totals
    categories: list[CategoryTotal]


class TrendPoint(Schema):
    month: str
    subscriptions: AggregateMoney
    fixed_bills: AggregateMoney
    total: AggregateMoney


class Trend(Schema):
    currency: Literal["INR"] = "INR"
    months: list[TrendPoint]


class DeleteResult(Schema):
    deleted: dict[str, int]


T = TypeVar("T")


class Page(Schema, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


RecommendationType = Literal["duplicate", "high_cost", "price_increase", "possibly_unused"]
RecommendationStatus = Literal["open", "accepted", "dismissed", "resolved"]


class RecommendationMember(Schema):
    subscription_id: uuid.UUID
    merchant: str
    category: Category
    cadence: Cadence
    avg_amount: Money
    monthly_equivalent: AggregateMoney


class RecommendationOut(Schema):
    id: uuid.UUID
    type: RecommendationType
    status: RecommendationStatus
    message: str
    subscription_id: uuid.UUID | None
    members: list[RecommendationMember]
    est_monthly_saving: AggregateMoney | None
    extra_monthly_cost: AggregateMoney | None
    percent_change: AggregateMoney | None
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RecommendationPatch(Schema):
    action: Literal["accept", "dismiss"]


class SavingsOut(Schema):
    potential_savings: AggregateMoney
    currency: Literal["INR"] = "INR"


class AlertOut(Schema):
    id: uuid.UUID
    subscription_id: uuid.UUID | None
    kind: Literal["renewal", "budget"]
    send_on: date
    status: Literal["pending", "retrying", "sent", "skipped", "failed"]
    sent_at: datetime | None
    channel: Literal["email"]
    attempt_count: int
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    safe_failure_reason: str | None


class ChatRequest(Schema):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class ChatConsent(Schema):
    live_opt_in: StrictBool


class ChatConfig(Schema):
    mode: Literal["offline", "live"]
    provider: Literal["fake", "gemini"] = "fake"
    live_opt_in: bool
    disclosure: str
    # Why a configured live provider is currently answered offline (operator or cap).
    fallback_reason: Literal["kill_switch", "daily_cap"] | None = None


class ChatFinal(Schema):
    answer: str
    verified: bool
    tools: list[str]
    conversation_id: uuid.UUID
    mode: Literal["offline", "live"] = "offline"
    # Set when a live-capable deployment answered offline: operator switch, global cap, or error.
    fallback_reason: Literal["kill_switch", "daily_cap", "provider_error"] | None = None


class ChatStatus(Schema):
    tool: str
    message: str


class ChatStreamError(Schema):
    message: str


class ChatHistory(Schema):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant", "tool"]
    content: str
    verified: bool | None
    tools: list[str]
    created_at: datetime


class ClearedHistory(Schema):
    deleted: int


class ExtractedRow(Schema):
    index: int
    date: DateValue | None
    description: str = Field(max_length=1000)
    amount: Money | None
    type: Literal["debit", "credit"] | None
    page: int
    confidence: str
    field_confidence: dict[str, str] = Field(default_factory=dict)
    flags: list[str]
    balance: str | None


class Reconciliation(Schema):
    status: Literal["matched", "mismatch", "unavailable"]
    balance_checks: int
    total_checks: int
    opening: str | None
    closing: str | None


class StatementResult(Schema):
    rows: list[ExtractedRow]
    source_type: Literal["pdf_text", "pdf_ocr", "image_ocr"]
    page_count: int
    flagged_count: int
    reconciliation: Reconciliation
    warnings: list[str]


class StatementPreviewOut(Schema):
    id: uuid.UUID
    filename: str
    status: Literal["pending", "processing", "ready", "failed", "cancelled", "confirmed"]
    stage: str
    source_type: Literal["pdf_text", "pdf_ocr", "image_ocr"]
    processed_pages: int
    total_pages: int
    expires_at: datetime
    error_code: str | None
    error_message: str | None
    result: StatementResult | None
    upload_id: uuid.UUID | None


class RowEdit(Schema):
    index: StrictInt = Field(ge=0, le=4999)
    date: DateValue | None = None
    description: str | None = Field(default=None, min_length=1, max_length=1000, strict=True)
    amount: Money | None = None
    type: Literal["debit", "credit"] | None = None
    verified: StrictBool = False
    delete: StrictBool = False


JobStatus = Literal["staging", "queued", "running", "done", "dead_letter", "cancelled"]


class JobOut(Schema):
    id: uuid.UUID
    upload_id: uuid.UUID | None
    preview_id: uuid.UUID | None
    kind: Literal["csv", "extraction"]
    status: JobStatus
    attempt_count: int
    max_attempts: int
    available_at: datetime
    expires_at: datetime
    created_at: datetime
    failure_code: str | None


class JobAction(Schema):
    action: Literal["cancel"]
