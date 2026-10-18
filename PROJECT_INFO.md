# SubTrack — project information and coding-agent handoff

Updated: 2026-10-18 (Asia/Calcutta).

## Phase 3 decisions (recorded before implementation)

- Identity: each subscription has a permanent UUID and a user-scoped unique identity key based on
  normalized merchant/currency/cadence and its initial charge anchor. Re-detection matches existing
  products by greatest charge overlap before creating identities. Average amount is mutable, not
  an identity field, so price changes preserve user decisions. Matching is one-to-one for clusters.
- Concurrency: a PostgreSQL user-row lock serializes ingestion/detection and data deletion for each
  user. Transaction uniqueness remains the authoritative cross-upload dedupe guard. Progress is
  recorded separately; transaction inserts, subscription updates and charge links commit atomically.
  Refined before finalizing the pipeline: use FOR NO KEY UPDATE (SQLAlchemy key_share=True),
  which permits FK key-share checks when another upload queues. Creating the pending upload does
  not acquire the work lock. This prevents a second POST from waiting for long detection work;
  workers and user-decision/deletion operations still serialize on the same user row.
- Tokens: HS256 JWT access tokens only, configurable short expiry, issuer/audience and secret from
  environment. No refresh tokens in this phase. Account deletion removes the user; subsequent access
  using its token fails. No model-supplied IDs or LLM calls exist in Phase 3.
- Background work: bounded in-process worker pool; upload bytes are held only until processing ends.
  Interrupted pending/processing uploads become failed on startup (safe retry; no partial financial
  data). A durable distributed queue is outside this phase. Single API process is supported.
- Category cache is per user/merchant. Generic multi-product merchants may need per-subscription
  overrides; a merchant-level choice deliberately applies across that merchant's products.
- Tests use a separate PostgreSQL database on Compose's PostgreSQL 16 service, never SQLite or the
  developer's application database. Migration lifecycle tests use a dedicated temporary database.
- Housekeeping commits: 190fa80 scaffold, 401a055 detection/CSV, 984c600 data/evaluation.
  No GitHub remote is configured; hosted CI is unverified. `.env`/`.venv` remain ignored.
- Python dependencies are compiled in Linux/Python 3.12 with pip-tools 7.5.2 from requirements.in
  into requirements.lock, including transitive pins and artifact hashes. Docker and CI install
  with --require-hashes. The lock targets the container/Ubuntu CI, not native Windows uvloop.
- Readiness compares the full set of database Alembic revisions to ScriptDirectory.get_heads(),
  not a literal migration ID. Missing schema, stale head and database failure return safe 503.
- Step 0 gate completed: make dev, make verify, make test, make lint, make evaluate all exited 0
  against real Compose; 114 backend tests and 2 frontend tests passed; all three evaluator suites
  retained precision/recall/F1 1.0. No remote exists, so hosted CI is explicitly unverified.

## Read this first

The user requested a complete, demo-ready application, with seven strictly sequential phases.
**Phases 1–3 are implemented and verified. Phase 3 is complete and committed.**
The user requested Phase 3 explicitly, including housekeeping, real PostgreSQL tests, commits and
then stopping before Phase 4. No frontend source was changed in Phase 3.
The full application remains incomplete; Phase 4 business frontend is next after this gate.

The workspace root itself is the `subtrack` repository; do not create a nested duplicate project.
No existing application or user files were present at the beginning.

Priority: correct numbers > data safety > working demo > polish > extra features.
Do not advance to the next phase until the current phase's tests and runtime gate pass.
Do not substitute SQLite for PostgreSQL or another frontend/backend framework.
No subagent delegation was requested; do not let parallel workers edit the same files.

## Implemented files and responsibilities

