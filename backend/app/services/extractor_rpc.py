"""Bounded Unix-only client. The parser receives no identity, DB credential or live-AI key."""

import base64
import json
from time import monotonic

import httpx

from app.config import get_settings
from app.schemas import StatementResult
from app.services.statement_extraction import ExtractionError

SAFE_ERRORS = {
    "password_required": "Enter the PDF password and retry.",
    "wrong_password": "PDF password was not accepted; check it and retry.",
    "too_many_pages": "PDF exceeds the page limit; split it before upload.",
    "low_quality": "The scan needs a clearer export; use CSV if possible.",
    "unreadable": "No readable transaction table; use a clearer export or CSV.",
}


def call(
    data,
    filename,
    *,
    password="",
    preflight=False,
    progress=lambda *args: None,
    cancelled=lambda: False,
):
    cfg = get_settings()
    if len(data) > cfg.statement_max_mb * 1024 * 1024 or len(password) > 256:
        raise ExtractionError("file_too_large", "Input exceeds its configured limit.")
    payload = json.dumps(
        {
            "data": base64.b64encode(data).decode(),
            "filename": filename,
            "password": password,
        },
        separators=(",", ":"),
    ).encode()
    transport = httpx.HTTPTransport(uds=str(cfg.extractor_socket))
    started = monotonic()
    limit = (15 if preflight else 8) * 1024 * 1024
    buffered, total = b"", 0
    try:
        with httpx.Client(transport=transport, timeout=httpx.Timeout(5, read=2)) as client:
            with client.stream(
                "POST",
                "http://subtrack-extractor/" + ("preflight" if preflight else "extract"),
                content=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status_code != 200:
                    raise ExtractionError("extractor_unavailable", "Parser is busy; retry shortly.")
                for chunk in response.iter_bytes():
                    if cancelled():
                        raise ExtractionError("cancelled", "Processing was cancelled safely.")
                    if monotonic() - started > cfg.statement_timeout_seconds + 5:
                        raise ExtractionError(
                            "extraction_timeout", "Parser exceeded its time limit."
                        )
                    total += len(chunk)
                    buffered += chunk
                    if total > limit + 65536:
                        raise ValueError
                    while b"\n" in buffered:
                        line, buffered = buffered.split(b"\n", 1)
                        event = json.loads(line)
                        kind = event.get("event")
                        if kind == "heartbeat":
                            continue
                        if kind == "progress":
                            done, pages = event["processed_pages"], event["total_pages"]
                            if (
                                type(done) is not int
                                or type(pages) is not int
                                or not 0 <= done <= pages <= cfg.statement_max_pages
                            ):
                                raise ValueError
                            progress(done, pages)
                        elif kind == "error":
                            code = event.get("code")
                            raise ExtractionError(
                                code if code in SAFE_ERRORS else "extraction_failed",
                                SAFE_ERRORS.get(
                                    code, "Statement could not be read safely; use CSV."
                                ),
                            )
                        elif kind == "result":
                            if preflight:
                                result = base64.b64decode(event["result"]["pdf"], validate=True)
                                if (
                                    not result.startswith(b"%PDF-")
                                    or len(result) > 10 * 1024 * 1024
                                ):
                                    raise ValueError
                                return result
                            result = StatementResult.model_validate(event["result"])
                            if len(result.rows) > 5000 or len(result.warnings) > 100:
                                raise ValueError
                            return result.model_dump(mode="json")
                        else:
                            raise ValueError
    except ExtractionError:
        raise
    except httpx.HTTPError:
        raise ExtractionError(
            "extractor_unavailable", "Parser is unavailable; retry shortly."
        ) from None
    except (ValueError, TypeError, KeyError):
        raise ExtractionError(
            "invalid_worker_output", "Statement could not be read safely; use CSV."
        ) from None
    raise ExtractionError("invalid_worker_output", "Parser ended without a complete result.")
