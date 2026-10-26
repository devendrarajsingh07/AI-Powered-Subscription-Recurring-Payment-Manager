# SubTrack — current-state handoff

Updated 2026-10-26. This is the sole current instruction source. Read README,
[local drill evidence](docs/LOCAL_DRILLS.md), [DOD](docs/DOD.md), the runbook and real code.
The complete preceding handoff is preserved in
[history](docs/history/HANDOFF_BEFORE_LOCAL_OPS_2026_10_26.md); its old branch instructions and
"drills not run" statements are superseded. Do not repeat completed product phases.

## Current task: local operational verification

Implemented and exercised using synthetic data only:
- Separate internal-only `subtrack-drills` Compose project; two APIs, separate worker,
  credential-free/network-free extractor, web proxy, separate source and restore PostgreSQL.
  No published ports, hosted credentials, normal DB dumps or live providers.
- Eight real HTTP/coordination checks: worker SIGKILL/reclaim, duplicate concurrent uploads and
  ownership, shared previews/chat/auth windows, API SIGKILL/chat expiry, queue admission,
  queued deletion and deletion during extraction. Jobs use actual CSV/OCR handlers.
- Synthetic dump/restore: all 30 table counts/canonical row digests and ten exact API responses
  match; restored login/dedupe/ownership/schema/deletion behavior verified. No managed PITR claim.
- k6: three VUs x three iterations, nine verified CSV/PDF/OCR/review/import/chat flows,
  553 requests, 580 checks, zero HTTP failures. HTTP p50/p95 11.59/79.60ms; whole flow
  14.14/19.30s. Machine and explicit local quota overrides are in LOCAL_DRILLS.md.
- ZAP passive local baselines completed with warnings: one medium style-src unsafe-inline finding
  remains, plus informational SPA/auth/session notices. Not a pentest or authenticated audit.
- Git-archive source rollback/re-promotion, exact frontend/API revision and unchanged DB/summary;
  incompatible head16 correctly refused readiness against head17. Previous/current business code
  is identical, so this is a same-schema source rehearsal, not arbitrary feature rollback evidence.
- Recursive Docker exclusions proven by actual COPY canaries: zero nested private canaries,
  exactly 16 approved backend synthetic EMLs, no frontend EMLs. CI repeats this check.
- Fourteen guard tests prevent normal/remote targets, unsafe SQL targets, unowned container
  removal, private-settings overwrite and unsanitized scanner evidence publication.

Private results, logs, tokens and the unencrypted synthetic-only backup live in ignored var/drills.
Never commit them. Restore outbox is separate from source outbox. `make drill-down` preserves
volumes/evidence and stops only the drill project. No application feature, schema or hosting
configuration changes are part of this task.

## Current verification

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

The initial extra restored-service run failed five tests due to inherited drill environment
values and a fake HTTP fixture ordering race. The corrected standard-test environment and
commit-before-503 fixture passed both complete suites. Privacy assertions and runtime behavior
were unchanged. Failed receipts remain private. Exact-commit hosted checks must still pass
before publication is considered verified; consult the checks workflow, not an older receipt.

The previous app baseline is 92b9ae6; master 67d5a31 adds documentation only. Hosted checks
40336004197 passed on 67d5a31 (deploy-demo skipped). These historical receipts do not certify
this operations revision. Full preceding receipts, screenshots and UI details remain in history.

## Existing expansion capabilities and limits

Local-only optional synthetic receipt review/import and mailbox lab are complete: versioned
consent, allowlisted 16-fixture worker sync, fenced leases/checkpoints/quotas/TTL, separate receipt
evidence, explicit owned bank-charge matching, disconnect/purge/export and separate voluntary
interests. Receipt evidence never enters financial summaries/detection/savings/chat. Interest
counts use separate consent and threshold suppression; no provider contact or offers exist.
OAuth PKCE/state/encryption and bounded HTTP methods have local stand-in tests, but actual
Google callback/orchestration, real incremental inbox sync and revocation delivery are NOT built.
`MAILBOX_LIVE_ENABLED=true` fails configuration. Both receipt/lab flags remain off on hosted demo.
Additive migration0017_mailbox_lab is current; no create_all or runtime financial math changed.

## Publication and hosting rules

Keep exactly one local and remote branch: **master**. Work directly there, commit logically,
run local gates before pushing and inspect exact-commit hosted CI. No topic branches, force-push,
history rewrite or beta tag. Divergent historical local branches were saved in an ignored bundle
before removal. Vercel's existing Git integration rebuilds master automatically; manual Render
promotion requires green CI and explicit scope. This local-operations task makes no manual
hosting/deployment changes. Check health.revision/version.json before claiming any live revision.

Repository: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager
Frontend: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1

## Owner constraints and remaining launch work

Hosting stays **free**, production fail-closed and beta locked. No paid resources, account/terms
creation, real users/data, live Gmail/Gemini or provider contact. Preserve Architecture A,
PostgreSQL coordination, bcrypt, strict SameSite/CSRF, offline deployed mode, Decimal money and
educational/public-demo notices. Hosted visitors stay isolated/disposable/synthetic; password
registration/login and file uploads remain disabled. Legal drafts remain unapproved/off.

Remaining: managed PostgreSQL/PITR before free DB expiry 2026-11-19 or accepted demo-data loss;
separate staging; deployed always-on worker; sibling custom domains; real sender/SPF/DKIM/DMARC;
monitoring/incident contact; paid-tier Gemini/billing/spend alerts; legal review; screen-reader
pass; private real-statement/receipt accuracy; live Gemini eval; repository visibility decision.
Local stand-ins do not complete those gates. Hosted rollback and enforced provider CI gating
have not been exercised. ZAP inline-style finding remains. Backup encryption/retention and
revocation of copied sessions must be established before any real restored service is exposed.
SQL deletion cannot recall delivered email, exports or managed backups.

Owner confirmed DB rotation 2026-10-22. MIT LICENSE is present, copyright 2026 DEVENDRA RAJ SINGH.
Do not repeat obsolete rotation/license action requests. No provider agreement, redistribution
rights, full reconciliation, invoice identity, FX matching or mail-only ledger is claimed.

## Operations publication checkpoint

Technical commit 14afdaa contains the verified tooling and build-context fix. Documentation is
committed separately. All local gates passed before publication; exact-HEAD hosted CI remains
the final check. `make drill-down` removed only the isolated project (volumes/evidence retained),
and subsequent `make verify` passed all three normal-stack checks. No manual hosting changes.

## Hosted browser-runner correction

Run 40359305930 on 52b0f7c passed main checks, secrets and strict auth. The full browser job
stalled before tests while apt downloaded 185 packages from the Ubuntu 26.04/resolute mirror
(selected by floating ubuntu-latest). This was observed in its live GitHub log, not inferred
from a test failure. Browser jobs now pin ubuntu-24.04, matching the successful local Noble
runner, with an eight-minute installation limit and 30-minute job bound. No browser, assertion
or test was disabled; the follow-up commit requires its own complete hosted CI result.