- `docker-compose.yml`: PostgreSQL 16, API, web; dependency health checks, named database volume.
- `.env.example`: local configuration, plus explicitly reserved future configuration.
- `Makefile`: dev, down, test, lint, verify; seed currently fails explicitly because it is not implemented.
- `backend/app/main.py`: liveness, database + migration readiness, CORS, OpenAPI, validation-error shape.
- `backend/app/config.py`: environment-based settings.
- `backend/app/db.py`: lazy engine, session dependency, declarative Base; no `create_all`.
- `backend/alembic`: explicit baseline and `0002_domain` business migration, tested up/down and drift.
- `backend/tests/test_health.py`: liveness, OpenAPI contract, database failure, CORS.
- `frontend`: React/Vite/TypeScript/Tailwind foundation, Query and Router providers; readiness screen.
- `scripts/verify_stack.py`: real HTTP verification through both public ports and the web API proxy.
- `.github/workflows/ci.yml`: unit checks, lint/type/build, real Compose boot and readiness verification.
- `backend/app/services/normalizer.py`: merchant aliases, rail/reference/noise removal, safe display.
- `backend/app/services/categories.py`: subscription/fixed-bill labels and unknown confirmation flag.
- `backend/app/services/detector.py`: Decimal recurrence statistics, amount clusters, confidence,
  nominal renewal prediction, missed cycles, price-increase signals, underlying charge links.
- `backend/app/services/ingestion.py`: pure CSV preview/mapping/parser, limits and safe row errors.
  Connected to the authenticated background upload pipeline in Phase 3.
- `backend/scripts/gen_sample_data.py`: reproducible synthetic history + independent ground truth.
- `backend/scripts/evaluate_detector.py`: one-to-one product quality metrics and CI gate.
- `backend/data`: generated demo CSV, ground truth, two handwritten bank-shaped fixtures, report.
- `backend/tests/test_detector.py`, `test_ingestion.py`, `test_evaluation.py`: core and data tests.

`/api/v1/openapi.json` is the current API contract: 18 paths, 22 operations, all business routes
JWT-protected. Checked-in JSON and endpoint inventory: `backend/openapi/`. `make openapi` regenerates;
`make test` detects contract drift. Readiness compares database revisions with Alembic script heads.

### Phase 3 implementation map

- `models/__init__.py`: all requested domain tables, ownership/composite FKs, NUMERIC money,
  check-enforced choices, cascading deletion and nullable-budget-alert idempotency index.
- `repositories.py`: user-scoped reads/writes, bulk ON CONFLICT dedupe, overlap-based stable product
  persistence, category cache, complete account deletion. A structure test requires user_id on
  every public repository function. Auth's pre-login account lookup is the documented exception.
- `auth.py`: bcrypt, redacted secret inputs, HS256 issuer/audience/expiry, missing-user dummy hash,
  constant-time bcrypt verification, generic login errors, bounded per-address sliding-window limiter.
- `uploads.py`: bounded background pool, separately committed real progress, same-user work lock,
  atomic transaction/detection/link writes, safe failure status and startup interruption recovery.
- `schemas/__init__.py`: extra-forbidden request/response contracts, UUID/ISO dates, Decimal strings.
  Aggregated money is not truncated to per-record NUMERIC(12,2) limits.
- `api/routes.py`: auth, CSV preview/confirmed upload/progress, subscription filters/sort/pagination/
  charges/actions, summary/trend, renewals, budgets, alert preferences, categories and account deletion.
- `services/summary.py`: Decimal projections (52 weekly/12 monthly/4 quarterly/1 yearly per year),
  round once at aggregation, actual-charge history including later-cancelled subscriptions.
- `middleware.py`: auth rate limit includes invalid bodies, bounded chunked multipart input,
  safe error envelope, exception redaction. CORS wraps early errors too.
- `tests/conftest.py`: creates random PostgreSQL 16 test databases, migrates with Alembic, truncates
  only test tables between tests, drops databases afterward. Application DB is never truncated.
- `tests/test_api.py`, `test_schema.py`: real PostgreSQL lifecycle/API/security/concurrency tests.
- `scripts/smoke_api.py`: real deployed HTTP flow with temporary synthetic account and cleanup.

API upload accepts INR only. No FX conversion or mixed-currency aggregation is implied; already
INR-converted FX amounts are supported. The application clock uses APP_TIMEZONE; tests override
the dependency. Pending uploads commit before 202; processing stages and counters reflect actual
work. Preview/preflight file validation is bounded, and heavy DB/detection work runs in the pool.

## Verification log

