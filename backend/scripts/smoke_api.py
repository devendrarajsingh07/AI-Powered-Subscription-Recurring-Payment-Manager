"""Exercise real HTTP register/login/preview/upload/summary and delete the synthetic account.

Runs from the API container against the running API, without exposing its token or credentials.
"""

import json
import os
import secrets
import time
import uuid
from pathlib import Path

import httpx


def main():
    base = os.environ.get("SMOKE_API_BASE_URL", "http://api:8000/api/v1")
    credential = {
        "email": f"smoke-{uuid.uuid4().hex}@example.org",
        "password": "Smoke42!" + secrets.token_urlsafe(18),
    }
    headers = None
    with httpx.Client(base_url=base + "/", timeout=30) as client:
        registration = client.post("auth/register", json=credential)
        registration.raise_for_status()
        login = client.post("auth/login", json=credential)
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        try:
            data = (
                Path(__file__).resolve().parents[1] / "data" / "sample_transactions.csv"
            ).read_bytes()
            preview = client.post(
                "uploads/preview",
                headers=headers,
                files={"file": ("sample_transactions.csv", data)},
            )
            preview.raise_for_status()
            upload = client.post(
                "uploads",
                headers=headers,
                files={"file": ("sample_transactions.csv", data)},
                data={"mapping": json.dumps(preview.json()["suggested_mapping"])},
            )
            upload.raise_for_status()
            assert upload.status_code == 202
            upload_id = upload.json()["id"]
            deadline = time.monotonic() + 45
            while True:
                progress = client.get(f"uploads/{upload_id}", headers=headers)
                progress.raise_for_status()
                result = progress.json()
                if result["status"] in ("done", "failed"):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Smoke upload timeout")
                time.sleep(0.1)
            assert result["status"] == "done", "Smoke upload failed"
            assert result["inserted_count"] == 399
            subscriptions = client.get("subscriptions?limit=100", headers=headers)
            subscriptions.raise_for_status()
            assert subscriptions.json()["total"] == 16
            summary = client.get("summary", headers=headers)
            summary.raise_for_status()
            assert summary.json()["subscriptions"]["count"] == 12
            assert summary.json()["fixed_bills"]["count"] == 4
            print(
                "PASS real HTTP register/login/preview/upload/summary: "
                "399 transactions, 16 products"
            )
        finally:
            if headers:
                response = client.delete("me/data", headers=headers)
                response.raise_for_status()
                assert response.json()["deleted"]["users"] == 1
                print("PASS smoke account and all owned data deleted")


if __name__ == "__main__":
    main()
