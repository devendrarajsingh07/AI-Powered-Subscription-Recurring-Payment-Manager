# Definition-of-Done and launch-readiness evidence

Updated 2026-10-26. Beta remains locked. The current-state section of
[PROJECT_INFO](../PROJECT_INFO.md) supplies current instructions. Prior evidence and every
master requirement/prohibition mapping remain in [the original evidence](history/DOD_BEFORE_CONTINUATION.md)
and [the pre-review snapshot](history/DOD_BEFORE_REVIEW_FIXES_2026_10_25.md).
Historical measurements do not certify later commits.

| Done | Implemented — blocked for launch (needs X) | Not done |
| --- | --- | --- |
| Deterministic Decimal detection, summaries, advisory insights; migration-only persistence and ownership constraints | Detection/import accuracy: verified on synthetic/handwritten fixtures; needs private real-statement measurement | Production launch, real-user beta, real financial-data processing |
| Offline tool-using assistant, figure verifier, injection/isolation tests; live retry consent regression | Gemini controls with shared caps, kill switch and fallback: needs paid project/billing/spend alerts and owner live eval | Live Gemini evaluation |
| Disposable, isolated, synthetic-only public-demo controls; local-only shared credential | Demo purge/retention: needs always-on worker and operational monitoring | Two-API/worker Compose crash/shared-limit demonstration |
| Password-denylist/bcrypt and PostgreSQL auth-limit regressions pass | Verification/reset, revocable rotating same-site sessions and CSRF: needs sibling custom domains/certificates and real email sender | Managed PITR and separate staging |
| PostgreSQL durable-job lease/retry and encrypted-input tests pass | Durable worker and restricted extraction container: needs multi-instance operational drills and deployed worker resources | Restore, load and ZAP drills |
| Local scheduling/retry, retention and content-free metric tests pass | Operational scheduling/metrics: needs always-on worker and monitoring/incident routing | Exercised rollback and enforced automated release gate |
| Local email-lifecycle, support and legal-versioning regressions pass | Email lifecycle and legal drafts: needs real sender/DNS/events, qualified legal review and incident contact | Human screen-reader pass |
| Owner confirmed DB credential rotation 2026-10-22; MIT LICENSE present, copyright 2026 DEVENDRA RAJ SINGH | Free PostgreSQL: needs managed backup/PITR before 2026-11-19 or accepted demo-data loss | Owner public/private repository decision |
| Review fixes: persistent billing projection/backfill, retry consent/account checks, shared renewal projection, pypdf 6.21.2 and static-host CSP | Manual demo deployment/revision/header checks passed; launch still needs enforced CI gating and operational drills | Claims of production readiness or capacity |

## Current verification

- `docker compose build api web` and `docker compose up --build --wait` passed; `make verify` passed.
- `make test`: 486 real PostgreSQL tests passed in 425.83s, with one upstream TestClient
  deprecation warning; 75 frontend tests passed. Root release-script tests are mounted and run.
- `make lint`: Ruff, ESLint and TypeScript passed. OpenAPI and generated TypeScript drift checks passed.
- `make evaluate`: synthetic TP/FP/FN 16/0/0, handwritten bank 3/0/0, handwritten products
  5/0/0; precision/recall/F1 1.0000 each. The extraction evaluator passed its 18-variant gate;
  imperfect OCR still requires explicit review and is not a real-bank accuracy measurement.
- Production build passed: main 354.46kB (111.66 gzip), lazy chart 389.93kB (114.22 gzip).
- `npm audit --audit-level=low`: 0 vulnerabilities. `pip-audit -r backend/requirements.lock
  --disable-pip`: no known vulnerabilities. pypdf 6.21.2 was installed using verified lock hashes.
- Gitleaks 8.30.1: 73 reachable local commits (`--all --no-textconv`) and current non-ignored source
  clean. The initial Git text-conversion scan failed; the explicit no-textconv rerun completed.
- Production CSP mobile Chromium probe passed registration, real demo ingestion, charts, renewals
  and account deletion; no page errors or CSP violations. Screenshot inspected outside the repo.
- Browser suite: 16 passed (6.0m), 2 profile-only tests skipped in that invocation then run
  separately: strict sibling-host TLS 1 passed (15.2s), isolated public-demo 1 passed (19.4s).
  Chromium 10/Firefox 3/WebKit 3 standard tests include every-page mobile light/dark axe, imports,
  grounded chat, real outbox idempotency and deletion. Linux browser runner used an origin-preserving
  local proxy and explicit 2026-10-18 API/test clock, then restored the normal local stack.