| Check | Result |
| --- | --- |
| Workspace inspection | Empty workspace; no applicable AGENTS.md found in checked ancestors |
| Docker | Installed Docker Desktop 4.95.0 per-user; CLI/engine 29.8.2; real stack healthy |
| GNU Make | Installed GNU Make 3.81 at `C:\Program Files (x86)\GnuWin32\bin\make.exe` |
| WSL | Sandbox denied access; elevated inspection found Ubuntu-24.04 and Ubuntu, neither has Docker |
| Default `python` | Installed normal Python 3.12.10; reopen terminals to refresh PATH |
| Available local Python | Bundled CPython 3.12.14, satisfies 3.11+ |
| Available Node/npm | Node 24.16.0 / npm 11.13.0; containers and CI use Node 22 |
| Backend tests | PASS: 161 tests on PostgreSQL 16; 114 baseline + 47 Phase 3 |
| Backend Ruff | PASS after import ordering and line length fixes |
| Frontend Vitest | PASS: 2 tests |
| Frontend ESLint | PASS |
| TypeScript + Vite production build | PASS: 83 modules transformed |
| Compose and CI YAML | Parsed with PyYAML; three expected services present (not a Docker validation) |
| Git repository | Logical Phase 1/2 and housekeeping commits created; Phase 3 commits listed below |
| `make dev` / Compose startup | PASS: PostgreSQL, API, and web all healthy |
| `make verify` | PASS: web HTML, proxied readiness, direct API readiness |
| `make test` | PASS: backend, quality evaluator, and frontend (final count below) |
| `make lint` | PASS: backend Ruff, frontend ESLint, TypeScript |
| Dependency audit | `npm audit` reports zero vulnerabilities after Vitest 4.1.11 update |
| Detector precision / recall / F1 | 1.0000 / 1.0000 / 1.0000 on all three committed datasets |

### Runtime installation (user authorized on 2026-10-18)

Docker Desktop is installed at `%LOCALAPPDATA%\Programs\DockerDesktop`; its `resources\bin`
contains Docker and Compose. A normal Python 3.12.10 is installed at
`%LOCALAPPDATA%\Programs\Python\Python312`. GNU Make is installed in the path listed above.
GNU Make's directory was added to the user PATH. Existing terminals may need their PATH refreshed
or to be reopened. All three commands were verified using the refreshed machine + user PATH.
Docker Compose reports version 5.6.0.
Docker uses its WSL2 Linux backend. Installation used the official signed Docker installer
(publisher Docker Inc); GNU Make and Python were installed with Windows Package Manager.
A local `.env` was created with random database/JWT secrets and verified gitignored.
Do not print these secrets or replace an existing developer `.env` when resuming.

Initial sandbox dependency installs could not resolve public registries. Network-enabled retry
was needed. A local `.venv` is ignored and is not a portable artifact.
Tests/build required elevated execution because the sandbox blocked dependency file access.
The workspace path contains an ampersand; package scripts invoke Node entry points directly
to avoid Windows npm command-shim quoting failures. Do not revert this without testing on Windows.
Frontend `package-lock.json` is present and used by Docker/CI. Python direct/transitive dependencies
and hashes are pinned in requirements.lock; requirements.in is the editable source. requirements.txt
is a compatibility pointer. Compile using pip-tools 7.5.2 on Linux/Python 3.12. Native Windows
development should use Docker rather than installing Linux uvloop from this lock.

### Actual commands run successfully

```text
backend: python -m pytest -q     -> 161 passed (PostgreSQL 16)
backend: ruff check .           -> All checks passed
frontend: npm test -- --run     -> 2 passed
frontend: npm run lint          -> exit 0
frontend: npm run build         -> TypeScript and Vite exit 0
```

The real Compose/PostgreSQL success path has been exercised with Alembic and readiness checks.
The two UI tests cover the readiness page only and replace its HTTP response. Business API tests
use real PostgreSQL; no business UI is implied. Remote CI has not run; its commands run locally.

### Phase 2 evaluation results

| Dataset | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Synthetic seed 42 (399 rows) | 16 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| Handwritten Withdrawal/Deposit | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| Handwritten Debit/Credit | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

Metrics include fixed bills as labelled recurring products, not as subscriptions. Synthetic labels
contain 12 subscriptions and 4 fixed bills. Tests additionally cover seeds 0–19 and three boundary
dates (month start and leap day). The first evaluation exposed a missing Notion alias: 15 TP,
1 FP, 1 FN, F1 0.9375. That alias was corrected; no expected labels were changed to hide it.
Handwritten fixtures are manually authored, not generated by the sample-data script and not
actual customer statements. Real-bank performance is unmeasured. See `backend/data/README.md`.

