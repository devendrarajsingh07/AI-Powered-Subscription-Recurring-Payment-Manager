import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.exc import IntegrityError

from app import auth
from app import repositories as repo
from app import schemas as s
from app.clock import today
from app.config import get_settings
from app.db import get_db
from app.models import Alert, Budget, MerchantCategory, Recommendation, Subscription, Upload
from app.services.alerts import generate as generate_alerts
from app.services.categories import kind_for_category
from app.services.ingestion import MAX_BYTES, CsvValidationError, parse_csv, preview_csv
from app.services.insights import potential_savings, regenerate
from app.services.normalizer import safe_display
from app.services.renewals import sub_out, upcoming
from app.services.summary import summarize, trend
from app.uploads import get_worker

router = APIRouter(
    prefix="/api/v1",
    responses={
        401: {"model": s.ErrorEnvelope},
        404: {"model": s.ErrorEnvelope},
        409: {"model": s.ErrorEnvelope},
        413: {"model": s.ErrorEnvelope},
        422: {"model": s.ErrorEnvelope},
        429: {"model": s.ErrorEnvelope},
    },
)
Db = Annotated[object, Depends(get_db)]
CurrentUser = Annotated[object, Depends(auth.get_current_user)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def fail(status, code, message):
    raise HTTPException(status, {"code": code, "message": message})


def require_owned(db, user_id, model, object_id):
    record = repo.get_owned(db, user_id, model, object_id)
    if record is None:
        fail(404, "not_found", "Record not found")
    return record


def lock_user(db, user_id):
    if repo.get_user(db, user_id, lock=True) is None:
        fail(401, "unauthorized", "Invalid or expired credentials")


@router.post("/auth/register", response_model=s.UserOut, status_code=201, tags=["auth"])
def register(body: s.Register, request: Request, db: Db):
    try:
        user = auth.register_user(db, str(body.email).lower(), body.password.get_secret_value())
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "registration_conflict", "Unable to register with that email")
    return user


@router.post("/auth/login", response_model=s.Token, tags=["auth"])
def login(body: s.Login, request: Request, db: Db):
    user = auth.credentials_user(db, str(body.email).lower(), body.password.get_secret_value())
    if user is None:
        fail(401, "invalid_credentials", "Invalid email or password")
    return s.Token(
        access_token=auth.issue_token(user.id), expires_in=get_settings().jwt_access_minutes * 60
    )


@router.get("/auth/me", response_model=s.UserOut, tags=["auth"])
def me(user: CurrentUser):
    return user


async def read_file(file: UploadFile) -> bytes:
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    if len(data) > MAX_BYTES:
        fail(413, "file_too_large", "CSV exceeds the 5 MB limit")
    return data


def validate_csv(data, mapping=None):
    try:
        parsed = parse_csv(data, mapping)
    except CsvValidationError as exc:
        fail(422, "invalid_csv", str(exc))
    if any(tx.currency != "INR" for tx in parsed.transactions):
        fail(422, "unsupported_currency", "Only INR transactions are supported in this phase")
    return parsed


@router.post("/uploads/preview", response_model=s.Preview, tags=["uploads"])
async def preview(user: CurrentUser, file: UploadFile = File(...)):
    """Bounded preview without persistence. Confirm the suggested mapping on upload."""
    data = await read_file(file)
    try:
        result = preview_csv(data)
    except CsvValidationError as exc:
        fail(422, "invalid_csv", str(exc))
    mapping = result["suggested_mapping"]
    # Unknown columns need a mapping step, not a failed preview.
    warnings = []
    malformed_count = 0
    try:
        parsed = parse_csv(data, mapping)
        malformed_count = parsed.skipped_count
        warnings = [dict(line=e.line, reason=e.reason) for e in parsed.errors[:100]]
    except CsvValidationError:
        warnings = [
            dict(line=1, reason="Confirm date, description and amount/type or debit/credit mapping")
        ]
    formats = set()
    date_column = mapping.get("date")
    if date_column in result["columns"]:
        index = result["columns"].index(date_column)
        for row in result["rows"]:
            if len(row) > index:
                for fmt, label in (
                    ("%Y-%m-%d", "YYYY-MM-DD"),
                    ("%d/%m/%Y", "DD/MM/YYYY"),
                    ("%d-%m-%Y", "DD-MM-YYYY"),
                    ("%d %b %Y", "DD MMM YYYY"),
                ):
                    try:
                        datetime.strptime(row[index], fmt)
                        formats.add(label)
                    except ValueError:
                        pass
    return dict(
        **result,
        date_formats=sorted(formats),
        warnings=warnings,
        malformed_count=malformed_count,
        remainder_notice=s.UploadOut.model_fields["remainder_notice"].default,
    )


