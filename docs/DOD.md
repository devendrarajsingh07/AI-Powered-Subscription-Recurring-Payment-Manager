# Definition-of-Done and launch-readiness evidence

Updated 2026-10-28. **NO-GO for real users.** Current instructions: [PROJECT_INFO](../PROJECT_INFO.md).
The previous evidence, including every earlier requirement/prohibition mapping and measured phase
receipts, is preserved in [history](history/DOD_BEFORE_CSP_2026_10_28.md). Historical
measurements do not certify later revisions. "Done" below is limited to its stated local/demo scope.

| Done | Implemented — blocked for launch (needs X) | Not done |
| --- | --- | --- |
| Deterministic Decimal detector, summaries, insights, migrations; synthetic/handwritten F1 gates | Actual statement/receipt accuracy (needs owner private measurement) | Production launch, real-user beta and real financial-data processing |
| Offline tool-using chat, figure verifier and isolation/injection/privacy regressions | Gemini shared caps/kill switch/consent/fallback (needs paid project, billing/spend alerts and owner live evaluation) | Live Gemini evaluation |
| Disposable synthetic public demo; user uploads/password login disabled; local-only shared credential | Purge/retention code (needs always-on worker and monitoring) | Always-on deployed worker and separate staging |
| Verification/reset, rotating sessions/reuse/revocation/CSRF tested on local sibling-host TLS | Real account lifecycle (needs custom sibling domains/certificates and verified sender) | Real transactional sender/SPF/DKIM/DMARC/events |
| Eight real two-API/worker coordination/crash/quota/deletion checks | Durable jobs/restricted extraction (needs deployed worker resources and monitored operating procedures) | Production capacity or sustained stress claim |
| Separate-PG synthetic restore: 30 table counts/digests, ten exact API comparisons, restored login/dedupe/ownership/schema/deletion checks | Managed recovery (needs managed PITR, encrypted backup storage, retention and owner restore drill) | Managed PITR verification and production recovery-time objective |
| Nine k6 full flows, zero HTTP failures, machine/quotas/p50/p95 recorded | Load sanity only (needs realistic private staging workloads before capacity planning) | Free-host capacity claim |
| Strict production style CSP, nine compiled-browser checks and limited ZAP baseline with zero high/medium/low findings | Security hardening (needs authenticated testing) | Authenticated pentest; vulnerability-free claim |
| Local and hosted same-schema strict-CSP rollback/re-promotion; Vercel CI/API gate and automatic post-deploy smoke | API-hook controller and authenticated metadata checks locally verified (needs owner credential setup and hosted activation); staging/managed recovery still needed | Fully automatic API deployment enforcement until observed |
| Recursive build exclusions: zero private canaries in both contexts; 16 approved backend EMLs only; CI Docker COPY regression | Container deployment (needs production role/network/secret/monitoring review) | Production deployment certification |
| Local scheduler, retry, retention, content-free metrics and email-lifecycle tests | Operations/email/legal code (needs monitoring, incident contact, sender/DNS and qualified legal review) | Approved legal texts and human screen-reader pass |
| Synthetic mailbox/evidence worker lab, explicit owned bank matching, separate voluntary interests | OAuth protocol foundation (needs Google/security/legal approval, real runtime integration and private accuracy checks) | Actual Gmail callback/orchestration, real incremental sync and revocation delivery |
| Owner confirmed DB rotation 2026-10-22; MIT LICENSE present | Free PostgreSQL (needs PITR-capable replacement before 2026-11-19 or accepted demo-data loss) | Owner public/private repository decision |
| No invented provider offers or shared entitlements | Any commercial expansion (needs owner-led agreements/licensing and fulfilment design) | Provider partnerships, negotiated offers or fulfilment |

## Verification for this hardening change — 2026-10-28

- `make dev verify`: passed; migrations/readiness and original stack boot verified.
- `make test lint evaluate`: passed. **574 backend** (485.89s), **99 frontend** in 11 files
  (8.24s), **17 release-gate** tests. Final endpoint validation added one further test;
  current Node suite is **18 passed**. No financial application code changed.
- Ruff, ESLint, TypeScript, OpenAPI and generated-type drift passed. Detector P/R/F1=1.0000
  on synthetic16/0/0, handwritten-bank3/0/0 and handwritten-products5/0/0 TP/FP/FN.
  Extraction18-variant and receipt16/16 gates passed. Real-bank accuracy remains unmeasured.
