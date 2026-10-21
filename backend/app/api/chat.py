"""Authenticated chat and explicit consent; no write tools or trigger endpoint."""

import asyncio
import uuid

from fastapi import Depends, Query, Request
from fastapi.responses import StreamingResponse

from app import models as m
from app import repositories as repo
from app import schemas as s
from app.api.routes import CurrentUser, Db, Limit, Offset, fail, lock_user, require_owned, router
from app.clock import today
from app.config import get_settings
from app.services import llm_controls as controls
from app.services.chat import DISCLOSURE, clear_history, gate, stream_turn
from app.services.chat_tools import clean
from app.services.llm import get_client
from app.services.normalizer import normalize_merchant


@router.get("/chat/config", response_model=s.ChatConfig, tags=["chat"])
def chat_config(user: CurrentUser, db: Db):
    cfg = get_settings()
    reason = controls.peek(db.get_bind()) if cfg.llm_provider != "fake" else None
    return dict(
        mode="offline" if cfg.llm_provider == "fake" or reason else "live",
        provider=cfg.llm_provider,
        live_opt_in=user.live_opt_in,
        disclosure=DISCLOSURE,
        fallback_reason=reason,
    )


@router.put("/chat/config", response_model=s.ChatConfig, tags=["chat"])
def chat_consent(body: s.ChatConsent, user: CurrentUser, db: Db):
    lock_user(db, user.id)
    user.live_opt_in = body.live_opt_in
    db.commit()
    return chat_config(user, db)


def check_consent(user, client=None, engine=None):
    live = controls.is_live(client) if client is not None else get_settings().llm_provider != "fake"
    # A killed or capped provider is answered offline and sends nothing, so it needs no consent.
    if live and not user.live_opt_in and not (engine is not None and controls.peek(engine)):
        fail(400, "consent_required", "Enable live AI consent before sending data to Google Gemini")


@router.post(
    "/chat",
    tags=["chat"],
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE status, then verified final; error on failure. "
            "No unverified token events. Shapes: ChatStatus, ChatFinal, ChatStreamError.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        400: {"model": s.ErrorEnvelope},
        503: {"model": s.ErrorEnvelope},
    },
)
async def chat(
    body: s.ChatRequest,
    request: Request,
    user: CurrentUser,
    db: Db,
    as_of=Depends(today),
    client=Depends(get_client),
):
    if not body.message.strip():
        fail(400, "empty_message", "Enter a question about your recurring payments")
    # Consent is only required when data would actually leave: a killed or capped live provider
    # is answered by the offline assistant, which sends nothing anywhere.
    engine = db.get_bind()
    check_consent(user, client, engine)
    conversation_id = body.conversation_id or uuid.uuid4()
    if body.conversation_id and not repo.count_owned(
        db, user.id, m.ChatMessage, m.ChatMessage.conversation_id == conversation_id
    ):
        fail(404, "not_found", "Conversation not found")
    engine, user_id = db.get_bind(), user.id
    db.rollback()  # Release auth/history read transaction before the asynchronous stream.
    lease_token = gate.acquire(user_id, engine=engine)
    # Only after validation and per-user admission. Routing counts nothing; each provider
    # request reserves shared capacity itself, so rejected requests never consume quota.
    client, fallback_reason = controls.route(engine, client)
    return StreamingResponse(
        stream_turn(
            request,
            engine,
            user_id,
            conversation_id,
            body.message,
            as_of,
            client,
            lease_token,
            fallback_reason,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/history", response_model=s.Page[s.ChatHistory], tags=["chat"])
def history(
    user: CurrentUser,
    db: Db,
    limit: Limit = 20,
    offset: Offset = 0,
    conversation_id: uuid.UUID | None = Query(default=None),
):
    conditions = [m.ChatMessage.conversation_id == conversation_id] if conversation_id else []
    total = repo.count_owned(db, user.id, m.ChatMessage, *conditions)
    if conversation_id and not total:
        fail(404, "not_found", "Conversation not found")
    rows = repo.list_owned(
        db,
        user.id,
        m.ChatMessage,
        *conditions,
        limit=limit,
        offset=offset,
        order_by=m.ChatMessage.created_at.desc(),
    )
    return dict(
        items=[
            dict(
                id=row.id,
                conversation_id=row.conversation_id,
                role=row.role,
                content=row.content,
                verified=row.verified,
                created_at=row.created_at,
                tools=[item["name"] for item in (row.tool_calls or [])],
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/chat/history", response_model=s.ClearedHistory, tags=["chat"])
def delete_history(user: CurrentUser, db: Db):
    lock_user(db, user.id)
    if gate.is_busy(user.id, engine=db.get_bind()):
        fail(409, "chat_busy", "Stop the current answer before clearing history")
    count = clear_history(db, user.id)
    db.commit()
    return dict(deleted=count)


@router.post("/categories/{category_id}/suggest", response_model=s.CategoryOut, tags=["categories"])
async def suggest_category(
    category_id: uuid.UUID, user: CurrentUser, db: Db, client=Depends(get_client)
):
    check_consent(user, client, db.get_bind())
    lock_user(db, user.id)
    row = require_owned(db, user.id, m.MerchantCategory, category_id)
    if row.confirmed or row.category != "unknown" or row.suggestion_attempted:
        return row
    if not repo.count_owned(
        db,
        user.id,
        m.Subscription,
        m.Subscription.merchant == row.merchant,
        m.Subscription.requires_confirmation.is_(True),
    ):
        return row
    user_id = user.id
    merchant = clean(normalize_merchant(row.merchant))
    engine = db.get_bind()
    lease_token = gate.acquire(user_id, db=db)
    try:
        client, _ = controls.route(engine, client)
        # Reserve before the single provider request, after validation and per-user admission.
        # A killed or capped provider sends nothing and leaves the one-time attempt unused.
        if controls.is_live(client) and controls.reserve(engine, controls.estimate(merchant)):
            controls.note(engine, "fallbacks")
            return row
        if controls.is_live(client) and hasattr(client, "before_request"):
            client.before_request = lambda: controls.guard(
                engine, client, controls.estimate(merchant)
            )
        row.suggestion_attempted = True
        db.commit()  # Claim once, including failed requests; no financial data crosses boundary.
        try:
            async with asyncio.timeout(get_settings().llm_timeout_seconds):
                suggestion = await client.categorize(merchant)
        except Exception:
            suggestion = None
        lock_user(db, user_id)
        row = require_owned(db, user_id, m.MerchantCategory, category_id)
        if (
            suggestion in s.Category.__args__
            and suggestion != "unknown"
            and not row.confirmed
            and row.source != "user"
        ):
            row.category, row.source = suggestion, "llm"
        db.commit()
        return row
    finally:
        db.rollback()
        gate.release(user_id, lease_token, engine=engine)
