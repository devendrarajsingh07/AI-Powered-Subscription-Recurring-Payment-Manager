# Definition-of-Done and launch-readiness evidence

Updated2026-10-21. Beta remains locked. Only the current-state handoff supplies current instructions.
Historical release evidence, every master requirement/prohibition mapping, and earlier measurements
are preserved without deletion in [the pre-continuation record](history/DOD_BEFORE_CONTINUATION.md).
Those results do not certify new changes. No paid resources or live Gemini calls are authorized.

| Done | Implemented — blocked for launch (needs X) | Not done |
| --- | --- | --- |
| WP2 invitation/export/audit foundations; successor CI39401421431 green on19f0098 | WP3 account APIs: local PostgreSQL and SMTP stand-in verified; needs real transactional sender, DNS and inbox validation | WP3 hosted CI and actual deployment/control verification pending |
| History scan44 commits/source scan clean (3 exact historical synthetic JWT exceptions); CI scan added, hosted verification pending | Strict rotating host-only cookies/revocable bearer sessions and CSRF: backend tests pass; needs sibling custom domains and trusted certificates | WP4 shared chat quotas/guard, durable queue, separate worker and restricted extraction container |
| Render PostgreSQL dashboard confirms external internet ingress blocked2026-10-21 | Public-demo visitor isolation/upload rejection/expiry/purge: local tests pass; actual hosted deployment verification pending | WP5 dedicated scheduling/retries, complete retention and content-free metrics |
|408 real PostgreSQL tests and67 frontend tests; final OpenAPI/type drift, lint/typecheck/build and detector gates pass | Synthetic/handwritten detector P/R/F1=1.0000 each; needs private real-statement measurement before accuracy claims | WP6 shared provider kill switch/global quotas/fallback/provider metrics |
| npm audit0 vulnerabilities; pip-audit no known vulnerabilities after certifi remediation | Offline grounded chat18 known-answer expectations; needs owner live Gemini eval, paid-tier project/billing/spend alerts before live launch | WP7 suppression/unsubscribe, versioned legal acceptance, support path and operational evidence |
| No secrets/real statements/outbox files tracked; raw financial application logging remains prohibited | Draft legal/privacy/terms and runbook; needs qualified lawyer approval and incident contact | WP8 green-master-only deploy gate, post-deploy smoke, rollback/restore/load/ZAP drills |
| Production remains unconditionally fail-closed; fake/offline deployed mode retained | Free Render database expires2026-11-19 and lacks PITR; needs managed PostgreSQL/PITR and separate staging | Owner rotation of exposed DB credential; account existence cannot be inferred from rejected public credentials |
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
- Final local evidence is recorded in history/PHASE8_WP3.md. New hosted CI/deployment pending;
  the earlier automatic-review rejection did not change hosted settings.
- Secret incident/rotation details: [SECURITY_INCIDENT.md](SECURITY_INCIDENT.md). Owner action pending.

## Owner launch actions

Rotate DB credential; managed PostgreSQL/PITR before2026-11-19 or accept demo data loss; separate
staging; sibling custom domains; transactional sender/SPF/DKIM/DMARC; paid-tier Gemini key/billing/
spend alerts; qualified legal review; incident contact; screen-reader pass; private real-statement
checks; live Gemini eval; chosen MIT copyright-holder/LICENSE application; repository visibility.
No beta tag, paid provisioning, real invitations, real financial uploads or history rewrite.
