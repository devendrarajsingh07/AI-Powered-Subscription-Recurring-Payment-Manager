# Operator runbook — demo deployment, beta preparation

The current Render/Vercel deployment is free and synthetic-only. Phase 8 is not launch-ready.
Incident contact: **OWNER TO SUPPLY**. Grievance/support contact: **OWNER TO SUPPLY**.

## Deploy and verify

Run the documented Make gates; push a logical commit on the sole master branch and inspect
all four CI jobs. The native free-demo strategy uses Render **After CI Checks Pass** and the
Vercel normal build command `node scripts/deploy-gate.mjs && npm run build`. That command
requires exact repository/master push CI, matching ready API revision and a final master-head
check. Missing configuration, failed checks and timeouts fail the build; old production remains.
Set non-secret repository variables DEMO_API_URL and DEMO_WEB_URL for post-deploy verification;
Vercel reads the existing VITE_API_BASE_URL. No new token/deploy hook is required for this path.
October28 observation: the saved Render trigger did not automatically deploy19799ee. Owner has since saved Render app access for this repository; the next automatic trigger needs observation; never claim automatic enforcement from the dropdown
alone. Until repaired and demonstrated, an operator must verify all four exact-commit CI jobs
before Manual Deploy latest master. Keep After CI Checks Pass selected; never switch to On Commit.
Vercel still fails closed until that exact API revision is ready.

See [configuration, tests and publication receipts](RELEASE_GATE.md). Native integration is a
free synthetic-demo control, not staging or production release certification. Keep additive
migrations and verify readiness/version/security smoke. Never copy platform environment pages.

## Roll back

Render and Vercel expose previous deployments. Select the same last verified source revision on
both. Check Alembic compatibility before rollback; never downgrade a real database automatically.
Local and hosted same-schema rollback/re-promotion have run; see RELEASE_GATE.md for actual
strict-CSP artifacts, paired source/smoke results and limits. No separate staging or managed
DB recovery is established. Render dashboard rollback disables auto-deploy: after restoring the
approved release, save After CI Checks Pass again. Vercel Instant Rollback pauses promotion;
promote the approved artifact to undo it, then verify Auto-Assign Custom Production Domains
is checked. Never rollback to an unsafe policy or downgrade a real DB automatically.

## Containment

For suspected exposure: pause the affected service and registration, preserve content-free event
metadata privately, assess affected processors/records, rotate credentials via the platform owner,
and obtain legal guidance on notifications. Do not paste statements, connection URLs or keys into
public issues. Record timeline, containment, verified remediation and follow-up privately.

The deployed assistant uses `LLM_PROVIDER=fake`. Do not enable Gemini with real data until paid-tier
terms/billing, consent and Phase 8 controls are verified. Account-security changes bind JWTs to a
revocable session/account version. Logout revokes the current family; logout-everywhere and reset
revoke all families. Check PROJECT_INFO for deployment evidence before relying on a hosted revision.
Signing-key rotation invalidates tokens/digests and forces sign-in. Public demos use disposable
memory-only access sessions, never cross-site refresh cookies.

## Credentials, backups and deletion

Credential changes must be performed by the owner in the platform secret manager, never committed.
Use separate migration/app roles and per-environment keys before beta. The previously exposed
demo DB credential was rotated by the owner. Keep external DB ingress blocked and rotate again
if any subsequent exposure is suspected.
See [exact owner rotation steps and incident evidence](SECURITY_INCIDENT.md). Rotation completed 2026-10-22 (owner-confirmed).

Free PostgreSQL expires 2026-11-19 and has no PITR. There is no managed restore/PITR verification or retention
promise for this deployment. The isolated synthetic local dump/restore drill passed; it does not
verify recovery of the hosted database. Provision backed-up staging/production first, then perform a timed
restore to a separate DB and compare schema plus independently recorded synthetic row counts.
Do not dump private financial records to this repository or CI artifacts.

Settings deletion hard-deletes the account and owned rows and purges private dev outbox copies.
Delivered mail, operator exports, provider retention and future backups require separate handling.
Do not delete another user's data without their verified request and the operator's authorization.

