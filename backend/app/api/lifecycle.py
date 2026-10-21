"""Email lifecycle and problem reports: unsubscribe, provider events, and a content-safe report."""

import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, EmailStr

from app import auth
from app import models as m
from app import repositories as repo
from app import schemas as s
from app.account_security import audit
from app.api.ops import authorize
from app.api.routes import CurrentUser, Db, fail, lock_user, router
from app.config import get_settings
from app.services import email_lifecycle as lifecycle

# Statements, account/card numbers and amounts do not belong in a problem report.
SENSITIVE = re.compile(
    r"\d{6,}"  # Long digit runs: account, card, reference or phone numbers.
    r"|(?:\d{3,4}[ -]){3}\d{3,4}"  # Grouped card/account numbers.
    r"|(?:₹|\$|€|£|\brs\.?|\binr)\s*\d",  # Currency amounts.
    re.IGNORECASE,
)


class EmailEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: EmailStr
    kind: Literal["hard_bounce", "complaint"]


@router.post("/alerts/unsubscribe", response_model=s.MessageResult, tags=["alerts"])
def unsubscribe(u: str, t: str, request: Request, db: Db):
    """RFC 8058 one-click target. Identical answer for valid and invalid links."""
    auth.limiter.check(request, "unsubscribe")
    user_id = lifecycle.parse_user(u)
    if user_id is not None and lifecycle.verify(user_id, t):
        user = repo.get_user(db, user_id, lock=True)
        if user is not None and user.alerts_enabled:
            user.alerts_enabled = False
            audit(db, user.id, "alert_unsubscribed")
            db.commit()
    return dict(message="If this link was valid, SubTrack alert emails are now turned off.")


@router.post("/ops/email-events", include_in_schema=False, dependencies=[Depends(authorize)])
def email_event(body: EmailEvent, db: Db):
    """Provider-agnostic hook: an operator or adapter reports a hard bounce or complaint."""
    count = lifecycle.suppress(db, str(body.address), body.kind)
    db.commit()
    return dict(suppressed_accounts=count)


@router.post(
    "/support/reports", response_model=s.SupportReportOut, status_code=201, tags=["support"]
)
def report_problem(body: s.SupportReportIn, user: CurrentUser, db: Db):
    if SENSITIVE.search(body.message):
        fail(
            422,
            "sensitive_content",
            "Please describe the problem without statements, account numbers or amounts",
        )
    lock_user(db, user.id)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = repo.count_owned(db, user.id, m.SupportReport, m.SupportReport.created_at >= since)
    if recent >= get_settings().support_reports_per_day:
        fail(429, "rate_limited", "Daily problem-report limit reached; try again tomorrow")
    row = repo.create_owned(
        db, user.id, m.SupportReport, category=body.category, message=body.message.strip()
    )
    audit(db, user.id, "support_report")
    db.commit()
    return dict(id=row.id, received=True)