Evaluator matching is one-to-one on merchant/cadence/kind/currency/average amount (one-paisa
tolerance), with separate checks for category, occurrences, last date, stopped flag and price signal.
Any labelled mismatch, unmatched detection/product, unexpected skipped rows, or F1 <0.9 fails CI.
Report: `backend/data/evaluation_report.json`. Commands: `make sample`, `make evaluate`, `make test`.
A manual 50,000-row irregular-history check returned 0 detections in 4.393 seconds on this machine.
This is a single bounded check, not a general production performance guarantee.

### Core contracts and known limitations

`detect_recurring(transactions, as_of=...)` is pure and requires an explicit date; no implicit wall
clock. Use `Transaction` with positive two-decimal `Decimal`, explicit debit/credit and currency.
Do not convert amounts to float when connecting ORM or Pydantic in Phase 3. It returns frozen
`Detection` dataclasses: merchant/category/kind/cadence, Decimal average/confidence/regularity/CV,
occurrences, last/next dates, missed cycles, possibly_cancelled, requires_confirmation, optional
`PriceIncrease`, and charge tuples. No LLM or database is accessed. Exact repeated input records
are ignored defensively; this does not replace DB-level idempotency.

Confidence: 50% regularity +30% (1-CV/0.15, clamped) +20% min(occurrences/6,1), with yearly ×0.85.
CV uses population standard deviation. Full-group testing precedes amount clustering to avoid
splitting a coherent price increase into products. A sorted-median cluster fallback avoids quadratic
processing. Apple generic billing retains unknown category/user confirmation; explicit iCloud/Music
descriptions within a cluster resolve categories deterministically.

Limitations: nominal day intervals approximate true calendar billing; unknown first-two-token
names may collide; similar product amounts may be inseparable; large price changes can fail CV;
many missing charges can fail regularity; non-Latin descriptions need later normalization support.
`possibly_cancelled` must remain uncertainty, never silently change user status. Fixed bills must
be excluded from savings recommendations. Unknown-merchant user confirmation is implemented through
the API and cache; LLM categorization remains unwired.

CSV parser supports UTF-8/BOM, delimiter sniffing with header fallback, four specified date formats,
mapping overrides, separate debit/credit, malformed row reasons without raw text, 5 MB/50k limits,
blank lines and spreadsheet-formula-safe previews. It preserves raw descriptions in transactions.
After broken CSV quoting, safe resynchronization is impossible: valid preceding rows are retained,
and the unreadable remainder is reported as one malformed record. Document this in upload results.
Non-UTF-8 exports are rejected explicitly. Header mapping must choose one amount layout, not both.

Synthetic fixtures default to 2026-10-18. For Phase 7 demo loading, regenerate relative to the demo
clock via `generate_dataset(as_of=...)`; do not silently treat stale fixed-date rows as current.

## Resume instructions

1. Read this file and README; inspect actual files before making assumptions.
2. Start Docker Desktop if needed. Preserve the existing ignored `.env` (random local credentials).
3. Run `make dev`, `make verify`, `make test`, `make lint`; `make evaluate` prints quality metrics.
   Without Make, use the equivalent commands in README. Refresh PATH in old Windows terminals.
4. After the final Phase 3 gate and commits, stop and report. Do not begin Phase 4 without the
   user's follow-up. Phase 4 will consume the checked-in OpenAPI contract and real API, replacing
   the readiness-only frontend with auth, upload progress, dashboard and subscription workflows.
5. Keep the repository runnable after each phase; run the full available suite and report a short status.

## Phase 3 final verification and handoff

Backend feature commit: **991d929** (`feat: persist authenticated multi-user subscription backend`).
Housekeeping commit: **88c2fd5**. Earlier logical commits: 190fa80 / 401a055 / 984c600.
README and this handoff are committed separately after recording the final results.
No GitHub remote exists; no push or hosted-CI success is claimed.

Commands ran from the repository root with the installed tools (PATH refreshed from machine/user
environment in older PowerShell sessions). Every gate below completed with exit code 0:

