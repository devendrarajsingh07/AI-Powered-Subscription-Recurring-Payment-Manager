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
- A post-deployment GitHub workflow starts on Vercel `deployment_status: success`, verifies
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