@router.post("/uploads", response_model=s.UploadOut, status_code=202, tags=["uploads"])
async def upload(
    user: CurrentUser,
    db: Db,
    request: Request,
    file: UploadFile = File(...),
    mapping: str = Form(...),
    worker=Depends(get_worker),
    as_of=Depends(today),
):
    """Submit a confirmed mapping JSON object; poll GET /uploads/{id} for real progress.

    Example mapping: {"date":"date","description":"description","amount":"amount","type":"type"}.
    Processing is atomic for transactions, detections and charge links.
    Safe row warnings are capped at 100.
    """
    try:
        selected = json.loads(mapping)
        if (
            not isinstance(selected, dict)
            or not selected
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in selected.items())
        ):
            raise ValueError
    except (ValueError, TypeError):
        fail(422, "invalid_mapping", "Mapping must be a JSON object of field-to-column names")
    data = await read_file(file)
    # File validation is bounded; heavy inserts and detection happen in the worker.
    from starlette.concurrency import run_in_threadpool

    parsed = await run_in_threadpool(validate_csv, data, selected)
    if worker is None or not worker.reserve():
        fail(429, "upload_queue_full", "Upload queue is full; retry after current uploads finish")
    try:
        record = repo.create_owned(
            db,
            user.id,
            Upload,
            filename=safe_display(
                (file.filename or "upload.csv").replace("\\", "/").split("/")[-1]
            )[:255],
            total_rows=parsed.row_count,
            row_count=parsed.row_count,
        )
        db.commit()
        response = s.UploadOut.model_validate(record)
    except IntegrityError:
        db.rollback()
        worker.release()
        fail(401, "unauthorized", "Account no longer exists")
    except Exception:
        db.rollback()
        worker.release()
        raise
    # Dispatch after writing 202, so pending is observable without artificial sleeps.
    from fastapi.responses import JSONResponse
    from starlette.background import BackgroundTask

    task = BackgroundTask(worker.submit, user.id, record.id, data, selected, as_of=as_of)
    return JSONResponse(status_code=202, content=response.model_dump(mode="json"), background=task)


@router.get("/uploads", response_model=s.Page[s.UploadOut], tags=["uploads"])
def uploads(user: CurrentUser, db: Db, limit: Limit = 20, offset: Offset = 0):
    return dict(
        items=repo.list_owned(
            db, user.id, Upload, offset=offset, limit=limit, order_by=Upload.uploaded_at.desc()
        ),
        total=repo.count_owned(db, user.id, Upload),
        limit=limit,
        offset=offset,
    )


@router.get("/uploads/{upload_id}", response_model=s.UploadOut, tags=["uploads"])
def upload_detail(upload_id: uuid.UUID, user: CurrentUser, db: Db):
    return require_owned(db, user.id, Upload, upload_id)


@router.get("/subscriptions", response_model=s.Page[s.SubscriptionOut], tags=["subscriptions"])
def subscriptions(
    user: CurrentUser,
    db: Db,
    status: s.Status | None = None,
    category: s.Category | None = None,
    cadence: s.Cadence | None = None,
    kind: s.Kind | None = None,
    sort: Literal["merchant", "avg_amount", "next_expected", "confidence"] = "merchant",
    direction: Literal["asc", "desc"] = "asc",
    limit: Limit = 20,
    offset: Offset = 0,
):
    conditions = [
        getattr(Subscription, field) == value
        for field, value in (
            ("status", status),
            ("category", category),
            ("cadence", cadence),
            ("kind", kind),
        )
        if value is not None
    ]
    column = getattr(Subscription, sort)
    order = column.desc() if direction == "desc" else column.asc()
    return dict(
        items=[
            sub_out(item)
            for item in repo.list_owned(
                db, user.id, Subscription, *conditions, offset=offset, limit=limit, order_by=order
            )
        ],
        total=repo.count_owned(db, user.id, Subscription, *conditions),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/subscriptions/{subscription_id}", response_model=s.SubscriptionDetail, tags=["subscriptions"]
)
def subscription_detail(
    subscription_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    charges_limit: Limit = 50,
    charges_offset: Offset = 0,
):
    record = require_owned(db, user.id, Subscription, subscription_id)
    charges = repo.subscription_charges(db, user.id, subscription_id)
    return s.SubscriptionDetail(
        **sub_out(record).model_dump(),
        charges_total=len(charges),
        charges_limit=charges_limit,
        charges_offset=charges_offset,
        charges=[
            s.ChargeOut(
                id=tx.id,
                date=tx.date,
                description=safe_display(tx.raw_description),
                amount=tx.amount,
                currency=tx.currency,
                type=tx.type,
            )
            for tx in charges[charges_offset : charges_offset + charges_limit]
        ],
    )