## Monitoring and launch

Readiness, queue-age/depth, delivery failure, DB saturation and provider metrics/alerts are beta
requirements, not currently provisioned monitoring. Never use message bodies, amounts or raw
descriptions as metric labels. See [launch gates](LAUNCH.md); keep real-user invitations paused.

## Live-AI kill switch, caps and metrics

Force the offline assistant for everyone without a redeploy: `python -m app.llm_admin kill`
(`restore` re-enables, `status` prints flags and today's usage counts). `LLM_KILL_SWITCH=true` does the
same through the environment and is re-checked before every provider request, including later
rounds of a chat already in progress and transport retries. Global daily caps
(`LLM_GLOBAL_DAILY_REQUESTS`, `LLM_GLOBAL_DAILY_TOKENS`) are enforced per provider request: one
request plus an estimated budget (input characters / 4 + `LLM_MAX_TOKENS`) is reserved atomically
before each call and never refunded, so failed calls and category suggestions count. Requests
rejected by validation (unknown conversation, busy user) reserve nothing. Reaching a cap switches to
the visible offline fallback.
Set `OPS_METRICS_TOKEN` (32+ random characters, platform secret manager only) to enable
`GET /api/v1/ops/metrics` with header `X-Ops-Token`; without it the route answers 404. Watch queue
depth and oldest age, `dead_letter_total`, alert failures and the `email` suppression count.

## Email events and unsubscribe

After a provider reports a hard bounce or spam complaint, POST `{"address": ..., "kind":
"hard_bounce"|"complaint"}` to `/api/v1/ops/email-events` with the ops token. Matching accounts stop
receiving alert emails and see a Settings notice. No provider adapter is built or verified; real SMTP
delivery, bounce handling and SPF/DKIM/DMARC need an owner-provided sending domain.

## Automated release (opt-in) and rollback

The following is an alternative legacy path, disabled by default. Never run it alongside the native controller. `.github/workflows/deploy.yml` requires both `DEPLOY_ENABLED=true` and `DEPLOY_STRATEGY=legacy-secrets`. Before any
secret is used or any code is checked out it verifies that the commit (a) is on this repository's
master history, (b) has a successful **push-triggered** `checks` run for that exact SHA, and (c) for
an automatic run, is still the master head (an older run is skipped as superseded). Pull requests,
forks and other branches never reach the job; a manual run (`rollback_sha`, full 40-character SHA)
passes the same checks, so it can only redeploy previously verified master commits.

`scripts/release_demo.py` then releases exactly that commit, API first:
- Render: the deploy hook is called with `ref=<SHA>`. Render documents that deploying a specific
  commit through a hook **turns off the service's auto-deploy**, leaving releases to this pipeline.
  Success requires `/api/v1/health` to report `revision == SHA` (from Render's `RENDER_GIT_COMMIT`)
  and `/health/ready` to return 200, so an old healthy instance can never pass.
- Vercel: deploy hooks cannot target a commit, so the script waits for the READY production build
  Vercel made from git for that SHA and promotes it through the REST API. Success requires the
  frontend's `/version.json` to report that SHA.
Then `scripts/smoke_deployed.py` checks headers, exact-origin CORS and routing.

Owner configuration: variables `DEMO_API_URL` (ending `/api/v1`), `DEMO_WEB_URL`, `VERCEL_PROJECT_ID`
(and `VERCEL_TEAM_ID` for a team), secrets `RENDER_DEPLOY_HOOK_URL` and `VERCEL_TOKEN` (a
project-scoped token). In Vercel, turn off automatic assignment of the production domain so new
builds stay staged until promoted; otherwise Vercel still publishes every master build ungated.
To roll back, run the workflow manually with `rollback_sha` set to the last verified commit.
The workflow and script are tested against local stand-ins only (`tests/test_release_demo.py`)
and have never run against the live services. Migrations are additive; never downgrade a database.

## Client address behind a proxy

Auth rate limits key on the connecting address. Behind Render's proxy that is the proxy itself unless
`TRUSTED_PROXY_HOPS` is set (default `0`: `X-Forwarded-For` is ignored). Set it to the number of
proxies you control (check one real request's header first; on Render start with `1`). The limiter then
uses only the entry those proxies appended, never a client-supplied earlier one, and falls back to the
peer address if it is missing or not an IP.

`DATABASE_URL` may be given as `postgres://` or `postgresql://`; the app rewrites it to the installed
`postgresql+psycopg://` driver.

## Stop the optional synthetic mailbox lab

Set MAILBOX_LAB_ENABLED=false and restart both local API and worker; production/public demo must
never enable it. A worker rechecks consent/generation/claim between each item. Disconnect through
DELETE /api/v1/mailbox/connection (caller JWT) to purge evidence, jobs and OAuth state, even after
flag disablement. Account deletion also purges everything; independent voluntary interests have
DELETE /api/v1/interests. Neither action changes bank history. Do not log JWTs or request content.

The independent MAILBOX_TOKEN_KEY is used only by local OAuth protocol tests in this release.
Changing it makes old encrypted state unusable and requires reconnection; it never falls back to
JWT_SECRET. No live Gmail credential is configured on hosted demos. For any future approved live
integration, real provider revocation/retry, key rotation and backup retention require an audited
operator procedure before launch. Existing database-secret/session/incident runbooks still apply.

## Local operational rehearsal (synthetic data only)

See [commands, measurements and limitations](LOCAL_DRILLS.md). Use `make drill-prepare`,
`make drill-up`, then `make drill-coordination`, `make drill-restore`, `make drill-load`,
`make drill-scan`, `make drill-rollback`, `make drill-isolation` and `make drill-down`.
Never substitute normal or hosted credentials. The reserved project has no published ports;
HTTP probes run on its internal network. Original settings are restored after test profiles.

The restore compares all 30 table counts/digests and ten exact API responses, plus ownership
and upload dedupe; archive transfer/verification is part of the recorded total time. Its archive
is unencrypted, synthetic-only and git-ignored. Before any real restored environment is exposed,
revoke copied sessions, rotate operator secrets, and establish encrypted backup storage, retention
and authorization. None of these managed guarantees follows from this drill.

Rollback builds Git archives without creating branches or downgrading the DB. An incompatible
head is rejected by readiness. The verified previous/current revisions have identical business
code and schema; this does not establish rollback compatibility for arbitrary later migrations.
The October28 strict-CSP rescan has zero high/medium/low findings; no authenticated penetration test was run.

Anonymous GitHub metadata reads can hit public rate limits. The build gate must fail closed;
record the failure and retry after service/quota recovery. Never change headers/addresses to evade
quota or bypass the SHA/CI checks. If a wait expires before API readiness, keep the prior frontend
and retry the same approved source after readiness, or release a new fully checked master commit.
A submitted UI action is not a deployment receipt: verify the new artifact and public revision.

## API-hook controller (opt-in; owner setup pending)

See CI_ACCESS_SETUP.md. DEPLOY_STRATEGY=api-hook plus DEPLOY_ENABLED=true uses only the existing
service's RENDER_DEPLOY_HOOK_URL Actions secret. Render native auto-deploy must be Off. The job
checks successful exact push CI and current master before any checkout/deployment secret, calls
Render with exact ref, and waits for matching revision/readiness. Vercel's gated Git build then
proceeds; GITHUB_RELEASE_READ_TOKEN (Contents/Actions read only) avoids anonymous quota pressure
without going to API/web requests or client assets. CI uses its ephemeral read-only token.
No financial arithmetic/provider changes; failures remain closed. Use actual artifact receipts,
not a submitted UI action, as proof. No activation claimed until hosted CI/release/smoke pass.

Final local privacy follow-up: request construction is inside the sanitized exception handler;
malformed credential input cannot appear in errors.7 focused HTTP tests and the complete suite
passed:577 backend(463.52s),99 component(8.82s),21 release-gate tests, lint/types/contracts and
all evaluator gates. This supersedes the earlier576 count. Owner credential setup and actual
hosted automatic-release verification remain pending; no live-credential success is claimed.