- Implementation [hosted CI 40215376979](https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/40215376979) passed all four jobs on 007e76d.
  Hosted backend log: 486 passed in 161.63s. Standard browser log: 16 passed (3.7m), public-demo
  profile 1 passed (5.9s); strict TLS job succeeded separately. This is independent of older CI.
- Vercel and Render both served 007e76d after verification. Render deployment
  dep-dbf3ks29lscs738mgjjg succeeded/live; readiness passed, synthetic-only demo mode retained.
  `python scripts/smoke_deployed.py --api https://ai-powered-subscription-recurring.onrender.com/api/v1
  --web https://ai-powered-subscription-recurring-p.vercel.app`: 23/23 passed.
- Vercel Git auto-deployment completed before CI, while Render was manually deployed after green
  CI. Enforced provider gating/automated rollback remains unverified and is not marked complete.
  This receipt update changes documentation only; latest master checks are authoritative for it.

No paid provisioning, live calls, real invitations, beta tags or history rewrite is authorized.
Secrets are never reproduced in evidence. The three historical scanner exceptions match exact
synthetic JWT fixtures, not production secrets. Console delivery is idempotent by file receipt;
SMTP retains its send/commit ambiguity. Figure verification proves provenance, not prose truth.

## Owner launch actions

Managed PostgreSQL/PITR before free database expiry (2026-11-19) or accept losing demo data;
separate staging; sibling custom domains; transactional sender/SPF/DKIM/DMARC; paid Gemini
project/billing/spend alerts; qualified legal review; incident contact; human screen-reader pass;
private real-statement checks; live Gemini eval; repository visibility decision. DB rotation
and the chosen MIT LICENSE are complete, not pending owner actions.

## Offline receipt foundation — 2026-10-26 (historical; UI status superseded below)

| Done | Implemented — blocked for launch (needs X) | Not done |
| --- | --- | --- |
| 35 receipt regressions pass on real PostgreSQL; 16/16 synthetic MIME outcomes; real Compose demo imports8 receipts, detects3 products, checks independent totals/replay and deletes its test account | Development-only reviewed receipt import; launch needs privacy/operational review and broader accuracy measurement | Gmail OAuth/sync, email-import UI, bank reconciliation and invoice identity |
| Public-demo EML/body refusal, source-mixing exclusion, ownership/expiry/cancel/delete, strict review/decimal validation and durable worker tests pass | Live email access needs reviewed OAuth consent/token lifecycle plus Google verification/security requirements | Live mailbox access or real-provider template accuracy |
| Full local gate521 backend/75 frontend; standard browsers16, TLS1 and public-demo1; lint/build/drift/audits/evaluators clean | All existing paid/infrastructure/legal launch blockers remain; hosted demos retain disabled email input | Provider interest lists, negotiated offers or credentials/plan sharing |

Exact commands, timings, the corrected fixture-audit failure, metadata limits and deployment
gates are in [the foundation record](EMAIL_RECEIPT_FOUNDATION.md). Existing application CI and
deployment receipts above are historical. Latest master checks are authoritative for this new
revision; a push alone does not prove a deployment. No live Gmail/Gemini call, paid service,
third-party account, provider contact, real user/data or beta tag was introduced.
Only the16 allowlisted synthetic EML fixtures may be tracked; original private emails and outbox
copies stay ignored. The original35 receipt tests include a targeted rerun after final bounded
blank-line parsing hardening. Detector F1 remains1.0000 on the prior synthetic/handwritten gates;
real-bank and real-provider accuracy are not measured.

### Receipt-import UI continuation (2026-10-26)

| Done | Implemented — blocked for launch (needs X) | Not done |
| --- | --- | --- |
| Local synthetic EML picker, editable fields, explicit approval, cancel, real upload progress/results, source badges; fail-closed capability and public-demo suppression | Receipt processing for real users — needs existing launch prerequisites, privacy review and private accuracy measurement | Live Gmail connection/OAuth/sync and bank reconciliation |
|525 backend +87 frontend tests;19 actual browser passes across profiles; detector P/R/F1=1.0000; receipts16/16; lint/type/contract/build/audits/history/tree scans passed | Publication waits for exact-commit hosted CI; hosted receipt input stays disabled | Provider partnerships, interest lists, commercial offers; no beta launch |

Timings and corrected harness failures are recorded in PROJECT_INFO.md. Browser plugin absent;
existing Linux Playwright image used. No manual screen-reader, real-provider accuracy or live-LLM
pass is claimed. The local configuration and existing screenshots were restored after testing.
