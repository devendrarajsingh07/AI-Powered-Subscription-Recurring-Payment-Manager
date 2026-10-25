# Definition-of-Done and launch-readiness evidence

Updated 2026-10-25. Beta remains locked. The current-state section of
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
