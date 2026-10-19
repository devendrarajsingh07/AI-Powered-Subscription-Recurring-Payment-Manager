# SubTrack — current state and coding-agent handoff

Updated 2026-10-19. Workspace root is the repository; do not create a nested subtrack folder.

## Current state

Phases 1–7 demo scope implemented and verified. Release publication is gated on green hosted CI
for the tagged commit; v1.0.0 denotes demo-complete, not production-ready.
Stack unchanged: React/Vite/TypeScript/Tailwind/Recharts/TanStack Query/Router,
FastAPI/SQLAlchemy/Alembic/PostgreSQL16. Decimal money; decimal-string APIs. Never create_all.
One live provider is now Gemini per explicit owner instruction; fake remains offline default.
No live evaluation was run. Recommendations/emails remain deterministic.

Public origin: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager
Local web http://localhost:5173; API http://localhost:8000/docs. Development-only demo login:
subtrack-demo@example.org / SubTrackDemo2026!. make seed is implemented and idempotent.
Run after .env copy: docker compose up --build --wait, then make seed. No external AI/SMTP at runtime;
initial clone/images/packages require network or caches. See README and docs/DEMO.md.

Current local results: 287 PostgreSQL tests, 46 frontend tests, eighteen independent chat questions;
detector three fixture sets P/R/F1 1.0000. Chromium7 flows and WebKit3 flows passed. Firefox157
cannot launch on this Windows host: native side-by-side assembly mozglue error; no app test ran in
that engine locally. Default suite retains Firefox, and Ubuntu CI installs/runs all3 engines.
Fresh public clone523ce47, separate volumes/project/ports5273+8100: up/seed twice/verify passed,
then both real demo-script and all-page accessibility tests passed. Fast-forwarded to c85418b and
reran the full available-browser suite:10 passed. Exact command evidence: docs/DOD.md.

History scan baseline18 commits clean. Expanded22-commit scan flagged3 synthetic test JWT literals,
reported to owner; never real credentials, no history rewrite. Tests now generate ephemeral values;
.gitleaksignore contains only those exact historical fingerprints. Reviewed scan has no unreviewed
findings. .env/outbox/eml/real statements are not tracked. npm audit0; pip-audit no known vulnerabilities
after security updates/hash-lock regeneration. API/web uid1000; PostgreSQL process uid70.

Known gaps: real-bank accuracy unmeasured; nominal calendar renewal dates; INR only; one API process,
in-process worker/scheduler/limiters, no durable queue; figure verifier checks provenance not prose;
SMTP at-least-once after acceptance/commit crash; exported files/delivered emails cannot be recalled.
Compose/Vite is DEV/DEMO, not a production deployment. Human screen-reader pass and live Gemini eval
not performed. Owner selected MIT; explicit phase instruction leaves LICENSE absent for owner action.

## Phase 7 decisions — recorded before implementation

- Baseline: make dev, verify, test, lint, evaluate and e2e all exit 0: 266 backend,
  42 frontend tests, five Chromium flows; three detector datasets precision/recall/F1 1.0000.
  Hosted master c4d1138 checks/e2e green (run 39238761092). Gitleaks full history:
  18 commits, no leaks. Repository public. No env/outbox/statement files tracked.
- User explicitly chose Gemini for live use: replace Claude with ONE Gemini REST adapter,
  using existing httpx, preserving consent, read-only tools, verification and offline default.
  Historical Claude decisions below are superseded only as to live provider. No live eval run.
  Before publication, revoke existing Claude-era live consent in a forward migration: a previous
  provider's opt-in does not authorize Gemini. Users must explicitly consent to Gemini afterward.
- Generate demo CSV and independent truth relative to application today, deterministic seed 42.
  Feed the existing parser/background worker/detector/persistence/insights and alert planner.
  Reuse the existing demo upload, including its visible as_of, until explicit removal/reload.
  Never shift real data. Loading is refused when real uploads exist; real uploads are refused
  while demo data exists. Scoped removal also defensively preserves any real-origin records.
- Mark uploads with source/as_of and a snapshot of settings changed by demo defaults. Seed
  budget only when absent; notification email only when absent. Restore defaults on removal
  only if unchanged since loading, preserving subsequent user choices. Remove demo-linked
  products only when no real charges remain, then regenerate recommendations/alerts.
- ENVIRONMENT defaults development. Demo endpoints/seed and clock overrides are forbidden
  in production; console notifier and adversarial FakeLLM are forbidden there too. Outside
  development require a strong non-placeholder JWT secret and explicit CORS origin.
- Theme preference light/dark/system is non-sensitive, guarded storage, applied before paint.
  Reuse slate/teal design and existing Playwright fallback (Browser plugin unavailable).