| Command | Actual result |
| --- | --- |
| `make dev` | Built images, migrated to `0002_domain`; db/api/web all healthy |
| `make verify` | Web HTML, web-proxied readiness and direct API readiness all PASS |
| `make test` | **161 backend tests**, **2 frontend tests**, all 3 detector evaluations and OpenAPI check pass |
| `make lint` | Backend Ruff, frontend ESLint and TypeScript pass |
| `make evaluate` | Synthetic 16 TP/0 FP/0 FN; handwritten bank 3/0/0; products 5/0/0; all F1=1.0 |
| `make openapi` | Generated 18 paths / 22 operations with schemas/examples; drift check passes |
| `docker compose run --rm --no-deps api python scripts/smoke_api.py` | Real HTTP flow: 399 transactions, 16 products; account/data deletion verified |

The 47 Phase 3 tests comprise 43 API/security/concurrency/progress tests and 4 schema/migration
tests. They use PostgreSQL 16, no SQLite. Positive-path responses are produced by real services
and DB writes. Failure-path tests inject controlled errors and barriers only to verify rollback,
progress, queueing and safe logging. The 2 existing frontend tests mock readiness HTTP only.
One upstream Starlette/AnyIO deprecation warning remains; no application warnings/errors remain.

Verified behaviors include independent ground-truth summary arithmetic; duplicate and concurrent
duplicate upload dedupe; user isolation/404s; complete cascading deletion without affecting another
user; stable identity through a price increase; preserved confirm/dismiss/cancel/category/last-use
decisions; generic login failures and malformed-request rate limits; expired/forged JWT rejection;
bad-file handling; money string/Decimal/rounding checks and totals above individual record bounds;
startup interrupted-job recovery; post-commit logging failure not relabelling saved data as failed;
schema up/down/up and zero ORM drift; no `create_all`; mandatory scoped repository parameters.

Pre-commit checks: `.env` and `.venv` ignored and untracked; actual local database/JWT secret
values absent from all candidate source files; no frontend diff; no real statements introduced.
Fixtures and OpenAPI credential examples are synthetic. SQLAlchemy hides parameters, request/worker
errors log no financial fields, and Uvicorn access logs are disabled to avoid raw query-string logs.

### Honest gaps and next work

- **Stop here before Phase 4.** No business frontend was implemented. The readiness page's older
  placeholder wording predates the backend; replace it during Phase 4, not in this backend phase.
- Phase 4: auth views, confirmed upload/progress/results, dashboard/charts, subscription table and
  charge drawer, uncertainty/actions/settings/privacy UI, consuming the checked-in real contract.
- Phase 5: recommendation engine, daily scheduler, notifier, renewal/budget alerts and emails.
  Their tables exist, but no generation or delivery behavior is claimed.
- Phase 6: LLMClient/FakeLLM, unknown-merchant LLM categorization/cache integration, read-only tools,
  streaming chat and grounded evals/UI. **No LLM calls occur in Phase 3.**
- Phase 7: authenticated demo-data loader/button reusing these services, polishing, screenshots,
  accessibility review and three-minute demo script. `make seed` still fails explicitly until then.
- Real-customer/bank-export accuracy is unmeasured; only generated and handwritten synthetic fixtures
  were evaluated. Merchant/amount-cluster limitations from Phase 2 still apply.
- Upload workers and auth limiter are in-process; one API process is supported. Jobs are not durable
  across restart, and recovery marks interrupted jobs failed for safe re-upload. Multi-instance queue,
  global limiting, refresh-token flows, mixed-currency reporting and production deployment are absent.
- INR-only upload is explicit; no silent mixed-currency sums. Nominal renewal dates are approximate.
- If historical evidence ceases to satisfy the detector, existing user-controlled records are retained
  rather than silently cancelled; users review uncertainty. Generic merchant-level category choices
  apply across that merchant; per-product overrides remain available on individual subscriptions.

## Required stack and design constraints

- React + Vite + TypeScript, Tailwind, Recharts, TanStack Query, React Router.
- Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PostgreSQL 16.
- APScheduler daily jobs; pluggable console/SMTP Notifier; HTML and plaintext emails.
- Email/password, bcrypt, JWT; scoped database access for every user operation.
- LLMClient with tool calling; offline FakeLLM for demos and CI. Live provider has not been chosen.
  Choose one via `LLM_PROVIDER` when implementing Phase 6; ask before switching it later.
