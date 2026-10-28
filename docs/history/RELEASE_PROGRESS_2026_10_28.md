# Archived release progress — 2026-10-28

Superseded by PROJECT_INFO and docs/RELEASE_GATE current receipts. Pending statements below
are historical observations, not current instructions.

# SubTrack — current-state handoff

Updated 2026-10-28. Sole current instruction source. Prior complete handoff and phase receipts:
[history](docs/history/HANDOFF_BEFORE_CSP_2026_10_28.md). Read README, docs/CSP_HARDENING.md,
docs/RELEASE_GATE.md, docs/DOD.md and actual code. Do not redo completed product phases.

## Current work: CSP hardening and free demo release verification

First strict paired release published as19799ee; follow-up workflow/receipt verification in progress:
- Production Vercel/nginx/preview policies require self-only scripts/styles/style elements and
  style-src-attr none. Vite HMR exceptions remain development-only. No nonce/hash workaround.
- Actual compiled build on read-only non-root nginx; nine Chromium/Firefox/WebKit cases pass:
  CSS attack probes, real registration/demo ingestion, charts/tooltips/tables, both themes,
  mobile/desktop, charge/chat dialogs, navigation, API-equal money and deletion.
- WebKit independently reports style-src-attr when constructing an unstyled native select.
  A minimal div/select probe reproduced this before app styling. Tests observe constructors
  without changing them, attribute only the bootstrap-origin reports, and require their exact
  count to match constructors. All application-origin reports and all CSS payload probes remain
  strict. WebKit screenshots inject their own style tag, so visual captures use Chromium/Firefox;
  WebKit functional/negative tests remain enabled. Do not claim zero raw WebKit console notices.
- Eighteen real local-HTTP/configuration Node release-gate tests pass. The key-free Vercel build gate waits
  for exact repo/master push CI, exact ready Render SHA, and rechecks head before build. It
  fails closed on missing/wrong metadata, errors/rate limits, old API, superseded SHA or timeout.
- Render native After CI Checks Pass is configured, but no automatic trigger was observed for19799ee; first API release was manual after CI. Repository app inspection found no Render attachment; existing installation settings require owner GitHub verification.
  Enabled After CI Checks Pass on October28 after local gates passed; saved setting visually verified. Root is already repository
  root, Dockerfile ./backend/Dockerfile, context ./backend; no build path filters.
- GitHub repository deployment secrets were absent on inspection. No new token is needed for
  the native integration path. Existing optional secret workflow additionally requires explicit
  DEPLOY_STRATEGY=legacy-secrets; never activate both controllers.
- New post-deploy workflow runs after Vercel commit-status success, verifies approved
  master history/CI before checkout, then exact paired revisions and read-only security smoke.
  It must not start before Render deploy, to avoid a check/deployment dependency cycle.

## Current measured results and gates

- `make dev verify` passed; `make test lint evaluate` passed: **574 backend** (485.89s),
  **99 components** (8.24s), initial17 Node release tests. Explicit endpoint validation added
  one test; final **18 Node** passed, plus lint/types/production build (10.63s) on final source.
- Browser wrapper passed **18 standard + one same-site TLS + one isolated public demo + nine
  compiled CSP = 29** distinct cases. Five standard-profile skips run separately. The wrapper
  restored normal API/worker flags/clocks and tracked screenshots. Chromium/Firefox/WebKit ran.
- Detector TP/FP/FN16/0/0,3/0/0,5/0/0: P/R/F1=1.0000 in each synthetic/handwritten set.
  Extraction18-variant and receipt16/16 gates passed. Real-source accuracy remains unmeasured.
- npm audit zero; locked pip-audit no known vulnerabilities. OpenAPI/types, Ruff/ESLint pass.
- Gitleaks scanned all80 pre-change reachable commits and current source: no leaks found.
  No private .env, outbox, statements or unapproved emails tracked; existing narrow exceptions unchanged.
