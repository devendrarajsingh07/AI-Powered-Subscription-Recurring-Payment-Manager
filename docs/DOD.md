# Definition-of-Done and launch-readiness evidence

Updated 2026-10-26. **NO-GO for real users.** Current instructions: [PROJECT_INFO](../PROJECT_INFO.md).
The previous evidence, including every earlier requirement/prohibition mapping and measured phase
receipts, is preserved in [history](history/DOD_BEFORE_LOCAL_OPS_2026_10_26.md). Historical
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
| Limited ZAP web/API baselines; findings disclosed, no high-risk alerts in that scope | Security hardening (needs inline-style CSP remediation/audit and authenticated testing) | Authenticated pentest; vulnerability-free claim |
| Local same-schema archived-source rollback/re-promotion; incompatible head refused readiness | Release pipeline code (needs enforced provider gate, separate staging and hosted rollback exercise) | Verified hosted rollback and CI-gated deployment enforcement |
| Recursive build exclusions: zero private canaries in both contexts; 16 approved backend EMLs only; CI Docker COPY regression | Container deployment (needs production role/network/secret/monitoring review) | Production deployment certification |
| Local scheduler, retry, retention, content-free metrics and email-lifecycle tests | Operations/email/legal code (needs monitoring, incident contact, sender/DNS and qualified legal review) | Approved legal texts and human screen-reader pass |
| Synthetic mailbox/evidence worker lab, explicit owned bank matching, separate voluntary interests | OAuth protocol foundation (needs Google/security/legal approval, real runtime integration and private accuracy checks) | Actual Gmail callback/orchestration, real incremental sync and revocation delivery |
| Owner confirmed DB rotation 2026-10-22; MIT LICENSE present | Free PostgreSQL (needs PITR-capable replacement before 2026-11-19 or accepted demo-data loss) | Owner public/private repository decision |
| No invented provider offers or shared entitlements | Any commercial expansion (needs owner-led agreements/licensing and fulfilment design) | Provider partnerships, negotiated offers or fulfilment |

## Verification for this operations change

- `make dev verify`: passed (47.375s).
- `make test lint evaluate`: passed (674.172s): **568 backend tests** (565.73s) and
  **99 frontend tests** in 11 files. Ruff/ESLint/types and OpenAPI/generated-type drift passed.
  Detector TP/FP/FN: synthetic 16/0/0, handwritten bank 3/0/0, products 5/0/0;
  P/R/F1=1.0000 each. Extraction gate and receipt outcomes 16/16 passed. Real-source accuracy unmeasured.
- Extra full backend run on the restored PostgreSQL service: **568 passed** (547.50s).
  These use separate fixture DBs, not the restored application rows. One upstream
  Starlette/TestClient/httpx deprecation warning remains in each backend run.
- Real-stack Linux/Docker browsers: **18 standard passes** (two profile skips), plus
  **one strict sibling-host TLS pass** and **one isolated public-demo pass**: **20 distinct cases**.
  Chromium/Firefox/WebKit ran; mobile light/dark axe, real imports/chat/outbox/privacy passed.
  Existing tracked screenshots and normal API/worker flags/clocks were restored byte-for-byte.
  Native Windows runner/cache limitations used the established Linux browser equivalent.
- Production build passed: main 354.65kB/gzip111.74, lazy mailbox 11.84/gzip3.90,
  chart 389.93/gzip114.22; Vite build 7.42s (full CLI 20.562s). No performance SLA.
- `npm audit --audit-level=low`: zero; `pip-audit -r backend/requirements.lock --disable-pip`:
  no known vulnerabilities. Root Ruff, k6 ESM syntax, isolated Compose configuration and
  real Docker build-context canary checks passed.
- Gitleaks entire pre-commit history (76 reachable commits) and current non-ignored source:
  no leaks found. Exact historical synthetic-JWT exceptions and the 16-fixture EML allowlist
  were not broadened. No .env/private statements/private emails/outbox are tracked.

Publication still requires exact-commit hosted CI; no hosted rollback is claimed.

Drill commands, real measurements, failed harness attempts and limits are in
[LOCAL_DRILLS](LOCAL_DRILLS.md). Detailed logs/tokens/reports and the unencrypted synthetic-only
archive remain ignored under var/drills. No hosted DB, real statements or live providers were used.
The extra pytest run uses separate test databases on the restored PG service; actual restored
rows are checked independently by table digests and API comparisons. Do not conflate the two.

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
