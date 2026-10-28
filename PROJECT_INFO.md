# SubTrack — current-state handoff

Updated 2026-10-28. Sole current instruction source. Earlier phases and release progress are in
[history](docs/history/). Read README, docs/DOD.md, docs/RELEASE_GATE.md, docs/CI_ACCESS_SETUP.md
and actual code. Do not redo completed product phases or repeat the unsuccessful native attempt.

## Current outcome / next step

- Strict production CSP deployed: self-only scripts/styles/style elements, style-src-attr none.
  Actual compiled charts/dialogs/themes and CSS attack probes pass in all three browsers.
- Last recorded verified paired demo release: b6cfbab8b4adee4c056d9e7fac09c7be6bf200d7,
  CI 40615294692 and automatic post-deploy smoke 40616602765. Hosted same-schema rollback to
  strict 19799ee and restoration both passed source verification and 24 smoke checks; no DB downgrade.
- Current API is manually published 5d9f4ce (green CI 40638645278); frontend remains strict b6cfbab.
  Financial application code is unchanged between these receipt commits. Latest paired release
  is NOT claimed. Waiting builds failed closed; failures and retry observations are preserved.
- Native Render After CI Checks Pass did not trigger after owner repository access and source
  binding refresh. Do not claim it fixed or retry it indefinitely. Replacement **api-hook** mode
  is implemented in the existing guarded workflow and disabled pending owner setup.
- Local code 35f4134 plus the sanitized-input privacy follow-up are committed on master. They
  have NOT been pushed while credential entry is in progress. Only one branch: master.
- **Credential setup:** after the owner's explicit transfer instruction, the existing Render hook
  was saved as encrypted repository Actions secret RENDER_DEPLOY_HOOK_URL and its saved name
  verified. No credential was generated or rotated; its value was not printed or stored locally.
- Vercel Production still has no GITHUB_RELEASE_READ_TOKEN. The owner generated a scoped token,
  but its one-time tab is now closed and it cannot be retrieved. The prepared Vercel Secret form
  awaits the owner's retained copy (or owner-created replacement if lost). Do not create a new
  credential or inspect entered values. Verify saved names only; keep activation off meanwhile.
  See CI_ACCESS_SETUP.md. Only the GitHub hook step is complete; no new hosted release is claimed.
- Then set repository variables DEPLOY_STRATEGY=api-hook and DEPLOY_ENABLED=true; set Render
  native Auto-Deploy Off (one controller); push current local master. Require all four exact-commit
  CI jobs, the API-hook job's matching SHA/readiness, Vercel's matching version, and automatic
  paired-source/24-check smoke. Record actual results before marking automation Done.
- API-hook mode uses current master only, successful exact push CI/repository checks before
  checkout/deployment credentials, and no Vercel deployment token. Superseded jobs skip. Vercel
  retains its exact-CI/API build gate; read token goes only to repository metadata URLs. CI uses
  its ephemeral read-only token. Literal credential scanning also runs on compiled output.

## Latest real local verification

- Full `make test lint evaluate`: **577 PostgreSQL tests** (463.52s), **99 component tests** in
  11 files (8.82s), **21 release-gate tests**, Ruff/ESLint/types/OpenAPI/generated-type drift pass.
- Focused release HTTP suite: 7 passed, including API-only without Vercel credentials, exact-revision
  waiting, invalid-mode refusal and malformed-hook error redaction. Host-venv attempt lacked bcrypt;
  the real Docker dependency environment and complete suite passed. No real credential in tests.
- Detector TP/FP/FN: 16/0/0 synthetic; 3/0/0 handwritten bank; 5/0/0 products: P/R/F1=1.0000 each.
  Extraction 18-variant and receipt 16/16 gates passed. Real-source accuracy remains unmeasured.
- Latest three-browser main flow: 18 passes (384.719s), five profile skips. Existing separate
  strict same-site 1/public-demo 1/compiled-CSP 9 also passed in prior full hosted runs (29 total);
  the next hosted run repeats them for the new release code. Normal flags/clock/screenshots restored.
- Final frontend production build 12.24s, with a synthetic build-only credential absent from the
  actual compiled output. npm audit 0, locked pip-audit no known vulnerabilities. No new dependency.
- Whole-history/source Gitleaks passes; narrow historical synthetic exceptions unchanged. No .env,
  outbox, private statements or unapproved emails tracked. Private receipts: ignored var/drills.
- Repeated before credential activation: entire history87 commits and current source scan both
  found no leaks. This is a scan receipt, not a claim that the missing Vercel token is configured.
- Local ZAP rescan: zero high/medium/low findings, three informational discovery types. Raw exit 2
  retained; no authenticated pentest or security-certification claim.
- WebKit emits native unstyled-select reports; tests require exact bootstrap-origin/constructor
  counts, while all app-origin violations and CSS payload probes remain fatal. Its screenshot
  helper injects CSS, so captures use Chromium/Firefox; WebKit functional/negative tests still run.

## Publication / privacy rules

Only master locally/remotely; no branches/worktrees/PRs, force push, history rewrite or beta tag.
Owner creates any new scoped credentials. The existing-hook transfer was explicitly authorized;
never print credentials, commit them, or collect owner-entered token form contents.
No paid resources, new accounts/terms, real users/data, live Gmail/Gemini or provider contact.
Repo: https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager
Web: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1

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
