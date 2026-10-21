# Definition-of-Done and launch-readiness evidence

Updated 2026-10-21. Beta remains locked. Only the current-state handoff supplies current instructions.
Historical release evidence, every master requirement/prohibition mapping, and earlier measurements
are preserved without deletion in [the pre-continuation record](history/DOD_BEFORE_CONTINUATION.md).
Those results do not certify new changes. No paid resources or live Gemini calls are authorized.

| Done | Implemented — blocked for launch (needs X) | Not done |
| --- | --- | --- |
| WP2 invitation/export/audit foundations; successor CI39401421431 green on19f0098 | WP3 account APIs: local PostgreSQL and SMTP stand-in verified; needs real transactional sender, DNS and inbox validation | WP4 durable jobs, shared chat quotas and restricted extraction container |
| History scan44 commits/source scan clean (3 exact historical synthetic JWT exceptions); hosted secret scan passed on f857f1f | Strict rotating host-only cookies/revocable bearer sessions and CSRF: backend tests pass; needs sibling custom domains and trusted certificates | WP4 shared chat quotas/guard, durable queue, separate worker and restricted extraction container |
| Render PostgreSQL dashboard confirms external internet ingress blocked2026-10-21 | Public demo isolated synthetic-only controls verified hosted; needs reliable always-on retention before launch | WP5 dedicated scheduling/retries, complete retention and content-free metrics |
|408 real PostgreSQL tests and67 frontend tests; final OpenAPI/type drift, lint/typecheck/build and detector gates pass | Synthetic/handwritten detector P/R/F1=1.0000 each; needs private real-statement measurement before accuracy claims | WP6 shared provider kill switch/global quotas/fallback/provider metrics |
| npm audit0 vulnerabilities; pip-audit no known vulnerabilities after certifi remediation | Offline grounded chat18 known-answer expectations; needs owner live Gemini eval, paid-tier project/billing/spend alerts before live launch | WP7 suppression/unsubscribe, versioned legal acceptance, support path and operational evidence |
| No secrets/real statements/outbox files tracked; raw financial application logging remains prohibited | Draft legal/privacy/terms and runbook; needs qualified lawyer approval and incident contact | WP8 green-master-only deploy gate, post-deploy smoke, rollback/restore/load/ZAP drills |
| Production remains unconditionally fail-closed; fake/offline deployed mode retained | Free Render database expires2026-11-19 and lacks PITR; needs managed PostgreSQL/PITR and separate staging | Owner rotation of exposed DB credential (reserved shared account absent at hosted startup) |
| Local published demo credential is labelled local-only | Existing broad release axe/browser tests; needs human screen-reader check | MIT LICENSE application/copyright-holder line and public/private repository decision |

## Current verification log

- Final frozen `make dev`, `make verify`, `make test`, `make lint`, `make evaluate`: exit0.
- PostgreSQL:408 passed,1 upstream TestClient deprecation warning,259.91s; frontend67 passed.
- OpenAPI/TypeScript drift, lint/typecheck and extraction18 synthetic review variants pass.
- Detector synthetic TP16/FP0/FN0, handwritten bank3/0/0, handwritten products5/0/0;
  precision/recall/F1=1.0000 each. Real-bank accuracy remains unmeasured.
- Browser normal suite16 passed (Chromium10/Firefox3/WebKit3),2 profile-specific tests run separately:
  strict sibling-host TLS1 passed; isolated public-demo1 passed. Expanded recovery-page mobile
  light/dark axe and responsive audit1 passed. No manual screen-reader claim.
- Production build: main352.42kB (111.03gzip), lazy chart389.93kB (114.22gzip).
- npm audit0; pip-audit no known vulnerabilities after certifi2026.10.19 fixes PYSEC-2026-4320.
- Final local evidence is recorded in history/PHASE8_WP3.md. Hosted branch CI39623411405 passed all4 jobs; master39624799629 also completed/success on the same SHA.
  Both demos deployed f857f1f; hosted controls and independent synthetic totals pass.
- Secret incident/rotation details: [SECURITY_INCIDENT.md](SECURITY_INCIDENT.md). Owner action pending.

## Owner launch actions

DB credential rotation done 2026-10-22 (owner-confirmed); managed PostgreSQL/PITR before2026-11-19 or accept demo data loss; separate
staging; sibling custom domains; transactional sender/SPF/DKIM/DMARC; paid-tier Gemini key/billing/
spend alerts; qualified legal review; incident contact; screen-reader pass; private real-statement
checks; live Gemini eval; chosen MIT copyright-holder/LICENSE application; repository visibility.
No beta tag, paid provisioning, real invitations, real financial uploads or history rewrite.

## WP3 deployment evidence2026-10-21

Render dep-dbcdh3jl550s738devf0 and Vercel21kzXbFuhxHkkZcNatA73hCDSxLn: live/ready at f857f1f.
Readiness200; public-demo-only true; password registration/login403; CSV/PDF/PNG upload and preview
six paths403. Two disposable visitors: independent16-product truth/totals, repeat loader unchanged,
other visitor empty and guessed IDs404; probe accounts deleted. Console startup shared_before0.
Browser confirms banner, isolated entry and399-row/16-product current-clock demo. No credentials
changed. Rotation remains owner-pending. WP4-8 code/operational gaps remain as listed.

## Phase 8 WP4–8 local status (2026-10-21, uncommitted, not deployed)

Statuses follow the owner's wording: nothing below is "done" for launch.

| Package | Implemented, verified locally | Blocked for launch / not verified here |
| --- | --- | --- |
| WP4 durable jobs | PostgreSQL queue (SKIP LOCKED, leases, claim tokens, dead-letter, encrypted bounded input), per-user admission cap, real-process SIGKILL recovery test, delete-while-running test | needs Compose two-API test, extractor container isolation proof, browser flows |
| WP5 scheduling/retention/metrics | retry-only loop, worker as scheduler owner, documented retention purge, token-gated content-free metrics | needs deployed worker and monitoring/alert routing |
| WP6 AI controls | env + DB kill switch (`python -m app.llm_admin`), global daily request/token caps (tokens estimated), visible offline fallback in API and UI | needs paid-tier Gemini, spend alerts and live evaluation (none authorised) |
| WP7 email/legal/support | hard-bounce/complaint suppression, signed one-click unsubscribe + RFC 8058 headers, restricted problem reports, versioned legal acceptance (flag off) | needs real sender/DNS, provider event adapter, lawyer-approved texts, incident/support contact |
| WP8 release | opt-in green-master-only deploy workflow, read-only smoke script, rollback procedure | workflow and smoke never run against Render/Vercel; Vercel still auto-deploys until the owner disables it; no restore/load/ZAP drill |

Commands and counts: backend 457 passed (122 + 181 + 154 in three groups, 28 test files, embedded
PostgreSQL 16, Python 3.12); frontend vitest 73 passed, eslint/tsc/prettier clean; `ruff check` and
`ruff format --check` clean; `export_openapi --check` and `types --check` current; detector TP/FP/FN
16/0/0, 3/0/0, 5/0/0; extraction evaluator runs. `scripts/smoke_deployed.py` passed 21/21 checks
against a local uvicorn server plus a stub web server only.
