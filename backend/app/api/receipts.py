"""Offline receipt foundation only. No OAuth, mailbox access or automatic confirmation."""

from fastapi import File, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app import auth
from app import schemas as s
from app.api.routes import CurrentUser, Db, fail, read_file, router
from app.services.email_receipts import MAX_BYTES, ReceiptError, parse_receipt
from app.services.receipt_previews import create, require_enabled
from app.services.statement_previews import output


@router.post("/receipts/preview", response_model=s.StatementPreviewOut, tags=["receipts"])
async def receipt_preview(
    user: CurrentUser, db: Db, request: Request, file: UploadFile = File(...)
):
    """Development-only synthetic EML → unverified rows. Import via POST /uploads after review.

    No original bytes, headers or email addresses are persisted. Attachments are not parsed.
    Gmail is not connected. Existing preview status/cancel routes apply; every row requires an
    explicit verified edit. Receipt/statement histories cannot share an account until reconciled.
    """
    require_enabled()
    auth.limiter.check(request, "receipt-preview:" + str(user.id))
    form = await request.form()
    if set(form) != {"file"} or len(form.getlist("file")) != 1:
        fail(422, "invalid_receipt_request", "Provide exactly one EML file and no extra fields")
    data = await read_file(file, limit=MAX_BYTES, label="EML receipt")
    if not (file.filename or "").lower().endswith(".eml"):
        fail(422, "unsupported_receipt", "Choose a synthetic .eml receipt file")
    try:
        result = await run_in_threadpool(parse_receipt, data)
    except ReceiptError as exc:
        fail(413 if exc.code == "receipt_too_large" else 422, exc.code, str(exc))
    return output(create(db, user.id, result))
