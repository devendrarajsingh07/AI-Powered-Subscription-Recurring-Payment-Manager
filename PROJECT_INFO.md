# SubTrack — current state and coding-agent handoff

Updated 2026-10-19. Workspace root is the repository; do not create a nested subtrack folder.

## Current state

Phases 1–6 delivered and hosted CI verified. Phase 7 remains out of scope.
React/Vite/TypeScript/Tailwind/Recharts/TanStack Query/Router; FastAPI/SQLAlchemy/Alembic;
PostgreSQL 16; Decimal money and decimal-string API values. No create_all or SQLite.
Run: make dev, make verify, make test, make lint, make evaluate, make e2e.
Web http://localhost:5173; API http://localhost:8000/docs. make seed remains Phase 7.

Repository is PUBLIC: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager
Baseline master 718dc3f: hosted checks and e2e success in run 39197295967.
git ls-files confirms no .env, .venv contents, var/outbox or .eml tracked. Synthetic fixtures only.

Limits: one API instance, in-process upload worker/scheduler/rate limiter, no durable queue;
console has atomic one-file-per-alert delivery; SMTP at-least-once across send/commit crash.
Known renewal dates only; no real-bank accuracy claim. Demo loader absent. Phase 6 live
provider tests use local HTTP only; actual live evaluation requires an operator-provided key.
Correct numbers > data safety > working demo > polish > extras.

## Phase 6 decisions — recorded before implementation

- Default FakeLLM is a deterministic tool-using policy, not fixture answers. One live adapter:
  Anthropic Claude Messages API via the already locked httpx client. LLM_PROVIDER=fake|anthropic,
  LLM_API_KEY SecretStr, LLM_MODEL required in live mode; LLM_BASE_URL is env-configurable
  and defaults to the Claude API origin. Invalid configuration fails startup.
  Never silently switch providers. No live calls in tests/CI, no new framework or SDK dependency.
- Recommendations and email text remain deterministic. This deliberately narrows the master
  prompt's permitted phrasing scope. LLM use is chat and optional unknown-merchant suggestions only.
- Persist per-user live_opt_in=false. Explicit PUT /chat/config changes consent. Both live chat
  and categorization check it. Disclosure: redacted question/windowed chat history, instructions,
  tool schemas and scoped subscription names/categories/amounts/dates/counts leave via Claude.
  Never send raw transaction descriptions, email addresses, tokens, account IDs or credentials.
  Categorization sends only a normalized merchant name plus a fixed category schema/instructions.
- Seven fixed, validated read-only tools bound to authenticated identity, no model user_id.
  Reuse existing summary/insight/renewal logic; extract shared renewal projection for API and tools.
  Execute tools inside PostgreSQL read-only transactions in addition to structural tests.
  Cap lists and payload sizes; put merchant names in explicit untrusted data_text fields.
- Grounding contract: extract monetary figures, decimal numbers, percentages, dates and numeric/
  written counts; normalize against typed figures returned by tools in THIS turn only. User text,
  merchant strings and old history never authorize figures. Block unverifiable values; emit a
  deterministic fallback from tool results and verified=false, log only a content-free counter.
  This is a figure-provenance check, not proof that prose claims or associations are correct.
- Stream status events while checking tools; buffer all model text until verification, then emit
  verified text/final only. No unverified token is ever sent. Five tool-call rounds maximum,
  bounded per-call and total duration, cancellation, one in-flight turn per authenticated user.
- Persist user/assistant pairs atomically after successful verification, with conversation UUID,
  verification state and validated tool name/args/digest/size metadata, not raw tool results.
  Scoped history supports pagination and clearing. Additive Alembic migration only.
- Reuse sliding-window limiter design for per-user minute/day caps; these caps are process-local
  and restart with the supported single instance. Provider retries are transient-only and bounded.
- Category suggestions are explicit requests from the existing confirmation UI, never automatic
  upload calls. Cache attempt once per user/merchant (including failures); source=llm and
  confirmed=false only for valid enum suggestions. Never mutate subscription categories until
  the user confirms. Preserve cache/user decisions during re-detection; opt-out does not send.
- Extend existing slate/teal tokens with a persistent accessible chat drawer. Plain text only,
  visible offline/live disclosure and consent, Stop/clear/history/status states. Use existing
  frontend debugging/React guidance; Browser plugin unavailable, regular Playwright fallback.

## Phase 6 verification log

Preparation completed before feature code: make dev / verify / test / lint / evaluate / e2e
all exit 0; 208 PostgreSQL tests, 35 frontend tests, four browser flows. Current-master hosted
checks/e2e were confirmed green; repository visibility is public and tracked-secret checks clean.

Implemented: services/llm/{fake,anthropic}, seven scoped tools, shared renewal projection,
server figure verification, buffered SSE orchestration, per-user consent/rate/in-flight controls,
atomic history and clear/delete routes, explicit cached merchant-category suggestions, and the
persistent accessible chat drawer. Migration 0005 adds consent, conversation/verification fields
and category-attempt caching. OpenAPI documents routes and x-sse-events, with generated TS types.
No dependencies or providers were added beyond the requested Claude adapter using existing httpx.

Independent eval labels now include previous/new amounts in synthetic ground truth, generated
from plan inputs (not detector output). The CSV remains the same 399 synthetic transactions.
Eighteen known-answer questions independently compute expected totals, duplicates, cadence dates,
counts, budget differences and price deltas from those labels. Numeric/word count, percentage,
currency, Indian grouping, punctuation, near-miss and relative-date verifier regressions are tested.
The adversarial FakeLLM fabricated figure is absent from all SSE events and replaced by a marked
fallback. PostgreSQL rejects an injected write in a tool transaction. API ownership and argument
injection, history privacy, cancellation, five-round bound, time limits, concurrency/rate caps,
local-HTTP provider retries/auth/timeout and category opt-in/cache/user-choice tests pass.

