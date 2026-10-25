"""Post-deploy smoke for the hosted demo: health, security headers, exact-origin CORS, SPA routing.

Read-only: it never registers accounts, uploads data or sends credentials. Usage:
    python scripts/smoke_deployed.py --api https://api.example/api/v1 --web https://app.example
Exit code is non-zero on any failed check, so a pipeline can block or roll back.
"""

import argparse
import sys
import urllib.error
import urllib.request

API_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
}
WEB_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def call(url, method="GET", headers=None, timeout=60):
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with OPENER.open(request, timeout=timeout) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            return response.status, headers, response.read(200_000)
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read(200_000)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, {}, str(error).encode()  # Unreachable host: reported as a failed check.


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True, help="API base ending in /api/v1")
    parser.add_argument("--web", required=True, help="Frontend origin")
    args = parser.parse_args(argv)
    api, web = args.api.rstrip("/"), args.web.rstrip("/")
    failures = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
        if not ok:
            failures.append(name)

    status, headers, _ = call(api + "/health", timeout=120)  # Free instances may be waking up.
    check("api health 200", status == 200, str(status))
    status, _, body = call(api + "/health/ready")
    check("api ready 200", status == 200, str(status))
    for key, value in API_HEADERS.items():
        check(f"api header {key}", headers.get(key) == value, str(headers.get(key)))
    csp = headers.get("content-security-policy", "")
    check("api CSP forbids framing", "frame-ancestors 'none'" in csp)
    check("api HSTS", "max-age=" in headers.get("strict-transport-security", ""))

    good = call(
        api + "/auth/config",
        "OPTIONS",
        {"Origin": web, "Access-Control-Request-Method": "GET"},
    )
    check("cors allows exact web origin", good[1].get("access-control-allow-origin") == web)
    check("cors allows credentials", good[1].get("access-control-allow-credentials") == "true")
    for evil in ("https://evil.example", web + ".evil.example"):
        probe = {"Origin": evil, "Access-Control-Request-Method": "GET"}
        bad = call(api + "/auth/config", "OPTIONS", probe)
        check(f"cors refuses {evil}", bad[1].get("access-control-allow-origin") is None)

    status, _, _ = call(api + "/ops/metrics")
    check("ops metrics hidden without token", status == 404, str(status))
    status, _, _ = call(api + "/ops/email-events", "POST")
    check("ops email-events hidden without token", status in (404, 405), str(status))
    status, _, _ = call(api + "/me/export")
    check("private routes require auth", status == 401, str(status))

    status, headers, body = call(web + "/login")
    check("web SPA route 200", status == 200 and b'<div id="root"' in body, str(status))
    for key, value in WEB_HEADERS.items():
        check(f"web header {key}", headers.get(key) == value, str(headers.get(key)))
    policy = headers.get("content-security-policy", "")
    check("web CSP restricts scripts", "script-src 'self'" in policy)
    check("web CSP forbids framing", "frame-ancestors 'none'" in policy)
    status, _, body = call(web + "/unsubscribe?u=x&t=y")
    check("web unsubscribe route serves the SPA", status == 200 and b'<div id="root"' in body)
    status, headers, _ = call(web + "/api/v1/health")
    html = "text/html" in headers.get("content-type", "")
    check("web does not masquerade API paths as HTML", not html)

    print(f"\n{len(failures)} failed" if failures else "\nAll smoke checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
