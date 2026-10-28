# Free demo release gate — verified receipts

Updated 2026-10-28. Free hosting, synthetic-only demo, beta locked. Current instructions: PROJECT_INFO.
No new account, deployment token, hook, paid plan, live provider or real-data access was created.
Historical progress/failures are preserved in history/RELEASE_PROGRESS_2026_10_28.md.

## Current outcome

- Vercel exact-CI/API build gate and automatic post-release verification are demonstrated.
- Hosted same-schema strict-CSP rollback/re-promotion is demonstrated; no database restore claimed.
- Render's native checks-passed setting is saved/restored. The first two releases required manual
  deployment after green CI. Owner has since saved repository access on the existing Render GitHub
  app (Only select repositories); its attachment is now visible on this repository. **Observe the
  next green master push before claiming automatic API deployment.** No agent access grant occurred.
- No new secrets are needed. Public endpoint variables DEMO_API_URL and DEMO_WEB_URL are saved;
  Vercel uses VITE_API_BASE_URL and exposed source metadata. Private repository conversion needs
  a reviewed replacement for anonymous GitHub metadata reads, which otherwise fail closed.

## Actual releases and checks

| Source | Hosted CI | API artifact | Frontend artifact | Outcome |
| --- | --- | --- | --- | --- |
|19799eee9f750d7c110eb80ec6c99074bbc44601|40612395352, all four success|dep-dbgksglg1s2s73bl4pqg|HyS4RkTfYrUrXoQ55tBi6AdzmJRu|Paired source  + 24 smoke passed|
|b6cfbab8b4adee4c056d9e7fac09c7be6bf200d7|40615294692, all four success|dep-dbgl568ae00c73couq9g|C8SEsrScQmjT5Kv1EQU3YToyMPC2|Paired source + automatic smoke 40616602765 passed|
|Rollback to 19799ee (source 19799ee)|Previously green ancestor|dep-dbglafh42hec73ddhji0|HyS4RkTfYrUrXoQ55tBi6AdzmJRu|Paired source  + 24 smoke passed|
|Restore b6cfbab|Previously green master|dep-dbglc8vb9u1s738l1cfg|C8SEsrScQmjT5Kv1EQU3YToyMPC2|Paired source  + 24 smoke passed|

The first API releases were explicitly manual after CI; the saved setting alone was not called
proof. First frontend build waited for CI and then matching API, publishing after readiness;
23m31s included its fail-closed wait. The follow-up status workflow skipped the pending event
(run 40615299506), then ran successfully on actual Vercel success(run 40616602765). It verifies
approved master history and exact push CI before checkout; no financial endpoints or secrets.

Hosted b6cfbab logs: 574 backend(201.59s),99 component,18 release-gate tests;18 standard browser
passes(5.4m) +1 public-demo(6.3s) +9 compiled CSP(22.0s) +1 same-site =29 distinct passes.
Five profile skips run separately. Local final results and detector/audit/scan limits: DOD.md.

## Rollback rehearsal and limits

Vercel Instant Rollback selected exactly the immediately previous strict-CSP19799ee artifact.
Render rollback selected its matching artifact; no Alembic downgrade, credential change or user
record mutation. CLI source verifier accepted only the CI-approved master ancestor. All24 smoke
checks passed, including strict styles/CORS/headers/readiness. Rollback verification window:
2026-10-28 07:22:28.739333–07:23:38.179144 IST, **69.439811s**, including polling and smoke.

Restored API b6cfbab first, then promoted the matching frontend. Vercel explicitly said promotion
undoes Instant Rollback; auto-assign custom domains is checked again. Render rollback had turned
Auto-Deploy Off; After CI Checks Pass was saved again. Post-idle roll-forward verification:
10:17:35.095837–10:19:00.901582 IST, **85.805745s**, including polling, wake-up and smoke.
These are verification-command wall times, not downtime/RTO/SLA. An owner-verification pause
occurred between actions; do not interpret the gap as a service outage or managed recovery test.

First smoke attempt had one unavailable health request, producing7 derived failures; subsequent
24/24 passed. The failed log is retained. One Vercel rollback dialog disappeared on a data-refresh
failure before submission; reopening the exact artifact succeeded. No false success was recorded.
Public browser shows the persistent demo banner and isolated-session button, no password form.
Config remains demo-only, receipt imports off, legal drafts unapproved. No account was read/changed.

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
- [Vercel GitHub integration](https://vercel.com/docs/git/vercel-for-github): Git-connected deployment behavior.
  This repository was observed using legacy Vercel commit statuses, not deployment records.

This design does not establish managed PITR, staging or production readiness.