- Compose is a dev/demo deployment, not production guidance. SMTP remains at-least-once;
  console atomic outbox is a dev demonstration. No screen-reader, real-bank or live-AI claim.
- License: user selected MIT in the Phase 7 question. Per explicit phase instruction, no
  LICENSE file is added in this phase; record the selection for the owner to apply afterward.

## Verification and resume

Read README, docs/DOD.md and docs/ARCHITECTURE.md for actual results and limits; inspect checked-in
OpenAPI/schemas before code changes. Earlier factual decision logs are preserved in
[Phases1–5](docs/history/PHASES_1_5.md) and [Phase6](docs/history/PHASE_6.md). Their old no-remote,
provider and phase-stop instructions are historical, not current authorization.

Stop after Phase7 release verification. Do not implement stretches without a new user request.
Priorities: correct numbers > data safety > working demo > polish > extra features.


## Phase 7 verification log

Logical commits:2b1f3ad decisions, f9043c5 backend/demo/Gemini/security lock,4244e15 UI/browser checks,
523ce47 docs,3d5f7f9 WebKit focus/reviewed scan findings,c85418b non-development auth guard,
6e3fd76 browser register Retry-After handling. No default limiter was raised for tests.

make dev/verify/seed and seed repeat exit0. Full final make test286 backend+46 frontend,
OpenAPI/TS drift current; make lint/evaluate exit0. Eighteen independent questions pass offline.
Fresh clone has separate new volumes, ports5273/8100 and explicit replay clock18Oct; demo path
and every-view axe light/dark360 pass; all protected routes overflow checks360/768/1280 pass.
Full local Chromium7+WebKit3 pass. Windows Firefox host launch blocked before page execution;
all3 engines remain configured on Ubuntu CI. Corrected real WebKit focus bug without removing checks.

Initial Python audit49 advisory entries in4 packages remediated and hash-lock regenerated:
FastAPI0.147.0, Starlette1.9.0, PyJWT2.15.0, multipart0.0.31, pytest9.0.3; no stack change.
Repeat npm/pip audits clean. Reviewed full-history scan25 commits clean after exactly3 documented
synthetic-test fingerprint exceptions; no real credential/history rewrite. Non-root IDs verified.
Production preview has headers, zero page errors; first DCL sample105ms (single local sample),
main346KB/109KB gzip, lazy charts390KB/114KB gzip. Full limits/measurements are in DOD.

All runtime demo records flow through real ingestion. Production guards include default demo auth
and pre-existing tokens when a dev database is reused outside development. New seed never resets
someone else's password. Delete account/demo purge private console files; exports are not recalled.
No real-bank, screen-reader or live-Gemini evaluation was performed. Owner selected MIT; no LICENSE
file added under explicit Phase7 instruction. Human actions: apply license, screen reader/private
statement/live Gemini checks. No stretch implemented. Hosted source CI is GREEN on 6e3fd76794edbd560698c7bb24adf7be97d54ecb, run39246044919.
Both checks/e2e succeeded, including13 browser flows: Chromium7, Firefox3, WebKit3.
The final documentation/screenshot commit must itself pass hosted CI before pushing v1.0.0.


Hosted evidence: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39246044919
This documentation-only release record changes no verified application code. The release tag's
commit/check association on GitHub is the final publication evidence; never tag a failing commit.
Latest production-build check: main346.56KB (109.50KB gzip), charts389.93KB (114.22KB gzip),
CSS24.93KB (6.25KB gzip); preview DCL96ms in repeat single local sample, headers/zero errors pass.
Final audits repeated: npm0, pip no known vulnerabilities; Gitleaks25 commits no unreviewed findings.

Isolated checkout repeated full make verify/test/lint/evaluate through8ae8845: all exit0,
286 backend+46 frontend, both drift checks, F1=1 across all3 fixture sets. Corrected test-only
assumptions about CORS5173 and inherited replay clocks; production guards remain strict. The
written-demo browser now also opens/closes charges, records music intent without cancellation,
and checks Sent in Settings, matching docs/DEMO.md clicks; local test passed in24.4s.
No screen reader, real statement or live Gemini evaluation claimed. Current release publication
still requires hosted green on the tagged commit. Optional checker never writes bytecode/results.

Final privacy guard: migration0007 resets old Claude-era live consent so Gemini requires a fresh
per-user opt-in. PostgreSQL upgrade0005→head and safe downgrade are tested with an opted-in user.
make dev/verify/test/lint/evaluate after the guard all exit0:287 backend+46 frontend, drift current,
P/R/F1=1.0000 on the3 fixture sets. Earlier286 entries are preserved historical measurements.
