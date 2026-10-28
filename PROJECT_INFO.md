# SubTrack — current-state handoff

Updated 2026-10-28. Sole current instruction source. Earlier complete handoffs, phase receipts and
release progress are preserved in [history](docs/history/). Read README, docs/DOD.md,
docs/RELEASE_GATE.md, docs/CSP_HARDENING.md and actual code. Do not redo completed product phases.

## Current state

- Strict production CSP is implemented and deployed: self-only scripts/styles/style elements,
  style-src-attr none. Real charts, dialogs and themes work; no nonce/hash/inline workaround.
- Last recorded verified paired demo release: **b6cfbab8b4adee4c056d9e7fac09c7be6bf200d7**.
  All four hosted jobs passed in run 40615294692; automatic post-deploy smoke 40616602765 passed.
  Exact source verifier and 24 deployed headers/CORS/routing checks pass. Public browser shows
  isolated disposable sessions and the persistent synthetic-only banner; no password/file uploads.
- Hosted same-schema rollback to strict release 19799ee and re-promotion to b6cfbab both passed
  paired source verification and 24 smoke checks. No DB downgrade or older unsafe CSP. Vercel
  auto-assign domains is checked again; Render After CI Checks Pass restored after rollback.
- The first two API deployments were manual, only after all exact-commit CI jobs passed.
  Their native trigger did not run because Render lacked access to this repository. Owner has
  now completed GitHub verification and repository selection: Render appears on the repository's
  installed-app list; SubTrack is saved under Only select repositories. No agent permission grant,
  new account, token or paid plan. **Automatic API deployment still needs observation on the next push after source refresh.**
- Vercel's fail-closed build waits for exact master push CI, exact ready API SHA and rechecks head.
  The post-release workflow uses observed legacy Vercel success statuses, verifies approved history
  before checkout, then paired source and 24 smoke checks. Pending statuses correctly skip it.
  No dependency cycle. Optional secret-based controller remains disabled unless explicitly selected.
- Commit2492cd2 passed all four CI jobs in 40635104548. Its API was manually deployed after
  green CI as dep-dbgoccflk1mc73938d80. Vercel correctly timed out after 25m waiting for the API
  while integration was being diagnosed; frontend stayed b6cfbab. Manual retry requests did not
  produce an observed deployment; do not report them as success. Local anonymous GitHub
  metadata verification also failed closed on403/quota; no quota bypass or timeout change.
- Render's source binding has now been refreshed to the same repo through Git Provider:
  master/Docker, existing Dockerfile/context/command preserved, After CI Checks Pass verified.
  A fresh push is the remaining automatic-trigger test; if it fails, keep manual green-only
  deployment and label automation unresolved rather than claiming completion.
- Follow-up edits are factual receipt/docs changes. Run doc/secret checks, commit directly to
  master, push, confirm all four CI jobs, observe native Render trigger, then paired Vercel release
  and automatic smoke. Do not declare that trigger verified before it actually runs.

## Verified commands and counts

- `make dev verify`: passed; normal stack restored and health checked after isolated cleanup.
- `make test lint evaluate`: passed locally:574 PostgreSQL tests(485.89s),99 component tests
  in11 files(8.24s), initial17 Node tests. Final endpoint validation added one: **18 Node tests**
  pass; final frontend lint/types/OpenAPI-type drift/production build pass(10.63s Vite).
- Hosted b6cfbab logs independently confirm574 backend(201.59s),99 component,18 Node and
  **29 distinct browser passes**:18 standard,1 strict same-site TLS,1 isolated public demo,
  9 compiled CSP across Chromium/Firefox/WebKit. Five standard skips run in separate profiles.
- Detector TP/FP/FN:16/0/0 synthetic,3/0/0 handwritten bank,5/0/0 handwritten products;
  precision/recall/F1=1.0000 each. Extraction18-variant and receipt16/16 gates pass.
- npm audit zero; locked pip-audit no known vulnerabilities; Ruff/ESLint/types/contracts pass.
- Whole-history Gitleaks:83 reachable commits and current source, no leaks. No private .env,
  outbox, statements or unapproved emails tracked. Narrow historical synthetic exceptions unchanged.
- Repeated local ZAP: zero high/medium/low findings; three informational discovery types remain.
  Raw scanner exit2 retained; no authenticated pentest or vulnerability-free claim.
- WebKit reports native unstyled select construction; tests characterize it separately with exact
  bootstrap-origin/constructor counts. All app violations and CSS payload probes remain fatal.
  Playwright's WebKit screenshot preparation injects CSS, so captures use Chromium/Firefox;
  WebKit functional/negative tests still run. See CSP_HARDENING.md, not a zero-raw-warning claim.
- Private logs/screenshots remain outside tracked source. Initial Node deadline-classification
  failures, browser harness issues, DNS interruption and first unavailable hosted health request
  are retained; successful retries are reported separately. Human screen-reader check not performed.

## Publication rules

Only one local/remote branch: **master**. No worktrees/topic branches/PRs, force push, history
rewrite or beta tag. Technical35677df, first strict 19799ee, corrected status/receiptb6cfbab.
Latest docs-only receipt commits run the same CI; final publication must be checked by exact SHA.
Repo: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager
Web: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1
No new credential may be created/copied/read as a workaround. Keep hosted access synthetic-only.

## Preserved product state and limits

Deterministic Decimal detection/aggregation, scoped auth, upload progress/dedupe, advisory
insights, alerts, read-only grounded chat, relative demo loading and deletion remain intact.
Migration0017_mailbox_lab is current; no runtime create_all or destructive schema changes.
Synthetic receipt/mailbox lab, consent/leases/checkpoints/evidence matching and voluntary
interests are locally verified, but live Gmail callback/incremental sync/revocation are NOT
implemented or enabled. MAILBOX_LIVE_ENABLED=true fails configuration. Hosted lab flags stay off.
No offers, provider agreements, redistribution rights, invoice ledger or FX matching exist.

Local operations already completed: eight two-API/worker crash/shared-limit/deletion checks,
30-table synthetic restore equality, nine k6 flows, local same-schema rollback. Details and
limits are in docs/LOCAL_DRILLS.md. Old CSP finding is superseded locally by the rescan above.

Keep hosting free, fake LLM/console demo mode, production fail-closed, beta locked, Architecture A,
PostgreSQL coordination, bcrypt and strict SameSite/CSRF. No paid provisioning, accounts/terms,
real users/data, live Gmail/Gemini, provider contact or new stretch features. Public demo remains
isolated/disposable/synthetic-only with password login and uploads disabled. Legal drafts off.

## Owner/launch requirements that cannot be claimed complete

Managed PostgreSQL/PITR before 2026-11-19 or accepted demo-data loss; separate staging; always-on
worker; sibling custom domains; real transactional sender/SPF/DKIM/DMARC; monitoring and incident
contact; paid Gemini/billing/spend alerts; qualified legal review; human screen-reader pass;
private real-statement/receipt accuracy; owner live Gemini evaluation; repository visibility.
Public unauthenticated GitHub gating requires this repo to remain public or a reviewed replacement.
No managed recovery, capacity SLA, authenticated pentest or production-readiness claim.
DB rotation was owner-confirmed 2026-10-22. MIT LICENSE is present, copyright 2026 DEVENDRA RAJ SINGH.
Do not repeat obsolete requests to rotate that credential or choose/apply the license.
