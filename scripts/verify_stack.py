"""Verify the real Compose stack through the web proxy, API, and migration state."""

import json
import os
import urllib.request

web_port = os.environ.get("WEB_PORT", "5173")
api_port = os.environ.get("API_PORT", "8000")
for url in (
    f"http://localhost:{web_port}",
    f"http://localhost:{web_port}/api/v1/health/ready",
    f"http://localhost:{api_port}/api/v1/health/ready",
):
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode()
        assert response.status == 200, url
        if "health/ready" in url:
            assert json.loads(body)["status"] == "ready", url
        else:
            assert '<div id="root">' in body, url
    print(f"PASS {url}")

