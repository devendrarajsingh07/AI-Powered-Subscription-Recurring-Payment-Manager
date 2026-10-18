"""Bound HTTP upload bodies and prevent exception/SQL parameters from reaching logs."""

import logging

from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.auth import limiter

logger = logging.getLogger("subtrack.api")
MAX_MULTIPART_BYTES = 5 * 1024 * 1024 + 64 * 1024


class SafetyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] == "POST" and scope["path"] in (
            "/api/v1/auth/register",
            "/api/v1/auth/login",
        ):
            try:
                limiter.check(Request(scope), scope["path"].rsplit("/", 1)[-1])
            except HTTPException as exc:
                response = JSONResponse(
                    status_code=exc.status_code, content={"error": exc.detail}, headers=exc.headers
                )
                return await response(scope, receive, send)
        if scope["method"] == "POST" and scope["path"] in (
            "/api/v1/uploads",
            "/api/v1/uploads/preview",
        ):
            # Bound even chunked bodies before multipart can spool arbitrary data to disk.
            chunks, total = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                total += len(message.get("body", b""))
                if total > MAX_MULTIPART_BYTES:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "file_too_large",
                                "message": "CSV exceeds the 5 MB upload limit",
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
