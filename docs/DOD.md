# Definition-of-Done evidence

Release verification in progress. This file records measured results, not promises. Baseline before
Phase 7: 266 PostgreSQL tests, 42 frontend tests, five Chromium flows; hosted c4d1138 green.
Final command/count/CI and fresh-clone evidence will be appended below after execution.

| Master requirement / prohibition | Evidence | Status |
| --- | --- | --- |
| Compose starts, migration head correct, non-root processes | make dev; make verify; id/proc checks | Pass locally; API/web uid1000, PostgreSQL uid70 |
| Seeded current demo; no direct fixture subscriptions/recommendations | make seed; test_demo real pipeline/idempotency | Pass; CSV → parser/worker → detector/DB/insights/alert plans |
| Full register→data→review→chat→email→budget→delete demo | demo.spec.ts written-three-minute flow | Pass individually; full final run below |
| F1≥0.9 and honest precision/recall | make evaluate | Three fixture sets P/R/F1 1.0000; real-bank accuracy unmeasured |
| Backend and per-user isolation | make test, test_api/test_chat/test_insights/test_demo | Real PostgreSQL only; final count below |
| Frontend, typecheck, lint, build | Vitest/MSW, make lint, npm run build | Final results below |
| Browser main flow | make e2e | Chromium plus Firefox/WebKit configured; execution below |
| ≥15 grounded chat known answers | test_chat_evals, make chat-eval | 18 independent expectations; default offline; live not run |
| Verifier blocks invented numbers; never stream unverified text | test_grounding, adversarial FakeLLM/chat tests | Pass; figures only, prose associations not proven |
| README setup/env/architecture/limitations and shareable handoff | README, ARCHITECTURE, PROJECT_INFO/history | Documented; fresh-clone verification below |
| Phases gated, no stretches or fake completion | Preserved phase logs and test outputs | Prior phases archived; no stretch implementations |
| Stack/provider changes need authorization | Gemini replaces Claude | Explicit owner authorization “for live use gemini”; no second live adapter |
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
| Dependencies necessary and audited | requirements hash lock; pip-audit/npm audit | Python baseline findings remediated; final audits below |
| No raw financial data carelessly logged or sent | caplog/LLM output/privacy tests; separate ignored outbox | Pass within application logging tests; retention limits documented |
| Delete-my-data, chat removal/outbox purge, isolation | delete API tests; browser demo final deletion | Pass; exported/SMTP/provider copies cannot be recalled |
| Persistent educational-use notice | Browser axe/main-flow and screenshots | Present in shell/auth/chat/mail; no regulated advice |
| No simultaneous edits / OpenAPI single source of truth | Single agent; export/type drift checks | Pass; no parallel agents editing files |
| Offline demo no API key/SMTP | FakeLLM + ConsoleNotifier, seed/demo.spec | Pass at runtime; initial install/clone still needs network or caches |
| Production guardrails | test_demo production/JWT/CORS/adversarial/seed tests | Fail closed; Compose remains dev/demo, not production deployment |
| Responsive/themes/states and accessibility | demo.spec all-page audit, QA matrix | Axe both themes360 and overflow360/768/1280 passed individually; human screen reader pending |
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