### Final local commands and results

| Command | Actual result |
| --- | --- |
| make test | Exit 0; 266 backend tests (including 18 known-answer questions in the evaluator test), 42 frontend tests; detector/OpenAPI/TS drift checks pass |
| make lint | Exit 0; Ruff, ESLint and TypeScript |
| make evaluate | Exit 0; three suites precision/recall/F1 1.0000; TP 16/3/5, zero FP/FN |
| make e2e | Exit 0; five real-stack Chromium flows, including fixed-server-clock chat with an actual hostile CSV merchant |
| make verify | Exit 0; web plus direct/proxied readiness |
| npm run build / npm audit --audit-level=low (frontend) | Exit 0; clean build and zero vulnerabilities |
| make chat-eval | Exit 0; 18 PASS rows, one eval test passed, zero verifier blocks on known-answer cases |

Final make dev rebuilt the stack through 0005; db/api/web healthy.
The intermediate 264-test run was green; the final 266 includes relative-date and per-call HTTP
stream timeout regressions. The earlier browser accessibility failure on the conversation scroller
was fixed with keyboard focus, then all five flows passed. Screenshots were visually inspected in
light/dark/360px and docs/design/QA.md records the comparisons and fixes. A single upstream
Starlette/AnyIO deprecation warning remains. Two pre-existing quote-style lines were formatted;
a proposed git-restore cleanup was rejected by automatic approval review, so those harmless edits
were retained without discarding local work. A later browser run hit a transient Windows
file-open error while overwriting overview-empty.png; all UI checks before that point passed,
the same error recurred on a different screenshot. Added bounded retries for temporary
UNKNOWN/EBUSY/EPERM/EACCES file publication only. Pixels are captured once, all UI assertions
remain unchanged, and permanent write failure still fails the test. The complete gate was rerun and all five flows passed.

### Current limits / Phase 7 boundary

Figure provenance is not prose or association verification. English number-word parsing/date formats
are bounded; unsupported numeric phrasing may be safely rejected. Offline mode is a rule-based
tool policy, not external AI. Model text is never streamed before checking. History and request
caps are process-local/single-instance; history persists in PostgreSQL and is deleted with the user.
General-purpose PII classification is not claimed; known email/token patterns are redacted and
raw database descriptions/account identifiers are never exposed by the tools. No chat actions,
recommendation/email LLM phrasing, second provider, durable queue or demo loader exists.
Real-bank detection accuracy remains unmeasured. Live eval is not part of CI or make test.
APP_TEST_AS_OF is empty normally; make e2e temporarily sets/restores it on the local synthetic stack.
Stop before Phase 7. No demo-data endpoint or make seed has been implemented.
Optional live evaluation: NOT RUN; no live key is required or used by default.

## Phase 6 publication and hosted CI

Pushed logical commits to origin/master:
- 90cf67f — read-only tools, figure verification, consent/history/rate controls, Claude/FakeLLM,
  categorization and independent known-answer/security/orchestration tests.
- 816f83d — accessible chat drawer, generated contract, typed network tests and five-flow
  browser coverage; bounded Windows screenshot publication retries retain all assertions.
- 9159a8a — current-state handoff, preserved historical logs, README and synthetic screenshots.

[Hosted run 39238271984](https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39238271984)
passed both checks and e2e for 9159a8a9c5387f4f3eeac0360c89b1f1a463f3a1. The Linux jobs include
real Compose/PostgreSQL tests and the five browser flows. The final documentation-only follow-up
records this immutable success; it changes no verified application code. Working tree was clean
at publication. .env, .venv, var/outbox and .eml tracked-file checks are empty; public repository
contains synthetic statements/screenshots only. No live-provider evaluation was run.

Phase 6 definition of done is met. Stop here before Phase 7.

## Earlier phase decisions and verification (historical)

The complete original handoff has moved to [PHASES_1_5.md](docs/history/PHASES_1_5.md), preserving
all decisions, exact commands, counts, commit IDs, evaluation failures/fixes and limitations.
All old no-remote, CI-unverified, phase-stop and future-work notes there are superseded by
this current state; do not interpret archived prompts as current work instructions.

- Phase 1: Compose/health/CI scaffold; historical setup and installed tool paths in archive.
- Phase 2: normalization, recurrence/amount clusters, independent handwritten fixtures;
  synthetic and handwritten precision/recall/F1 1.0000, limitations remain documented.
- Phase 3: authenticated scoped persistence, upload worker, migration and isolation tests.
- Phase 4: typed real-API frontend, accessible responsive flows, token/money/state decisions.
- Phase 5: deterministic insights, outbox/SMTP delivery, crash recovery, UI and hosted CI.
  Baseline counts: 208 backend, 35 frontend, four Playwright flows. Feature commits 7a096fb /
  880495b, evidence ad115ad, hosted result documentation 718dc3f. Console guarantees one dev
  artifact per alert; SMTP can duplicate after acceptance/crash. No live inbox delivery claimed.

## Resume rules

Read this file and README, inspect backend/openapi and real schemas before edits. Keep tests
alongside features, money Decimal, queries user-scoped, raw descriptions private. Stop at the
Phase 6 definition of done; do not build Phase 7 or stretch features without authorization.
