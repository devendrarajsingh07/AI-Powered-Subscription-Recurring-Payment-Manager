# Definition-of-Done evidence

Release v1.0.0 is published; exact release/tag CI passed (run39368517177). The combined-prompt
Part 1 addendum passed hosted run39372903888. Part 2 passed hosted run39381573641 on764a3c9; local results are below. This file records measurements.
Baseline before
Phase 7: 266 PostgreSQL tests, 42 frontend tests, five Chromium flows; hosted c4d1138 green.
Final command/count/CI and fresh-clone evidence are recorded below.

| Master requirement / prohibition | Evidence | Status |
| --- | --- | --- |
| Compose starts, migration head correct, non-root processes | make dev; make verify; id/proc checks | Pass locally; API/web uid1000, PostgreSQL uid70 |
| Seeded current demo; no direct fixture subscriptions/recommendations | make seed; test_demo real pipeline/idempotency | Pass; CSV → parser/worker → detector/DB/insights/alert plans |
| Full register→data→review→chat→email→budget→delete demo | demo.spec.ts written-three-minute flow | Pass: fresh-clone full available-browser run below |
| F1≥0.9 and honest precision/recall | make evaluate | Three fixture sets P/R/F1 1.0000; real-bank accuracy unmeasured |
| Backend and per-user isolation | make test, test_api/test_chat/test_insights/test_demo | Pass: 307 PostgreSQL tests after Part1 addendum; release baseline287 |
| Frontend, typecheck, lint, build | Vitest/MSW, make lint, npm run build | Pass: 46 frontend tests; lint/type/build/drift clean |
| Browser main flow | make e2e | Local Chromium7/WebKit3 pass; Ubuntu CI13 pass including Firefox3; Windows native launch limitation documented |
| ≥15 grounded chat known answers | test_chat_evals, make chat-eval | 18 independent expectations; default offline; live not run |
| Verifier blocks invented numbers; never stream unverified text | test_grounding, adversarial FakeLLM/chat tests | Pass; figures only, prose associations not proven |
| README setup/env/architecture/limitations and shareable handoff | README, ARCHITECTURE, PROJECT_INFO/history | Documented; fresh-clone verification below |
| Phases gated, no stretches or fake completion | Preserved phase logs and test outputs | Prior phases archived; no stretch implementations |
| Stack/provider changes need authorization | Gemini replaces the previous provider | Explicit owner authorization “for live use gemini”; no second live adapter |
| LLM never detects/aggregates/calculates | Pure Decimal detector/summary/insights and seven read-only tools | Tested; live response figures checked against tools |
| Normalize merchants, alias rails/references | normalizer/detector hard-case tests | Pass; no exact raw-string matching |
| Drift/FX/product clusters/irregular purchases/yearly/stopped/credits | Detector tests + handwritten fixtures | Pass on fixtures; limits documented |
| Fixed bills distinct; no recommendation on all repeats | categories/insights exclusions | Tested; bills remain in recurring budget totals |
| Unknown categories need confirmation and expose confidence | API/UI notices; category/cache tests | Pass; live suggestion is opt-in, never auto-confirmed |
| Prompt injection is untrusted data; no model identity | strict tool schemas, injection/isolation tests | Pass; PostgreSQL read-only transactions and structural checks |
| No arbitrary SQL/action/file/network tools | chat_tools structural test + readonly transaction rejection | Pass; fixed seven tools, five rounds |
| Advisory recommendations, no inferred unused signal | Pure insight rules and UI no-estimate tests | Pass; last_used_at required; accept never cancels |
| Alembic only, no create_all | migration up/down and model drift tests | Pass; additive 0006 demo provenance |
| Upload/alert idempotency, overlap/restarts/crashes | API/concurrency/job/failure tests and real outbox e2e | Console artifact idempotent; SMTP acceptance/commit gap is at-least-once |
| Upload size/row limits and malformed input safe | test_api limits/encoding/quoting/formula cases | Pass; unreadable remainder behavior documented |
| Decimal money, never floats or frontend financial math | Schema Numeric/no Float checks, Decimal conversion/JSON tests, money.test | Pass; chart coordinates are dimensionless BigInt |
| No hardcoded keys/secrets/real statements | git ls-files + full-history Gitleaks | Baseline 18 commits clean; final scan below |
| Async uploads with real progress, atomic writes | Worker API progress/failure/queue tests | Pass; single-process recovery, no durable queue |
| Tests alongside code, no implementation-mirroring demo stubs | Detector/chat independent truth + network/UI/real DB flow | Pass; no canned financial figures in app |
| Dependencies necessary and audited | requirements hash lock; pip-audit/npm audit | Python baseline findings remediated; repeat audits below |
| No raw financial data carelessly logged or sent | caplog/LLM output/privacy tests; separate ignored outbox | Pass within application logging tests; retention limits documented |
| Delete-my-data, chat removal/outbox purge, isolation | delete API tests; browser demo final deletion | Pass; exported/SMTP/provider copies cannot be recalled |
| Persistent educational-use notice | Browser axe/main-flow and screenshots | Present in shell/auth/chat/mail; no regulated advice |
| No simultaneous edits / OpenAPI single source of truth | Single agent; export/type drift checks | Pass; no parallel agents editing files |
| Offline demo no API key/SMTP | FakeLLM + ConsoleNotifier, seed/demo.spec | Pass at runtime; initial install/clone still needs network or caches |
| Production guardrails | test_demo production/JWT/CORS/adversarial/seed tests | Fail closed; Compose remains dev/demo, not production deployment |
| Responsive/themes/states and accessibility | demo.spec all-page audit, QA matrix | Axe both themes360 and overflow360/768/1280 pass in fresh-clone final run; human screen reader pending |
| Secrets only env; explicit origin | startup guards; .env ignored; no VITE secrets | Pass; no default dev credential outside development |
| License choice not made by agent | Owner selected MIT | Recorded; explicit instruction keeps LICENSE absent in this phase |
| Optional real statements / live provider | Private checker; make chat-eval-live | Synthetic checker run; owner checks not run or claimed |