- Deterministic tested code performs detection, aggregation, all amounts, dates, estimates.
  LLM limited to unknown merchant categorization/cleanup, phrasing insights, and tool-grounded chat.
- Decimal end to end; database NUMERIC(12,2); JSON money should serialize as decimal strings.
- Never use `create_all`, raw financial data logs, committed personal statements, hardcoded secrets,
  arbitrary SQL tools, model-provided user IDs, or LLM-generated arithmetic.
- Auth/chat rate limits, consistent errors, pagination, strict-origin CORS, file limits,
  delete-my-data endpoint/action, visible educational-use notice are release requirements.

## Phase plan and acceptance gates

1. **Scaffold (PASS):** Compose/env/Makefile/API health/CI. All services boot via `make dev`.
2. **Detection/data (PASS):** normalizer, categories, detector, synthetic generator, handwritten bank
   fixtures, ground truth and evaluation. F1 1.0 on all three committed datasets; full tests pass.
3. **Backend (PASS):** business models/migrations/auth/CSV background uploads/subscriptions/summary/
   renewals/budget/settings/categories/privacy. PostgreSQL integration, isolation, migrations and
   concurrency tests pass; exact final test count and command log are appended below.
4. **Frontend:** auth, CSV flow, dashboard, subscription table and charge drawer against real API.
5. **Insights/alerts:** deterministic savings rules, scheduler, console/SMTP notifier, email templates.
   Gate: alert and ingestion idempotency, actual console renewal and budget notifications.
6. **Chat:** read-only tools, FakeLLM/live adapter, bounded tool loop, SSE, guardrails and chat drawer.
   Gate: >=15 grounded question evals; every answer number/date supported by tool output.
7. **Polish:** demo button/seeding, themes/responsive/accessibility, all empty/loading/error states,
   documentation, screenshots, three-minute demo script, final full-suite/lint/typecheck run.

No stretch features before the complete Definition of Done. No polish before detection measurement.

## Implemented schema (Phase 3)

- users: id, unique email, password_hash, created_at; alert preferences/notification email as needed.
- uploads: id, user_id, filename, row_count, status, uploaded_at; progress and row-error reporting.
- transactions: id, user_id, upload_id, date, raw_description, merchant_normalized,
  NUMERIC amount, debit/credit type, INR currency. Index (user_id, merchant_normalized, date).
  Unique dedupe (user_id, date, raw_description, amount).
- subscriptions: id, user_id, merchant, category, cadence, avg_amount, confidence, occurrences,
  last_charge, next_expected, active/cancelled/dismissed status, user_confirmed, timestamps.
  Includes permanent identity_key, kind/currency, regularity/CV, category override flag, cancelled_at,
  user-provided last_used_at, possibly_cancelled/missed_cycles and previous/new price/detected date.
- subscription_charges: user_id, subscription_id, transaction_id; composite owner FKs prevent cross-user links.
- recommendations: id, user_id, optional subscription_id, type, message, est_monthly_saving,
  open/accepted/dismissed status, created_at.
- budgets: id, user_id, monthly_limit, updated_at.
- alerts: id, user_id, optional subscription_id, renewal/budget kind, send_on, sent_at,
  email channel, JSON payload. Unique identity index uses PostgreSQL NULLS NOT DISTINCT, with budget
  dates constrained to the first day of the month; renewal alerts require a subscription.
- chat_messages: id, user_id, role, content, JSON tool_calls, created_at.
- merchant_categories: user_id, merchant, category, rule|llm|user source, confirmed; unique user/merchant.
  Phase 3 writes rule/user entries only. Generic category overrides can be per subscription too.

## CSV and detection contract (Phase 2/3)

CSV <=5 MB and <=50,000 rows. Detect delimiter and YYYY-MM-DD / DD/MM/YYYY / DD-MM-YYYY /
DD MMM YYYY dates. Support date,description,amount,type and Indian bank Withdrawal/Deposit or
Debit/Credit exports. Preview suggests mapping; confirmed mapping ingests. Skip/report bad rows
without crashing. Preserve raw descriptions in storage; strip leading = + - @ when echoing values.
Re-upload must not duplicate transactions. Long work needs actual progress feedback.

Normalize lowercase/digits/references/punctuation/rails/noise/city names, alias known merchants,
retain first 1–2 meaningful tokens. Do not match raw descriptions exactly. Group only debits;
split different products under one merchant using amount clusters without swallowing price changes.