@router.patch(
    "/subscriptions/{subscription_id}", response_model=s.SubscriptionOut, tags=["subscriptions"]
)
def patch_subscription(
    subscription_id: uuid.UUID,
    body: s.SubscriptionPatch,
    user: CurrentUser,
    db: Db,
    as_of=Depends(today),
):
    lock_user(db, user.id)
    record = require_owned(db, user.id, Subscription, subscription_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "last_used_at" and value and value > as_of:
            fail(422, "invalid_last_used", "Last used date cannot be in the future")
        setattr(record, key, value)
        if key == "category":
            record.category_overridden = True
            record.requires_confirmation = value == "unknown"
            record.kind = kind_for_category(value)
        elif key == "user_confirmed" and value:
            record.requires_confirmation = False
        elif key == "status":
            record.cancelled_at = datetime.now(timezone.utc) if value == "cancelled" else None
    record.requires_confirmation = record.category == "unknown" and not record.user_confirmed
    regenerate(db, user.id, as_of=as_of)
    generate_alerts(db, user.id, as_of=as_of, now=datetime.now(timezone.utc))
    db.commit()
    return sub_out(record)


@router.get("/summary", response_model=s.Summary, tags=["summary"])
def summary(user: CurrentUser, db: Db, period: Literal["month", "year"] = "month"):
    return summarize(db, user.id, period=period)


@router.get("/summary/trend", response_model=s.Trend, tags=["summary"])
def summary_trend(
    user: CurrentUser, db: Db, months: Annotated[int, Query(ge=1, le=60)] = 12, as_of=Depends(today)
):
    return trend(db, user.id, months=months, as_of=as_of)


@router.get("/renewals/upcoming", response_model=s.Page[s.SubscriptionOut], tags=["renewals"])
def renewals(
    user: CurrentUser,
    db: Db,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Limit = 20,
    offset: Offset = 0,
    as_of=Depends(today),
):
    items = upcoming(db, user.id, days=days, as_of=as_of)
    return dict(items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset)


@router.get("/budget", response_model=s.BudgetOut, tags=["budget"])
def budget(user: CurrentUser, db: Db):
    records = repo.list_owned(db, user.id, Budget, limit=1)
    return dict(monthly_limit=records[0].monthly_limit if records else None)


@router.put("/budget", response_model=s.BudgetOut, tags=["budget"])
def put_budget(body: s.BudgetPut, user: CurrentUser, db: Db, as_of=Depends(today)):
    lock_user(db, user.id)
    records = repo.list_owned(db, user.id, Budget, limit=1)
    if records:
        records[0].monthly_limit = body.monthly_limit
    else:
        repo.create_owned(db, user.id, Budget, monthly_limit=body.monthly_limit)
    generate_alerts(db, user.id, as_of=as_of, now=datetime.now(timezone.utc))
    db.commit()
    return dict(monthly_limit=body.monthly_limit)


@router.get("/settings/alerts", response_model=s.AlertSettingsOut, tags=["settings"])
def settings(user: CurrentUser):
    cfg = get_settings()
    return s.AlertSettingsOut(
        lead_time_days=user.alert_lead_days,
        notification_email=user.notification_email,
        enabled=user.alerts_enabled,
        delivery_mode=cfg.notifier_provider,
        delivery_notice=(
            "Development mode: emails are saved to a private outbox, not delivered to an inbox."
            if cfg.notifier_provider == "console"
            else "Email delivery is configured via SMTP. Check recent alerts for delivery status."
        ),
    )


@router.put("/settings/alerts", response_model=s.AlertSettingsOut, tags=["settings"])
def put_settings(body: s.AlertSettings, user: CurrentUser, db: Db, as_of=Depends(today)):
    lock_user(db, user.id)
    user.alert_lead_days = body.lead_time_days
    user.notification_email = (
        str(body.notification_email).lower() if body.notification_email else None
    )
    user.alerts_enabled = body.enabled
    generate_alerts(db, user.id, as_of=as_of, now=datetime.now(timezone.utc))
    db.commit()
    return settings(user)


@router.get("/categories/unconfirmed", response_model=s.Page[s.CategoryOut], tags=["categories"])
def unconfirmed(user: CurrentUser, db: Db, limit: Limit = 20, offset: Offset = 0):
    return dict(
        items=repo.all_unconfirmed(db, user.id, offset=offset, limit=limit),
        total=repo.count_owned(
            db, user.id, MerchantCategory, MerchantCategory.confirmed.is_(False)
        ),
        limit=limit,
        offset=offset,
    )


@router.patch("/categories/{category_id}", response_model=s.CategoryOut, tags=["categories"])
def patch_category(
    category_id: uuid.UUID, body: s.CategoryPatch, user: CurrentUser, db: Db, as_of=Depends(today)
):
    lock_user(db, user.id)
    record = require_owned(db, user.id, MerchantCategory, category_id)
    result = repo.confirm_category(db, user.id, record.merchant, body.category)
    regenerate(db, user.id, as_of=as_of)
    generate_alerts(db, user.id, as_of=as_of, now=datetime.now(timezone.utc))
    db.commit()
    return result


@router.delete("/me/data", response_model=s.DeleteResult, tags=["privacy"])
def delete_my_data(user: CurrentUser, db: Db):
    """Atomically delete the account and its owned records. Its tokens stop working."""
    lock_user(db, user.id)
    from app.services.notifier import ConsoleNotifier, DeliveryError

    try:
        ConsoleNotifier(get_settings().outbox_dir).purge(user.id)
    except (OSError, DeliveryError):
        fail(503, "outbox_unavailable", "Could not remove private outbox copies; please retry")
    counts = repo.delete_data(db, user.id)
    db.commit()
    return dict(deleted=counts)


def recommendation_out(record):
    return s.RecommendationOut(
        **{
            name: getattr(record, name)
            for name in s.RecommendationOut.model_fields
            if name != "members"
        },
        members=record.facts.get("members", []),
    )


@router.get(
    "/recommendations", response_model=s.Page[s.RecommendationOut], tags=["recommendations"]
)
def recommendations(
    user: CurrentUser,
    db: Db,
    status: s.RecommendationStatus | None = None,
    type: s.RecommendationType | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    conditions = [
        getattr(Recommendation, name) == value
        for name, value in (("status", status), ("type", type))
        if value is not None
    ]
    return dict(
        items=[
            recommendation_out(row)
            for row in repo.list_owned(
                db,
                user.id,
                Recommendation,
                *conditions,
                limit=limit,
                offset=offset,
                order_by=Recommendation.created_at.desc(),
            )
        ],
        total=repo.count_owned(db, user.id, Recommendation, *conditions),
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/recommendations/{recommendation_id}",
    response_model=s.RecommendationOut,
    tags=["recommendations"],
)
def patch_recommendation(
    recommendation_id: uuid.UUID, body: s.RecommendationPatch, user: CurrentUser, db: Db
):
    lock_user(db, user.id)
    record = require_owned(db, user.id, Recommendation, recommendation_id)
    if record.status == "resolved":
        fail(409, "resolved_recommendation", "This recommendation no longer applies")
    target = "accepted" if body.action == "accept" else "dismissed"
    if record.status != target:
        record.status = target
        record.decisions = {**record.decisions, record.facts_hash: target}
        if target == "accepted":
            record.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return recommendation_out(record)


@router.get("/summary/savings", response_model=s.SavingsOut, tags=["summary"])
def savings(user: CurrentUser, db: Db):
    return dict(potential_savings=potential_savings(db, user.id))


@router.get("/alerts", response_model=s.Page[s.AlertOut], tags=["alerts"])
def alerts(user: CurrentUser, db: Db, limit: Limit = 20, offset: Offset = 0):
    return dict(
        items=repo.list_owned(
            db,
            user.id,
            Alert,
            limit=limit,
            offset=offset,
            order_by=Alert.last_attempt_at.desc().nullslast(),
        ),
        total=repo.count_owned(db, user.id, Alert),
        limit=limit,
        offset=offset,
    )


@router.get("/alerts/{alert_id}", response_model=s.AlertOut, tags=["alerts"])
def alert_detail(alert_id: uuid.UUID, user: CurrentUser, db: Db):
    return require_owned(db, user.id, Alert, alert_id)