## Measurements and verification log

- Gitleaks 8.30.1, full history before edits: 18 commits/~1.35 MB, no leaks.
- Expanded history scan initially flagged three synthetic production-guard JWT literals in
  f9043c5:tests/test_demo.py, never used as account/application credentials. Reported to the owner;
  no history rewrite. Tests now generate ephemeral values. .gitleaksignore lists ONLY those exact
  three historical fingerprints, with no path/rule suppression. Reviewed scan:22 commits, no
  unreviewed findings. No real secret was discovered. Retain this explanation with the scan result.
- Baseline pip-audit reported 49 advisory entries (including duplicate identifiers) in PyJWT,
  pytest, python-multipart and Starlette. Updated PyJWT2.15.0, pytest9.0.3, multipart0.0.31,
  FastAPI0.147.0 and compatible Starlette1.9.0; regenerated hash lock. Repeat audit: no known vulnerabilities.
- npm audit: zero vulnerabilities. No new LLM SDK; existing httpx implements Gemini REST.
- Production bundle observed: main ~346 KB (109 KB gzip), lazy dashboard/chart chunk ~390 KB
  (114 KB gzip), CSS ~25 KB (6 KB gzip); other routes lazy chunks <10 KB each. No performance SLA.
- API/web non-root exec id confirms uid1000; PostgreSQL PID1 Uid70 after entrypoint privilege drop.
- Browser every-page axe (login/register, overview, upload, subscriptions, renewals, recommendations,
  categories, settings, 404) light/dark at360: zero violations. All protected routes at768/1280:
  no document-wide horizontal overflow. Chat/removal dialogs also checked.
- Real-stack demo flow individually passed, including independent ground truth, renewal at
  2026-10-19 for fixed app date2026-10-18, budget and per-user outbox purge.
- Optional private checker exercised on data/handwritten_bank.csv: three detections, three malformed
  rows safely reported. No real financial statement used. Live Gemini eval not run.

Human tasks remain: screen reader/navigation pass, private redacted statement comparison, optional
live Gemini eval with owner's key/model, and owner application of the selected MIT license.

## Fresh-clone verification — executed 2026-10-19

Empty target `var/fresh-release`, cloned the public pushed repository at523ce47; later fast-forwarded
to c85418b (same verified demo runtime plus auth/demo guard and focus fixes) and repeated up/seed/verify
and the full available-browser suite. No original database was reused: COMPOSE_PROJECT_NAME=subtrack-fresh,
new postgres/outbox volumes, WEB_PORT5273/API_PORT8100, WEB_ORIGIN/E2E_BASE_URL localhost5273. Explicit
APP_TEST_AS_OF=2026-10-18 reproduces the written script, not an implicit change to normal user data.

