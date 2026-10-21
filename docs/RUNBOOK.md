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
See [exact owner rotation steps and incident evidence](SECURITY_INCIDENT.md). Rotation is pending.

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
same through the environment. Global daily request/token caps (`LLM_GLOBAL_DAILY_REQUESTS`,
`LLM_GLOBAL_DAILY_TOKENS`) switch to the visible offline fallback when reached; tokens are estimated.
Set `OPS_METRICS_TOKEN` (32+ random characters, platform secret manager only) to enable
`GET /api/v1/ops/metrics` with header `X-Ops-Token`; without it the route answers 404. Watch queue
depth and oldest age, `dead_letter_total`, alert failures and the `email` suppression count.

## Email events and unsubscribe

After a provider reports a hard bounce or spam complaint, POST `{"address": ..., "kind":
"hard_bounce"|"complaint"}` to `/api/v1/ops/email-events` with the ops token. Matching accounts stop
receiving alert emails and see a Settings notice. No provider adapter is built or verified; real SMTP
delivery, bounce handling and SPF/DKIM/DMARC need an owner-provided sending domain.

## Automated release (opt-in) and rollback

`.github/workflows/deploy.yml` deploys only after the `checks` workflow succeeded for the same master
commit, and only when the owner sets repository variable `DEPLOY_ENABLED=true`, variables
`DEMO_API_URL` (ending `/api/v1`) and `DEMO_WEB_URL`, and secret `RENDER_DEPLOY_HOOK_URL` (optionally
`VERCEL_DEPLOY_HOOK_URL`). It waits for readiness, then runs `scripts/smoke_deployed.py`, a read-only
check of health, security headers, exact-origin CORS and SPA routing; run it by hand the same way.
Owner action: turn off Vercel's git auto-deploy and use the hook, otherwise Vercel still deploys
ungated. This workflow has not run against the live services. To roll back, run the workflow
manually with `rollback_sha` set to the last verified commit (or redeploy the previous deployment in
each dashboard), then re-run the smoke script. Migrations are additive; never downgrade a database.