- ZAP web/API rescan: zero high/medium/low findings in limited unauthenticated baseline;
  three informational discovery types remain. Raw scanner exit2 retained. No pentest claim.
- Private logs under ignored var/drills/csp-*. Initial Node deadline-classification failures,
  WebKit harness issues and Docker DNS interruption are retained; all final relevant checks pass.
- Non-secret GitHub variables DEMO_API_URL and DEMO_WEB_URL now saved. No new deployment secret.
- Remaining: verify native auto-trigger on follow-up (Render app repository access needs owner GitHub verification), status-trigger post-deploy workflow,
  strict-CSP same-schema hosted rollback/re-promotion and final receipts. Do not claim these yet.

## Publication rules

Exactly one local/remote branch: master. No worktrees/topic branches/PRs, force push, history
rewrite or beta tag. Baseline master 714ac03 passed all four hosted checks in run 40363921345.
Technical35677df and docs19799ee are pushed. Follow-up workflow/receipt edits remain uncommitted. Hosted run40612395352 passed all four jobs; both hosts serve19799ee and24 smoke checks pass. Verify current source versions before any live-version claim.
Repo: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager
Web: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1

Owner authorized finishing the remaining technical work and updating the existing free demo
after local/hosted gates. Render login was completed by the owner on 2026-10-28. No credentials
may be created/copied/read as a workaround. Use existing native integrations where possible.

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


---

# Free demo release gate

Design recorded before implementation, 2026-10-28. The owner keeps free hosting and a
synthetic-only demo. No accounts, paid resources, live providers or beta activation.

## Native integration path (no new deployment credentials)

- Render already has connected Git credentials for this repository/master and offers
  **After CI Checks Pass**. Enable that native option after the local gates pass.
- Vercel's production build command will run a bounded, fail-closed Node gate before Vite.
  Require the exact repository/master SHA, a successful push-triggered `ci.yml` run for that
  SHA, current master membership, and that the Render API serves that SHA with readiness200.
  Recheck the branch before approval. No financial endpoints, credentials or write APIs.
- Use the normal build command (zero success, nonzero failure), not an ignored-build-step
  inversion. Missing metadata, HTTP/parse/rate-limit errors, a failed CI run, superseded commit,
  wrong backend revision or timeout must keep the old production deployment active.
- Public GitHub reads need no key. Keep polling bounded and sparse to reduce anonymous rate
  limits. A future private repository requires a reviewed authenticated alternative; it fails
  closed with this configuration. Waiting consumes the existing free build allowance and may
  fail at its limits; it never authorizes a paid upgrade.
- Endpoint configuration is explicit: Vercel reads the existing production VITE_API_BASE_URL;
  post-deploy verification reads repository variables DEMO_API_URL (ending /api/v1) and
  DEMO_WEB_URL. Only HTTPS URLs without credentials, queries or fragments are accepted.
  These are public addresses, not secrets. Eighteen local HTTP/configuration tests pass.
- A post-deployment GitHub workflow starts on Vercel commit-status success, verifies
  approved master history before checkout, and checks exact frontend/API revision plus headers
  and CORS. Do not start that job at CI completion: Render waits for all check runs, which could
  otherwise form a wait cycle. Observed Vercel results on714ac03 use the separate commit-status
  API, while the four CI jobs use check runs. Fail-closed timeouts protect against future changes.
- Keep the existing optional secret-based deploy workflow disabled (it now also requires an
  explicit `DEPLOY_STRATEGY=legacy-secrets`, preventing two release controllers); repository secret names
  were absent when inspected. Do not create, expose or copy a token as a workaround.
- Roll back only to a previously green, same-schema **strict-CSP** demo release. No DB downgrade,
  new accounts/real uploads, or weakening the new policy. Re-promote current, restore Render's
  CI trigger (dashboard rollback disables auto-deploy), and verify both revisions/readiness.

## Verified provider behavior used in this design

