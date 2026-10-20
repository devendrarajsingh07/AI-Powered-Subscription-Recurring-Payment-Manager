# SubTrack — current state and coding-agent handoff

Updated 2026-10-20. The repository root is the workspace; do not create a nested subtrack folder.

## Current state

Phases 1–7 were released as v1.0.0 at 7dba254a2f84b62f525ee39595b1dfe907a03d04.
The tag is published. It means demo-complete for that scope, not production-ready.
Release/tag CI passed, including all 13 browser flows on Ubuntu:
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39368517177

The owner supplied a combined Phases 7/7.5/8 prompt. Additional Part 1 Gemini requirements
are implemented and locally verified; hosted CI on the addendum must pass before Part 2. After Part 2, stop before Part 3
and request the Vercel/domain/container-host/managed-PostgreSQL/email/paid-Gemini prerequisites.
Do not invent accounts or deploy/invite real users automatically.

Stack unchanged: React/Vite/TypeScript/Tailwind/Recharts/TanStack Query/Router,
FastAPI/SQLAlchemy/Alembic/PostgreSQL16. Decimal money, decimal-string APIs, Alembic only.
Gemini is the sole live adapter; fake remains offline default. No live evaluation has run.
Recommendations/emails remain deterministic. No original statements or real user data in git.
Local web http://localhost:5173; API http://localhost:8000/docs. Development-only demo login:
subtrack-demo@example.org / SubTrackDemo2026!. make seed is implemented and idempotent.
After .env copy: docker compose up --build --wait, then make seed.

## Current verification

Combined baseline: ignored var/combined-baseline-20261020-095823/.
make dev, verify, test, lint, evaluate exit0. 287 PostgreSQL backend tests,46 frontend tests;
OpenAPI/TypeScript drift pass. Detector TP/FP/FN: synthetic16/0/0, handwritten bank3/0/0,
handwritten products5/0/0; precision/recall/F1=1.0000 each. Real-bank accuracy is unmeasured.
make e2e Windows:10 passed,3 failed; Firefox157 native launch fails before app execution.
The redundant available-engine baseline rerun had9 pass/1 fail: mapping preview state was lost
during a Vite reconnect while generated types were being written. Subsequent edits and browser
checks were serialized. Stable final addendum run:10/10 Chromium/WebKit flows pass. No browser
is removed and no assertions weakened. Ubuntu release checks/e2e passed; addendum CI pending.

Codex Process Jobs refused win32 as unsupported, so normal command execution is used. A local
Firefox repair copied the exact manifest embedded in its mozglue DLL to a sidecar. Launch still
failed, so that sidecar was removed and the original installation restored.

## Part 1 addendum — decisions before implementation

- Reuse Gemini and consent-reset migration0007. Do not rebuild the demo loader, repeat migrations,
  rewrite history or move published v1.0.0. New additive requirements get separate commits.
- Keep existing httpx REST transport. LLM_MODEL must be explicitly configured; no guessed default.
  Exactly fake|gemini. Key remains SecretStr in x-goog-api-key header, never URL/query/log output.
- Rechecked the official sources below on 2026-10-20. Sanitize schemas only at the adapter boundary:
  inline local references, keep a documented conservative subset, strip unsupported keywords.
  Server-side extra=forbid Pydantic validation stays authoritative and unchanged.
- Categorization uses constrained JSON structured output and server-side enum validation. Its only
  user data is the normalized merchant. Suggestions remain unconfirmed and never override choices.
- Process parallel function calls in provider order within existing caps. Malformed arguments become
  safe tool errors consuming a round; they never reach repositories. Five-round cap stays.
- Blocked, empty or truncated completions discard buffered model text and yield deterministic fallback
  with verified=false. No unverified token reaches the browser. Retry transient failures only, with
  existing bounds; cancellation closes upstream. Test with local HTTP, never live keys in CI.
  Unknown tools/extra identity fields still fail closed; only malformed wire-argument markers get
  the recoverable tool-error path. Existing injection/identity tests remain intact.
- Consent names Google Gemini and discloses tier differences. Unpaid Services terms permit product
  improvement and human review and prohibit sensitive/personal submissions. Paid Services terms
  exclude improvement use but permit limited safety/legal retention. The app cannot infer key tier.
  Operator must read the applicable terms before sending financial data; offline stays default.
- Active docs/errors/contract metadata name the configured provider; historical facts live under
  docs/history. Do not reapply superseded no-remote or phase-stop instructions from those logs.

Official sources (no live model calls):
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/function-calling
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/billing
- https://ai.google.dev/gemini-api/terms

## Limits and human-owned checks

Compose is dev/demo, not production. One API process; in-process workers/scheduler/limiters/chat gate,
no durable queue; INR only; nominal renewal dates; figure verification proves provenance, not prose.
SMTP is at-least-once across accepted-send/commit crashes. Exported/delivered data cannot be recalled.
Human screen-reader, private real-statement checks, and live Gemini evaluation remain unperformed.
Owner selected MIT; explicit instructions leave LICENSE absent for owner application.

Prior release audits: npm0/pip no known vulnerabilities; Gitleaks has three exact reviewed historical
synthetic JWT exceptions, no unreviewed findings. No .env/outbox/eml/private statements tracked.
Re-run scans for each new part; historical results do not certify new changes.

History preserving decisions/results/failures:
- [Phases1–5](docs/history/PHASES_1_5.md)
- [Phase6](docs/history/PHASE_6.md)
- [Phase7 release](docs/history/PHASE_7.md)

Priority: correct numbers > data safety > working demo > polish > extra features.
Part 2 is pending. Part 3 requires the external-prerequisite handoff after Part 2.

## Part 1 addendum verification — 2026-10-20

Logs: var/combined-part1-20261020-102403/ (ignored). make dev/verify/test/evaluate exit0;
307 real PostgreSQL tests,46 frontend tests,18 independent offline questions; OpenAPI/TS drift pass.
Initial focused run53 pass/2 fail: disclosure assertion wording and too-broad invalid-tool recovery.
Both were fixed, preserving fail-closed user-id rejection; focused rerun55 pass, then one wire-schema
test added and the full307 passed. No known-answer expected values or evaluator were changed.

First make lint/build failed because the generated response type required provider in the typed
MSW fixture. Added explicit fake/gemini fixture providers. Repeated make lint, npm --prefix frontend
run build, npm --prefix frontend test -- --run all exit0 (46 tests). No source changes during the
stable browser verification: python scripts/run_e2e.py --project=chromium --project=webkit exit0,
10 passed (Chromium7/WebKit3). Hosted all-browser result must be recorded before Part 2.

npm --prefix frontend audit --audit-level=low:0 vulnerabilities. pip-audit against requirements.lock
in disposable Python3.12 container: no known vulnerabilities. Gitleaks full32-commit history: no
unreviewed findings, retaining only the3 exact historical synthetic-test exceptions. Post-commit scan
must include the addendum. No .env/private statements/eml/LICENSE tracked; .env.example only.
Production bundle: main346.56KB/109.50KB gzip; lazy charts389.93KB/114.22KB gzip, unchanged.
One existing Starlette TestClient deprecation warning remains. No live Gemini, real-bank or human
screen-reader claim. Do not move v1.0.0; this is an additive post-release correction.
