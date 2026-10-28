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
