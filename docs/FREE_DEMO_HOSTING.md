# Free hosted demo — not a production deployment

The owner approved free Render resources on 2026-10-20. Frontend remains on Vercel. This does
not implement Phase8's private-beta security, durability, backup or operational requirements.
Use synthetic data only; the educational-use notice and offline assistant remain enabled.

## Render configuration

- Existing API: `AI-Powered-Subscription-Recurring-Payment-Manager`, Free, Oregon, one instance.
- Dockerfile: `./backend/Dockerfile`; build context: `./backend`; repository root directory empty.
- Docker command: `python scripts/start_demo_server.py`.
- Readiness path: `/api/v1/health/ready`.
- Free PostgreSQL16: `subtrack-demo-db`, Oregon; created2026-10-20, expires2026-11-19.
- External database access blocked; the API uses the private connection URL with the SQLAlchemy
  `postgresql+psycopg://` driver. Never copy the connection value into docs, issues or logs.
- Env: `ENVIRONMENT=development`, exact Vercel `WEB_ORIGIN`, generated `JWT_SECRET`, private
  `DATABASE_URL`, `LLM_PROVIDER=fake`, `APP_TIMEZONE=Asia/Kolkata`, `UPLOAD_WORKERS=1`,
  `UPLOAD_QUEUE_LIMIT=2`, `STATEMENT_CONCURRENT_LIMIT=1`.

The development-only entry point applies Alembic before starting one Uvicorn process on Render's
PORT with access logs disabled. It rejects production/test mode, missing signing secrets and invalid
ports. This boot migration is an explicit **demo-only exception** for the free plan, which lacks a
pre-deploy command. Phase8 must use a separate migration release step; do not reuse this entry point
for production or change ENVIRONMENT merely to bypass production guards.

## Vercel configuration

Root `frontend`, Vite, `npm run build`, output `dist`. The checked-in rewrite serves the SPA for
client routes and leaves `/api/` paths alone so a missing API base does not masquerade as HTML200.
Set `VITE_API_BASE_URL` to the hosted API origin plus `/api/v1`, then redeploy. Uploads go directly
to that API; no statements are proxied through Vercel Functions. No keys belong in VITE variables.

## Limits and current verification

Free API instances sleep; scheduled alerts are unreliable while asleep. PostgreSQL expires after
30 days and provides no PITR. API512MB memory is insufficient to guarantee OCR with512MB parser
limits plus the API; lower concurrency does not establish capacity. Dev outbox files are ephemeral.
Keep this a disposable demonstration; do not invite real users or upload real bank statements.

The first Render build failed because Dockerfile was sought at repo root. Corrected path/context
built successfully; runtime then correctly refused the missing signing secret. A quoted shell
override was rejected by Render's command parsing, motivating the Python entry point. Eight real
subprocess/PostgreSQL entry-point tests and focused Ruff pass locally. Hosted startup and frontend
integration remain pending until the signing secret is supplied and environment settings saved.

A database credential was accidentally exposed by the browser accessibility output even after
the field was hidden. The owner explicitly requested retaining it. External ingress is blocked;
replacement remains recommended before any non-disposable use. Never reproduce the value.
Subsequent secret-bearing UI reads must suppress raw accessibility output and report only state
or boolean checks. Browser credential-change actions remain a user handoff.
