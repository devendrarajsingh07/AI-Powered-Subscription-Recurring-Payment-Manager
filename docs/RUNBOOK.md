# Operator runbook — demo deployment, beta preparation

The current Render/Vercel deployment is free and synthetic-only. Phase 8 is not launch-ready.
Incident contact: **OWNER TO SUPPLY**. Grievance/support contact: **OWNER TO SUPPLY**.

## Deploy and verify

Run the documented Make gates; push a logical commit and inspect every GitHub job. Vercel currently
auto-deploys master; Render is manual. Together they do **not** yet enforce a green-CI deployment gate.
Do not call this production CI/CD. For beta, disable that trigger and implement an authenticated
post-CI release with a separate migration step, staging smoke and backward-compatible migrations.
Verify `/api/v1/health` and `/api/v1/health/ready`, then the frontend registration/login and offline
chat paths with synthetic data. Never copy platform environment pages into logs or issues.

## Roll back

Render and Vercel expose previous deployments. Select the same last verified source revision on
both. Check Alembic compatibility before rollback; never downgrade a real database automatically.
No staging rollback drill has run, so this is a procedure to verify, not evidence of recovery.

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
Use separate migration/app roles and per-environment keys before beta. The retained previously
exposed demo DB credential must be replaced before any real data. Keep external DB ingress blocked.
See [exact owner rotation steps and incident evidence](SECURITY_INCIDENT.md). Rotation completed 2026-10-22 (owner-confirmed).

Free PostgreSQL expires 2026-11-19 and has no PITR. There is no verified restore procedure or retention
promise for this deployment. Provision backed-up staging/production first, then perform a timed
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

`.github/workflows/deploy.yml` runs only when repository variable `DEPLOY_ENABLED=true`. Before any
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