- [Render CI gating](https://render.com/docs/deploys): zero or failed checks do not deploy;
  success/neutral/skipped conclusions are accepted by the native gate.
- [Render rollback](https://render.com/docs/rollbacks): dashboard rollback disables auto-deploy.
- [Render free limitations](https://render.com/docs/free): only the two recent previous artifacts
  are retained for rollback; this is a demo rehearsal, not managed production recovery.
- [Vercel builds](https://vercel.com/docs/limits): build time remains bounded by the free plan.
- [Vercel GitHub integration](https://vercel.com/docs/git/vercel-for-github): deployment-status
  events support post-deployment verification without a new token.

Results, configuration evidence and remaining human/paid launch requirements will be recorded
after execution. This design does not establish managed PITR, staging or production readiness.

## Local/configuration receipt — October28

Full local gates passed: backend574, components99, final Node18, browser29, evaluator F1=1.0000
on all three committed sets, lint/types/contracts/build, zero known audit vulnerabilities,
whole-history80-commit/current-tree Gitleaks no leaks. Compiled strict-CSP ZAP rescan has zero
high/medium/low findings. Detailed counts and limits: DOD.md and CSP_HARDENING.md.

Render's existing free service srv-dbbha7bbc2fs73b770j0 saved **After CI Checks Pass**;
visual confirmation captured outside the repo. Repository/master, root, Dockerfile/context and
health check were inspected; no credentials displayed or changed. GitHub non-secret URL variables
were saved; deployment secrets remain absent. Vercel's new gate is supplied by checked-in config.
No new account, token, hook or paid plan was created. Hosted commit/CI/deploy/rollback receipts
remain pending until publication and observation; baseline714ac03 is still the deployed version.

Post-push integration observation: public GitHub deployment metadata returned an empty list,
while the exact commit has a legacy `Vercel` pending/success status. The post-release workflow
was corrected to `status` with exact context/state filtering, rather than relying on an
unobserved deployment event. It still verifies successful push CI, master ancestry and paired
source versions before its read-only smoke. Pending/error statuses skip the job; Render uses
check runs, not this legacy status. First publication is verified manually as well.

### First strict release (publication in progress)

Source19799eee9f750d7c110eb80ec6c99074bbc44601 (technical35677df, documentation19799ee)
passed all four hosted jobs in run40612395352. Vercel buildHyS4RkTfYrUrXoQ55tBi6AdzmJRu
was observed holding first for exact CI and then matching API readiness. The persisted Render
checks-passed setting did not produce an observed auto-trigger for this commit. A manual latest
master deploy was started only after green CI: dep-dbgksglg1s2s73bl4pqg. Automatic triggering
remains unverified; do not equate a saved setting with demonstrated enforcement. No weaker
On Commit trigger was enabled. Publication is checked independently before marking success.

### First paired publication verified — October28 06:54 IST

Both public version endpoints report19799eee9f750d7c110eb80ec6c99074bbc44601. Render
`dep-dbgksglg1s2s73bl4pqg` succeeded; Vercel `HyS4RkTfYrUrXoQ55tBi6AdzmJRu` is Ready,
Production/Current, source master19799ee (23m31s including fail-closed wait). The frontend was
observed waiting for CI and then API; it published only after matching API readiness.

Read-only smoke repeated after an initial unavailable health request: **24/24 passed** on
both hosts, including strict CSP, headers, exact-origin CORS and private/ops route restrictions.
The first attempt's seven failures all derived from that single health request; its report is
retained, not counted as success. Public config remains `public_demo_only=true`, demo sessions,
receipt imports off and unapproved legal acceptance off. No account data was read or changed.

Repository app inspection shows no Render app attached to this repository. Opening the existing
account-level Render installation requires GitHub identity verification; owner action requested.
No app permissions have been granted/expanded. Native Render auto-trigger is not yet demonstrated.
The first deployment was explicitly manual after all green checks; do not claim full automatic
API release enforcement from that observation. The follow-up status-trigger workflow syntax and
read-only permissions were locally parsed/checked; its actual event execution remains to verify.