| Exact command/action, in order | Actual result |
| --- | --- |
| git clone https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager.git var/fresh-release | Exit0; empty checkout from pushed public origin |
| Set-Location -LiteralPath var/fresh-release; Copy-Item .env.example .env | Exit0; ignored development-only configuration |
| Set process env COMPOSE_PROJECT_NAME=subtrack-fresh, WEB_PORT=5273, API_PORT=8100, WEB_ORIGIN/E2E_BASE_URL=http://localhost:5273, APP_TEST_AS_OF=2026-10-18 | Isolated stack and explicit replay clock |
| docker compose up --build --wait | Exit0; all3 services healthy, migrations0001–0006 applied to empty DB |
| make seed | Exit0; dev login printed, real generated-CSV ingestion |
| make seed (again) | Exit0; same upload/data, no duplicates |
| make verify | Exit0; web/proxy/API all3 readiness checks pass |
| npm.cmd ci --prefix frontend | Exit0; 387 packages, zero audit findings |
| python scripts/run_e2e.py demo.spec.ts --project=chromium | Exit0;2 tests: exact demo and every-page axe/overflow; actual mail/purge |
| make run-alerts AS_OF=2026-10-19 | Exit0; repeated event delivery sent0, no duplicates |
| make outbox | Exit0; actual MIME files exported into ignored local directory |
| make chat-eval | Exit0;1 integration test with18 independently checked known answers |
| git pull --ff-only (to c85418b) | Exit0; no reset/discard; local screenshot evidence preserved |
| docker compose up --build --wait; make verify; make seed | All exit0 on updated runtime |
| python scripts/run_e2e.py --project=chromium --project=webkit | Exit0;10 passed in2.9min (Chromium7/WebKit3) |

Equivalent README setup/build/test commands were also exercised in the primary checkout:
make dev / verify / seed / test / lint / evaluate, OpenAPI/type generation, frontend npm ci/build/audit,
three browser installs, CLI alert job/outbox export and the synthetic private-checker invocation.
The optional owner-only live evaluation and private real-statement command are intentionally not executed.

## Final local command results

| Command | Actual result |
| --- | --- |
| make dev; make verify; make seed | Exit0, healthy stack and seeded development login |
| make test | Latest exit0:287 backend,46 frontend, evaluation and OpenAPI/TS drift current |
| make lint | Exit0: Ruff, ESLint, TypeScript |
| make evaluate | Exit0: synthetic16/0/0, handwritten-bank3/0/0, handwritten-products5/0/0 TP/FP/FN; all P/R/F1=1.0000 |
| make e2e (initial Windows all-project attempt) |9 passed/4 failed: Firefox3 native launch failures, WebKit1 focus restoration bug |
| python scripts/run_e2e.py main.spec.ts --project=webkit (after focus fix) | Exit0:3 passed; no focus assertion removed |
| fresh available-engine complete run | Exit0:10 passed; Firefox remains enabled in default suite and Linux CI |
| npm run build; node scripts/measure_load.mjs | Exit0; production login and CSP/nosniff/frame/referrer headers pass, zero page errors; first measured DCL105ms, no SLA |
| pip-audit -r requirements.lock --disable-pip in disposable Python3.12 container | No known vulnerabilities after remediation |
| npm audit --audit-level=low | Zero vulnerabilities |
| gitleaks git --redact . |24 commits reviewed, no unreviewed findings;3 historical synthetic fingerprints explicitly documented above |
| git ls-files *.env *.eml *outbox* *private-statements* | Empty; no real statements/keys claimed or committed |

One dependency deprecation warning remains: Starlette's TestClient/httpx bridge recommends a future
httpx2 migration. Tests currently pass; no warnings were suppressed and no unnecessary second HTTP
client was added merely to silence it.

## Browser failures and corrections

- WebKit pointer activation does not focus a button; explicitly focus the Review invoker before
  opening the drawer. Escape returns focus across Chromium/WebKit; assertion retained.
- Expanded Ubuntu suite initially hit the unchanged shared auth registration quota across engines:
  runs39244585655 and39245147418 failed. Main-flow registration now asserts a real429's friendly
  message, validates Retry-After, waits that exact server-directed interval and retries once.
  No arbitrary failure retry, rate-limit increase, mocked registration or skipped assertion.
- Windows Firefox157 cannot launch: SideBySide event names missing dependent assembly mozglue.
  This is a local host limitation before application execution; Ubuntu CI is the release gate for it.

## Hosted verification and publication policy

[Run39246044919](https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39246044919)
SUCCEEDED for source commit6e3fd76794edbd560698c7bb24adf7be97d54ecb. Both checks and e2e green;
actual e2e log:13 passed (Chromium7, Firefox3, WebKit3). The server-directed backoff was exercised
in Firefox without raising rate limits. The final documentation/screenshot commit repeats hosted
CI and is tagged only after it is green; check the v1.0.0 commit's associated GitHub run for that
publication evidence. No tag denotes production readiness.

