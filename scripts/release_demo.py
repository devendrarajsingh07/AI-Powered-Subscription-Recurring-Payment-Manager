"""Release one verified commit to the free demo and prove that commit is what is serving.

Run only by .github/workflows/deploy.yml after the SHA was verified (on master, green push CI).
Order: API first (migrations are additive, so the new API serves the old frontend), then the
frontend. Exits non-zero if either host does not serve SHA in time, so the job fails visibly.

- Render: deploy hook with `ref=<SHA>` deploys exactly that commit (and, per Render, disables
  auto-deploy, leaving releases to this pipeline). Success = /health reports `revision == SHA`
  AND /health/ready is 200. An old healthy instance can never satisfy this.
- Vercel: hooks cannot target a commit, so the pipeline finds the READY production build Vercel
  made for SHA from git and promotes it via the REST API. Success = /version.json reports SHA.

Secrets are read from the environment and never printed.
RELEASE_MODE=api releases only Render; Vercel's separate exact-CI/API build gate handles the web.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = int(os.environ.get("RELEASE_TIMEOUT_SECONDS", 15 * 60))
POLL = float(os.environ.get("RELEASE_POLL_SECONDS", 15))
VERCEL_API = os.environ.get("VERCEL_API", "https://api.vercel.com")  # Overridable for tests.
SHA = os.environ.get("SHA", "")


def env(name, required=True):
    value = os.environ.get(name, "").strip()
    if required and not value:
        sys.exit(f"::error::{name} is not configured")
    return value


def call(url, method="GET", token=None, timeout=30):
    headers = {"User-Agent": "subtrack-release", "Cache-Control": "no-cache"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        request = urllib.request.Request(
            url, method=method, headers=headers, data=b"" if method == "POST" else None
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(1_000_000)
            return response.status, json.loads(body) if body.strip().startswith(
                (b"{", b"[")
            ) else {}
    except urllib.error.HTTPError as error:
        return error.code, {}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, {}


def wait(description, check):
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if check():
            print(f"OK {description}")
            return
        time.sleep(POLL)
    sys.exit(f"::error::Timed out waiting for {description}; nothing was rolled forward further")


def release_api():
    hook, api = env("RENDER_HOOK"), env("API_URL").rstrip("/")
    separator = "&" if "?" in hook else "?"
    status, _ = call(hook + separator + "ref=" + SHA, "POST")
    if status not in (200, 201, 202):
        sys.exit(f"::error::Render deploy hook was refused (HTTP {status})")
    print("Render deploy requested for", SHA)

    def serving():
        live_status, body = call(api + "/health")
        ready_status, _ = call(api + "/health/ready")
        return live_status == 200 and body.get("revision") == SHA and ready_status == 200

    wait(f"API to serve {SHA} and be ready", serving)


def release_web():
    token, project, web = env("VERCEL_TOKEN"), env("VERCEL_PROJECT_ID"), env("WEB_URL").rstrip("/")
    team = env("VERCEL_TEAM_ID", required=False)
    scope = ("&teamId=" + urllib.parse.quote(team)) if team else ""

    def serving():
        status, body = call(web + "/version.json?ts=" + str(int(time.time())))
        return status == 200 and body.get("revision") == SHA

    if serving():
        print("OK frontend already serves", SHA)
        return
    found = {}

    def built():
        query = urllib.parse.urlencode(
            dict(projectId=project, sha=SHA, target="production", limit=5)
        )
        status, body = call(VERCEL_API + "/v7/deployments?" + query + scope, token=token)
        if status != 200:
            return False
        states = [d.get("readyState") or d.get("state") for d in body.get("deployments", [])]
        if states and all(state in ("ERROR", "CANCELED") for state in states):
            sys.exit(f"::error::Vercel build for {SHA} failed")
        ready = [
            d
            for d in body.get("deployments", [])
            if (d.get("readyState") or d.get("state")) == "READY"
        ]
        if ready:
            found["uid"] = ready[0]["uid"]
        return bool(ready)

    wait(f"a READY Vercel production build of {SHA}", built)
    if not re.fullmatch(r"dpl_[A-Za-z0-9]+", found["uid"]):
        sys.exit("::error::Unexpected Vercel deployment id")
    url = f"{VERCEL_API}/v10/projects/{urllib.parse.quote(project)}/promote/{found['uid']}"
    status, _ = call(url + ("?" + scope[1:] if scope else ""), "POST", token=token)
    if status not in (200, 201, 202):
        sys.exit(f"::error::Vercel promotion was refused (HTTP {status})")
    wait(f"frontend to serve {SHA}", serving)


def main():
    if not re.fullmatch(r"[0-9a-f]{40}", SHA):
        sys.exit("::error::SHA must be a verified full commit id")
    mode = os.environ.get("RELEASE_MODE", "full")
    if mode not in ("full", "api"):
        sys.exit("::error::RELEASE_MODE must be full or api")
    release_api()
    if mode == "api":
        print("Released API", SHA)
        return
    release_web()
    print("Released", SHA)


if __name__ == "__main__":
    main()
