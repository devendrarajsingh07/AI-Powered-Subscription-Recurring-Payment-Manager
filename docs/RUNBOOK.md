# Operator runbook — demo deployment, beta preparation

The current Render/Vercel deployment is free and synthetic-only. Phase 8 is not launch-ready.
Incident contact: **OWNER TO SUPPLY**. Grievance/support contact: **OWNER TO SUPPLY**.

## Deploy and verify

Run the documented Make gates; push a logical commit and inspect both GitHub jobs. Current hosted
services auto-deploy pushes to master, so they do **not** yet enforce a green-CI deployment gate.
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
terms/billing, consent and Phase 8 controls are verified. The existing access JWTs cannot currently
be individually revoked: deletion invalidates the account; signing-key rotation invalidates every
token and forces every user to sign in again. Per-session revocation is still to be implemented.

## Credentials, backups and deletion

Credential changes must be performed by the owner in the platform secret manager, never committed.
Use separate migration/app roles and per-environment keys before beta. The retained previously
exposed demo DB credential must be replaced before any real data. Keep external DB ingress blocked.

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