Final repeat: npm audit0; pip-audit no known vulnerabilities; Gitleaks25-commit reviewed history
has no unreviewed findings (exact3 synthetic exceptions retained); build main346.56KB/109.50KB gzip,
charts389.93KB/114.22KB gzip, CSS24.93KB/6.25KB gzip; preview repeat DCL96ms with zero page errors
and all controlled web security headers. Single machine samples establish no performance guarantee.

## Final isolated-stack replay and fixture corrections

Fast-forwarded the isolated checkout to8ae8845, rebuilt both images, and ran make verify/test/lint/
evaluate at ports5273/8100 with the explicit18Oct clock: **all exit0**,286 PostgreSQL tests,
46 frontend tests, both contract drift checks, Ruff/ESLint/TypeScript and all3 detector datasets.
Before correction, this additional configuration exposed test-fixture assumptions: a legacy CORS
test hardcoded5173, and the valid-production fixture inherited the intentionally forbidden test
clock. The CORS test now checks the configured origin; valid-production inputs explicitly clear
the clock, while each invalid-guard case still asserts rejection. No application guard was weakened.
The failed isolated run (285 passed/1 failed) and its safe production rejection were investigated,
not discarded or reported as green. The corrected26 safety/health cases also passed independently.

The final written-demo test additionally opens/closes the real Spotify charges drawer, records
music review intent and proves statuses unchanged, and reloads Settings to see Sent in the UI.
It passed locally in24.4s and keeps the same13-flow hosted suite. The private checker disables
bytecode writes before app imports; synthetic CLI smoke still reports3 detections/3 malformed rows.
ESLint9 and a transitive encoding package emitted npm deprecation notices; npm audit remains0.
These existing development-tool maintenance notices are documented, not security findings or
suppressed warnings. No major tooling migration was added in this release scope.

## Recipient-consent release guard

Before tagging, migration0007 was added so an old provider opt-in cannot authorize Gemini.
A real-PostgreSQL upgrade test inserts an opted-in user at0005, upgrades to head and verifies
consent=false; downgrade does not reconstruct consent. Twenty-four schema/demo safety cases pass.
Final make dev/verify/test/lint/evaluate after this guard all exit0: **287 backend,46 frontend**,
OpenAPI/TypeScript current, three fixture sets P/R/F1=1.0000. Application data migration was also
applied to the running dev stack before readiness passed. The prior286 counts above describe
the earlier measured runs, not an omitted test. Live Gemini still requires each user's new opt-in.

## Phase 7.5 evidence — supplemental statement import

| Requirement | Actual evidence/result |
| --- | --- |
| PDF/scanned PDF/JPEG/PNG reuse real pipeline | 330 PostgreSQL tests; real browser text PDF399 rows ->16 ground-truth products; scanned15 plus corrected JPEG -> independent totals and dedupe; PNG local preview/cancel |
| No silent extraction errors | make test includes evaluate_extraction.py:18 synthetic variants; silent0; clean text field1.000; every returned row flagged, no automatic acceptance |
| OCR limitations disclosed | docs/STATEMENT_IMPORT.md complete matrix: degraded/rejected variants, 150dpi synthetic floor, description mistakes; no real-bank claim |
| Review/edit/strict validation | Nine typed-MSW statement component tests; server excludes flagged-unverified rows; Decimal/reconciliation/Dr-Cr/grouping tests |
| Isolation/privacy/intake/password | Parser limits, hanging-worker fault injection, actual malformed/recursive PDFs, memory/temp/EXIF/shell/polyglot/password tests; scoped TTL/cancel/delete/quota tests |
| Timeout evidence limit | Controlled subprocess fault injection proves watchdog/cleanup; no claim that a naturally occurring bank PDF hung during testing |
| Migration/contracts | Alembic up/down/drift included; OpenAPI and generated TS checks pass |
| Frontend/accessibility | 55 frontend tests; real review axe both themes360; hostile strings plain text; screenshots/QA checklist |
| Earlier behavior | Full available-browser13/13 pass; detector all3 fixture sets P/R/F1=1; 18 offline chat questions retained |
| Audits/runtime | npm0; pip no known vulnerabilities; image646058096bytes; API uid1000; full-history secret scan recorded in handoff |
| Optional private checker | Synthetic15-row PDF, Docker network-none/read-only+tmpfs, exit0; real personal check human-owned |
| Hosted CI | checks and e2e passed on implementation764a3c9, run39381573641; Ubuntu16 configured flows including Firefox; docs-only successor is checked after push |

The prior release counts are historical. Current local counts330 backend/55 frontend supersede them.
Phase8 beta readiness is **not met**: no hosted staging/prod, durable queue, cookie sessions, invitation,
verification/reset, backup restore drill or legal sign-off. External prerequisites are in PROJECT_INFO.md.

