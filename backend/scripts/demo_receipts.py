"""Disposable LOCAL synthetic demo through HTTP -> preview/review -> real durable ingestion."""

import json
import secrets
import sys
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402


def main():
    cfg = get_settings()
    if (
        cfg.environment != "development"
        or cfg.public_demo_only
        or not cfg.receipt_import_enabled
        or cfg.llm_provider != "fake"
        or cfg.require_email_verification
        or cfg.legal_acceptance_required
    ):
        print(
            "Receipt demo needs local development, offline assistant "
            "and RECEIPT_IMPORT_ENABLED=true."
        )
        print(
            "It refuses public/production mode, verification mail and unapproved legal acceptance."
        )
        return 1
    directory = Path(__file__).resolve().parents[1] / "data" / "receipts"
    truth = json.loads((directory / "ground_truth.json").read_text(encoding="utf-8"))
    with httpx.Client(base_url="http://localhost:8000/api/v1/", timeout=20) as client:
        token = None

        def checked(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if not response.is_success:
                raise RuntimeError(f"Demo API step failed: {response.status_code}")
            return response.json()

        def ingest(name):
            row = checked(
                "POST",
                "receipts/preview",
                files={"file": (name, (directory / name).read_bytes(), "message/rfc822")},
            )
            assert row["source_type"] == "email_receipt" and row["status"] == "ready"
            upload = checked(
                "POST",
                "uploads",
                data={
                    "preview_id": row["id"],
                    "edits": json.dumps([{"index": 0, "verified": True}]),
                },
            )
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = checked("GET", "uploads/" + upload["id"])
                if state["status"] == "done":
                    return state
                if state["status"] == "failed":
                    raise RuntimeError("Synthetic import failed")
                time.sleep(0.2)
            raise RuntimeError("Synthetic import deadline exceeded")

        try:
            mode = checked("GET", "auth/config")
            if mode["public_demo_only"] or mode["legal_acceptance_required"]:
                raise RuntimeError("Local API is not in the permitted test profile")
            credentials = {
                "email": f"receipt-fixture-{uuid.uuid4().hex}@example.org",
                "password": secrets.token_urlsafe(24) + "A1!",
            }
            checked("POST", "auth/register", json=credentials)
            token = checked("POST", "auth/login", json=credentials)["access_token"]
            client.headers["Authorization"] = "Bearer " + token
            files = [name for name, case in truth["cases"].items() if case.get("detect")]
            for name in files:
                assert ingest(name)["inserted_count"] == 1
            plans = checked("GET", "subscriptions?limit=100")["items"]
            assert sorted((s["merchant"], s["cadence"], s["avg_amount"]) for s in plans) == sorted(
                (p["merchant"], p["cadence"], p["avg_amount"]) for p in truth["patterns"]
            )
            annual = sum(
                Decimal(p["avg_amount"]) * (12 if p["cadence"] == "monthly" else 1)
                for p in truth["patterns"]
            )
            monthly = (annual / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            summary = checked("GET", "summary")
            assert (summary["monthly_equivalent"], summary["yearly_total"]) == (
                str(monthly),
                format(annual, ".2f"),
            )
            repeated = ingest(files[0])
            assert repeated["inserted_count"] == 0 and repeated["duplicate_count"] == 1
            print(
                f"PASS {len(files)} reviewed receipts; {len(plans)} independently expected products"
            )
            print("PASS independent Decimal totals and duplicate replay; no mailbox/provider calls")
        finally:
            if token:
                checked("DELETE", "me/data")
                print("PASS disposable synthetic account and data deleted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Never dump headers, tokens, message bodies or private HTTP response content.
        print("Receipt demo failed; check local API/worker readiness and feature settings.")
        raise SystemExit(1) from None
