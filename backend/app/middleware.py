"""Bound HTTP upload bodies and prevent exception/SQL parameters from reaching logs."""

import logging

from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartParser
from starlette.requests import Request

from app.auth import limiter
from app.config import get_settings

logger = logging.getLogger("subtrack.api")
MAX_MULTIPART_BYTES = 5 * 1024 * 1024 + 64 * 1024
EARLY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=15552000",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "Cache-Control": "no-store",
}


class SafetyMiddleware:
    def __init__(self, app):
        self.app = app
        # Bodies are bounded before parsing; keep originals/passwords out of framework spool files.
        MultiPartParser.spool_max_size = 10 * 1024 * 1024 + 64 * 1024

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        lab_write = (scope["method"] in ("POST", "PUT", "PATCH")
                     and (scope["path"].startswith("/api/v1/mailbox/")
                          or scope["path"] == "/api/v1/interests"))
        if lab_write and (not get_settings().mailbox_lab_enabled
                          or get_settings().public_demo_only):
            return await JSONResponse(status_code=404, headers=EARLY_HEADERS, content={
                "error": {"code": "mailbox_disabled", "message": "Mailbox lab is disabled"}
            })(scope, receive, send)
        if lab_write:
            chunks, size = [], 0
            while True:
                part = await receive()
                chunks.append(part)
                size += len(part.get("body", b""))
                if size > 32768:
                    return await JSONResponse(status_code=413, headers=EARLY_HEADERS, content={
                        "error": {"code": "request_limit", "message": "Request exceeds its limit"}
                    })(scope, receive, send)
                if not part.get("more_body", False):
                    break
            original_receive = receive

            async def lab_receive():
                return chunks.pop(0) if chunks else await original_receive()

            receive = lab_receive
        if (
            get_settings().public_demo_only
            and scope["method"] == "POST"
            and scope["path"]
            in (
                "/api/v1/uploads",
                "/api/v1/uploads/preview",
                "/api/v1/receipts/preview",
            )
        ):
            # Refuse before reading bytes or parsing multipart, including chunked requests.
            return await JSONResponse(
                status_code=403,
                headers=EARLY_HEADERS,
                content={
                    "error": {
                        "code": "demo_data_only",
                        "message": "File uploads are disabled in the public demo. "
                        "Load synthetic demo data instead.",
                    }
                },
            )(scope, receive, send)
        if (
            scope["method"] == "POST"
            and scope["path"] == "/api/v1/receipts/preview"
            and not get_settings().receipt_import_enabled
        ):
            return await JSONResponse(
                status_code=404,
                headers=EARLY_HEADERS,
                content={
                    "error": {
                        "code": "receipt_import_disabled",
                        "message": "Receipt-import development foundation is disabled",
                    }
                },
            )(scope, receive, send)
        if scope["method"] == "POST" and scope["path"] in (
            "/api/v1/auth/register",
            "/api/v1/auth/login",
        ):
            try:
                limiter.check(Request(scope), scope["path"].rsplit("/", 1)[-1])
            except HTTPException as exc:
                response = JSONResponse(
                    status_code=exc.status_code,
                    content={"error": exc.detail},
                    headers={**EARLY_HEADERS, **(exc.headers or {})},
                )
                return await response(scope, receive, send)
        if scope["method"] == "POST" and scope["path"] in (
            "/api/v1/uploads",
            "/api/v1/uploads/preview",
            "/api/v1/receipts/preview",
        ):
            # Bound even chunked bodies before multipart can spool arbitrary data to disk.
            chunks, total = [], 0
            maximum = (
                1024 * 1024 + 64 * 1024
                if scope["path"] == "/api/v1/receipts/preview"
                else 10 * 1024 * 1024 + 64 * 1024
                if scope["path"].endswith("/preview")
                else MAX_MULTIPART_BYTES
            )
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                total += len(message.get("body", b""))
                if total > maximum:
                    response = JSONResponse(
                        status_code=413,
                        headers=EARLY_HEADERS,
                        content={
                            "error": {
                                "code": "file_too_large",
                                "message": "Receipt exceeds the 1 MB upload limit"
                                if scope["path"] == "/api/v1/receipts/preview"
                                else "Statement exceeds the preview upload limit"
                                if maximum != MAX_MULTIPART_BYTES
                                else "CSV exceeds the 5 MB upload limit",
                            }
                        },
                    )
                    return await response(scope, receive, send)
                chunks.append(message)
                if not message.get("more_body", False):
                    break
            original_receive = receive

            async def bounded_receive():
                return chunks.pop(0) if chunks else await original_receive()

            receive = bounded_receive
        started = False

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-frame-options", b"DENY"),
                        (b"strict-transport-security", b"max-age=15552000"),
                    ]
                )
                if scope["path"].startswith("/api/v1/") and not any(
                    name.lower() == b"cache-control" for name, _ in headers
                ):
                    headers.append((b"cache-control", b"no-store"))
                if scope["path"] not in ("/docs", "/redoc"):
                    headers.append(
                        (
                            b"content-security-policy",
                            b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                        )
                    )
                message = dict(message, headers=headers)
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception:
            # No exception strings/tracebacks/SQL bind values: these can contain financial data.
            logger.error(
                "Request failed; request_id=%s", scope.get("state", {}).get("request_id", "none")
            )
            if not started:
                response = JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "code": "internal_error",
                            "message": "Request failed safely; try again later",
                        }
                    },
                )
                await response(scope, receive, send)