Sort dates, median interval: weekly 7±1, monthly 30±4 (month-length/billing drift), quarterly 91±6,
yearly 365±10. Regularity >=0.7; amount CV <=0.15; min 3 occurrences except yearly min 2.
Confidence blends regularity, amount stability, occurrence count. Next expected = last + nominal
interval, roll forward when overdue, flag possibly cancelled after 2 missed cycles. Latest amount
>previous median by >5% triggers a price-increase rule.

Separate streaming/music/cloud/fitness/telecom/software/news subscriptions from rent/loan/insurance/
utilities fixed bills; fixed bills contribute to recurring tracking but not subscription savings.
Test drift, FX amounts, Apple iCloud versus Music clusters, irregular food/rides false positives,
two-charge yearly plan, stopped subscription, salary credits, and messy handwritten bank formats.
Synthetic generator: ~10 months, duplicate music services, price rise, rent/salary traps, noise;
include older yearly charge so two-yearly-charge test is possible. Evaluation must compare product
identities/cadences, disclose failures, and fail CI below F1 0.9. Do not evaluate synthetic data alone.

## Recommendations and alerts contract (Phase 5)

Duplicate plausible categories (music/video/cloud): cheaper overlapping costs form saving estimate.
High cost: configurable annual threshold or larger-than-median spend share.
Price increase: detector rule. Possibly unused: only user last-used or explicit low-engagement signal;
never infer usage from payments. Wording: "you may want to review". Accept tracks cancellation;
dismiss hides a recommendation. LLM may phrase text, never derive estimates.

Daily active renewal alerts N days before charge (default 3, user configurable). Persist and send
due alerts once; restart-safe. Budget alert once/user/month includes overage and top contributors.
Review database uniqueness/concurrency and delivery failure semantics in idempotency tests.

## Business API contract to implement

All under `/api/v1`, protected except register/login and operational health:

- POST auth/register, auth/login; GET auth/me; delete-my-data endpoint (choose documented route).
- POST uploads/preview, uploads; GET uploads; upload progress endpoint as required.
- GET subscriptions; PATCH subscriptions/{id}; charge detail for drawer.
- GET summary?period=month|year; GET summary/trend?months=12.
- GET recommendations; PATCH recommendations/{id}.
- GET renewals/upcoming?days=30.
- GET/PUT budget; GET/PUT settings/alerts.
- POST chat (SSE).
- Authenticated, idempotent Load demo data endpoint/button using real ingestion/detection services.

## Chat contract (Phase 6)

Tools: list_subscriptions(status?, category?), spend_summary(period: month|year,
group_by?: category|merchant), upcoming_renewals(days), compare_to_budget(),
get_recommendations(status?), subscription_detail(merchant), potential_savings().

Validate/cap all args; identity comes only from JWT. Read-only scoped DB queries, no arbitrary SQL.
At most 5 tool loops. Truncate/sanitize output; uploaded text is untrusted data, never instructions.
Do not expose raw descriptions or personal data unnecessarily. Log tool calls to chat_messages.
Assistant answers only from results, uses returned INR/currency, says unknown for missing data,
keeps replies short, no regulated financial advice. Grounding checks must actually validate returned
figures, not tautologically echo scripted answers. Minimum 15 known-answer demo questions.

## Frontend and final demo contract

Login/register; upload drag/drop→preview/map→confirm→progress→results; dashboard monthly/yearly/
active/savings KPIs, category donut, 12-month trend, next 5 renewals; sortable/filterable table with
confidence, confirmation/dismiss/cancel/category edits and charges drawer; 30-day renewal timeline;
recommendation actions; budget/lead-time/notification email settings; persistent streaming chat
with suggested prompts; dark/light themes, accessible keyboard controls, responsive layouts.

Final demo: new user register→sample upload→correct subscriptions/cadence/renewals→duplicate music
saving→"what renews this week?" grounded answer→console renewal email→lower budget→budget alert.
`docker compose up` starts everything, `make seed` works; backend, detector/chat evals, frontend,
lint/types pass. README includes setup/env, architecture, detection limits/known gaps/screenshots/
three-minute script. Keep this handoff current with actual results and outstanding gaps.

