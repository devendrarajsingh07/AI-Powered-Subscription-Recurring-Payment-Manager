"""Private stdin/stdout relay for real HTTP probes on the isolated Docker drill network."""

import base64
import json
import http.client
import sys
import urllib.error
import urllib.request

value = json.load(sys.stdin)
allowed = {
    "http://api1:8000/api/v1",
    "http://api2:8000/api/v1",
    "http://restore-api:8000/api/v1",
    "http://rollback-api:8000/api/v1",
    "http://web:8080/api/v1",
    "http://web:8080",
}
if value["base"] not in allowed or not value["route"].startswith("/"):
    raise SystemExit("Only isolated drill APIs are allowed")
data = base64.b64decode(value["data"]) if value["data"] is not None else None
request = urllib.request.Request(
    value["base"] + value["route"],
    data=data,
    headers=value["headers"],
    method=value["method"],
)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    response = opener.open(request, timeout=value["timeout"])
except urllib.error.HTTPError as error:
    response = error
except (OSError, urllib.error.URLError):
    print(json.dumps({"status": 0, "type": "application/json", "body": "{}"}))
    raise SystemExit(0) from None
try:
    with response:
        result = {
            "status": response.status,
            "type": response.headers.get_content_type(),
            "retry_after": response.headers.get("Retry-After"),
            "body": response.read(4 * 1024 * 1024).decode(),
        }
except (OSError, http.client.IncompleteRead):
    result = {"status": 0, "type": "application/json", "body": "{}"}
print(json.dumps(result))