- Browser profiles: **18 standard**, **one same-site TLS**, **one isolated public demo** and
  **nine compiled CSP** = **29 distinct passes**. Five profile skips in the standard command
  execute in their separate profiles. Chromium/Firefox/WebKit ran. See CSP_HARDENING.md for
  the exact native-select and screenshot harness limits; no header exception was added.
- Production build passed (8.68s Vite): main354.65kB/gzip111.73, lazy chart389.93/gzip114.22,
  mailbox11.84/gzip3.90. No capacity or performance SLA.
- `npm audit --audit-level=low`: zero; locked `pip-audit`: no known vulnerabilities.
- ZAP repeated on isolated local web/API: zero high/medium/low findings. Three informational
  discovery types remain. Private raw reports retain scanner exit2; no authenticated pentest.
- Initial combined run stopped at three deadline-classification Node failures after backend
  and component passes. The deadline handler was fixed; full combined re-run passed. Failed
  attempts, registry DNS and browser-harness issues remain in private logs, not pass counts.
- Secret scans, exact-commit hosted CI, native provider settings, paired publication and
  hosted rollback receipts are recorded in RELEASE_GATE.md as they are actually executed.

Earlier restore/load/coordination evidence remains in LOCAL_DRILLS.md and the historical DOD.
The previous 568-test count and inline-style warning are historical, superseded here.

## Guarantees retained

- All money remains Decimal/NUMERIC and API decimal strings; no client totals or LLM arithmetic.
- User scope comes from authentication; tools stay read-only; figure provenance is checked,
  not prose truth. SMTP retains send/commit ambiguity; console receipts are idempotent files.
- Uploads/detection remain idempotent; uncertainty never silently cancels a subscription;
  user decisions persist. No runtime create_all or destructive schema changes.
- Public demo remains synthetic-only with isolated disposable visitors and visible notices.
  Live receipt/Gmail/Gemini paths remain disabled; no paid resources, invitations or beta tag.
- Entire-history/current-source secret scans and dependency audits remain release gates.
  Three exact historical synthetic-JWT exceptions are not generalized production-secret ignores.
- SQL deletion cannot recall delivered emails, exports or backups. Restored sessions are copied
  for verification; revoke them and rotate operator secrets before any real restore is exposed.

## Owner actions

Managed PostgreSQL/PITR before free DB expiry 2026-11-19 or accepted demo-data loss; staging;
worker availability; sibling domains; verified sender/SPF/DKIM/DMARC; paid Gemini/billing/spend
alerts; legal review; incident contact; screen-reader pass; private statement/receipt accuracy;
live Gemini eval; repository visibility decision. DB rotation and MIT application are complete.

## Hosted receipts — October28

First 19799ee: all four CI jobs in 40612395352; paired revision and 24 smoke checks passed on repeat.
Follow-up b6cfbab: all four CI jobs in 40615294692; automatic success-triggered deployed smoke 40616602765
passed. Real hosted logs confirm574 backend,99 component,18 Node and29 browser passes. Hosted
rollback to strict 19799ee and restoration to b6cfbab both passed source verification and 24 smoke.
No DB downgrade, unsafe-CSP rollback, paid resources or live data/provider calls.

Owner completed Render repository selection on the existing app; it now appears on this repository.
After CI Checks Pass restored; Vercel auto-assign domains checked. Automatic API trigger still must
be demonstrated on the next push. Manual releases above happened only after green exact CI.
See RELEASE_GATE.md for IDs, timestamps, failures/retries and limits. Free demo remains NO-GO.

Follow-up2492cd2: all four CI jobs in 40635104548 passed; manual API publication verified. Its waiting
Vercel build timed out safely before API integration was repaired; old frontend remained live.
No successful retry is claimed. Render app access/source binding are now refreshed; fresh-push
automatic deployment remains unverified. See RELEASE_GATE.md for failures and next-gate scope.

## API-hook fallback — implemented, locally verified, activation blocked

576 backend,99 component,21 release-gate tests; full lint/types/contracts/evaluator; three-browser
main flow18, build and audits passed. Scoped metadata authorization and compiled-artifact credential
scan are tested with synthetic keys. API-hook mode needs owner service-hook/read-token setup in
CI_ACCESS_SETUP.md and real hosted verification before automatic deployment can be marked Done.
Native trigger remained unobserved after source refresh. No real credentials were read/generated.
