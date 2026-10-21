# Phase8 Step0 and WP3 verification log

2026-10-21. This is evidence/history, not an instruction source. See PROJECT_INFO for current work.

## Security first

Incident evidence/limits and exact owner rotation procedure: ../SECURITY_INCIDENT.md.
Gitleaks8.30.1 full history44 commits/2.26MB exit0 with3 exact prior synthetic JWT exceptions.
Broad directory scan10 matches: ignored .env2, installed SQLAlchemy6, scanner README2; no values printed.
Current-source scan2.25MB exit0 after account changes. No tracked .env/outbox/.eml or real statements.
Render PostgreSQL network page checked: all internet traffic blocked by database-level inbound rules.
Public local-demo credential login probe401; it does not prove whether the row existed. New startup
purge emits only `shared_before`/`removed` counts so hosted verification can establish that fact.
The first new hosted deployment must be checked; rotation remains OWNER ACTION PENDING.
Successor fixture-fix run39401421431 on19f0098: completed/success, rechecked through GitHub public API.

An attempted environment-only close-registration save was rejected by automatic approval review:
deployment prerequisite not yet met. The draft was cancelled; no environment change/deployment
occurred. Wait for this package's full local gates and hosted CI before returning to hosted changes.

## Implemented decisions

Canonical decisions: ../PHASE8_ACCOUNT_SECURITY.md; next package is PLANNED only in
../PHASE8_DURABLE_PLAN.md. Architecture/stack/provider unchanged. Additive migrations0011/0012.
Production remains unconditionally blocked. No paid resources, live Gemini, real invitations or beta tag.
Strict refresh cookies use exact Origin/CSRF; public cross-site demo uses no refresh cookie and no
password registration/login/file uploads. Local shared seed refuses public-demo-only mode.
All OCR/CSV/detection/financial algorithms remain unchanged.

## Commands/results

- `make dev`, `make verify`: exit0; healthy real PostgreSQL/API/web, Alembic at head.
- `make test`: full406 PostgreSQL tests passed in234.57s,67 frontend tests; detector/extraction and
  OpenAPI/TS drift gates pass. Two further malformed-CSRF cases entered the frozen final run.
- `make lint`, `make evaluate`: exit0; backend/frontend lint/typecheck and3 detector sets pass.
- Synthetic16/0/0, handwritten bank3/0/0, handwritten products5/0/0 TP/FP/FN; each P/R/F1=1.0000.
- `npm --prefix frontend run build`: exit0; main352.42kB/111.03gzip, lazy chart389.93kB/114.22gzip.
- `npm --prefix frontend audit --audit-level=low`: exit0,0 findings after network-authorized rerun.
- `pip-audit -r backend/requirements.lock --disable-pip`: initially1 certifi advisory
  PYSEC-2026-4320, fixed by regenerating Linux hash lock with only certifi2026.10.19 updated.
  Repeated audit exit0, no known vulnerabilities. Missing local pip/audit tooling was installed in
  the ignored venv; no application dependency was added.
- Official Playwright1.64.1 Linux runner with Docker CLI/Make, sharing web network namespace and
  localhost5173, actual stack, explicit APP_TEST_AS_OF2026-10-18 then restored: **16 passed/5.7min**
  (Chromium10,Firefox3,WebKit3).2 configuration-specific tests intentionally run separately below.
- `python scripts/prepare_auth_tls.py`; `docker compose -f docker-compose.yml -f
  docker-compose.auth-test.yml up --build --wait`; E2E_LOCAL_TLS=1 and sibling app/api.subtrack.test
  HTTPS browser: **1 passed/17.2s**. Actual verification/outbox code, cookie flags/reload/rotation,
  reset and revocation. No system trust installation or deployed validation relaxation.
- Public-demo Compose overlay; E2E_PUBLIC_DEMO=1 browser: **1 passed/10.9s**. Two isolated visitors,
  actual loader, independent ground-truth product count, direct CSV/PDF/PNG uploads rejected,
  no refresh cookie, mobile light/dark axe, reload loses disposable session, own-data cleanup.
- CI now includes full-history/current-source secret scan, normal three-engine flows, explicit
  public-demo and TLS jobs. Hosted result is pending publication, not claimed green here.

## Failures corrected without weakening assertions

Initial focused backend66 pass/1 structural OpenAPI failure: enumerate only deliberate pre-auth
account endpoints; cookie endpoints document actual APIKeyCookie security, business guard retained.
New account tests initially19 passed. Initial purge test used an expired ORM identity after deletion;
capture its UUID before deletion instead. A verification-gate expectation exposed a generic401;
the gate now returns a clear403 and rejects existing unverified access before upload.
One interrupted full run had181 pass/1 failure; it was not accepted as full evidence.

Windows sandbox blocked Git helper/full scan and Vitest temp renames; reran with reviewed access.
The partial10-commit scan and6 non-started frontend suites were not counted as passing checks.
First TLS browser attempt exposed CSP blocking its explicitly configured API; allow that exact
origin in dev CSP. No wildcard or cookie relaxation. First normal-browser attempt exposed normal
anonymous bootstrap401 console noise and reused login rate bucket causing session loss during
page audits. Bootstrap now returns null normally with no cookie; refresh stays authenticated and
CSRF-protected. Session endpoints have a separate PostgreSQL rate bucket; tests cover it.
The next run15 pass/1 failure exposed a test race reading cancellation before DELETE completed;
await the real response, preserving cancelled/null-payload assertions. Full rerun16 passed.
First public-demo test had an ambiguous Upload link selector; scope Main navigation, unchanged controls.

## Pending receipts

Final frozen full gate completed:408 PostgreSQL tests passed in259.91s,67 frontend tests;
make dev/verify/test/lint/evaluate and OpenAPI/TS drift exit0. Expanded recovery-page mobile
light/dark accessibility/responsive browser audit1 passed in57.9s.
Commits, new hosted CI and actual deployment/control probes must be recorded before advancing to WP4. The beta is blocked by both remaining code and external prerequisites.

Hosted run39620266005 exposed a TLS test navigation race; diagnostic successor39621040811
confirmed no login request was sent. Its screenshot shows a blank required email field. Both
recovery and login pages have an email input, so the test filled the departing recovery field
before navigation committed. Wait for the sign-in heading before filling the destination form;
retain response200/cookie/revocation assertions. No product security change or timeout increase.

Corrected TLS navigation flow rerun locally:1 passed in13.6s (test9.5s); normal Compose
configuration restored. Hosted checks/secrets passed on both earlier runs, TLS failed as recorded;
full e2e still running at this checkpoint. No deployment or master promotion occurred.

The full hosted e2e run39620266005 had15 pass/1 failure: the accessibility audit repeatedly
reloaded every route and exhausted the shared60/min CSRF bootstrap bucket. Parsed failure trace
statuses (no headers/tokens/content printed) showed seven /auth/csrf429 responses. The page audit
now uses actual accessible navigation for internal routes, keeps full reloads for theme/width entry
and404, and asserts every destination URL. Dedicated TLS reload tests remain. Real limits are
unchanged; no reset, raised cap or extra retry hides abuse controls.

Navigation-based mobile light/dark/all-width audit rerun:1 passed in51.8s. Hosted successor
39622053051 moved past cookie reload/logout, then exposed the same repeated-email-field race
entering reset from login. Add the reset heading wait too; no security change.

Both recovery-route waits verified locally:TLS1 passed in15.9s; normal stack restored.
Navigation audit1 passed in51.8s; TypeScript build clean. Product code remains unchanged from
the408/67 full gate; hosted checks rerun on the successor test commit before promotion.
