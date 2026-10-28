> Current instructions: [PROJECT_INFO](../PROJECT_INFO.md) and [release gate](RELEASE_GATE.md).
> Free synthetic-only disposable sessions; password registration/login and file uploads disabled.
> Owner confirmed DB rotation on2026-10-22. Earlier dated deployments below are historical receipts.

# Free hosted demo — not a production deployment

The owner approved free Render resources on 2026-10-20. Frontend remains on Vercel. This does
not implement Phase8's private-beta security, durability, backup or operational requirements.
Use synthetic data only; the educational-use notice and offline assistant remain enabled.

## Render configuration

- Existing API: `AI-Powered-Subscription-Recurring-Payment-Manager`, Free, Oregon, one instance.
- Dockerfile: `./backend/Dockerfile`; build context: `./backend`; repository root directory empty.
- Docker command: `python scripts/start_demo_server.py`.
- Native auto-deploy: **After CI Checks Pass**, saved October28 after local verification.
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

Root `frontend`, Vite, output `dist`. The checked-in build command runs
`node scripts/deploy-gate.mjs && npm run build`; it waits for exact-commit CI and API readiness. The checked-in rewrite serves the SPA for
client routes and leaves `/api/` paths alone so a missing API base does not masquerade as HTML200.
Set `VITE_API_BASE_URL` to the hosted API origin plus `/api/v1`, then redeploy. Local/private upload mode uses the API directly; the hosted public demo rejects all file uploads
and accepts only its synthetic loader. No statements are proxied through Vercel Functions. No keys belong in VITE variables.

## Limits and current verification

Free API instances sleep; scheduled alerts are unreliable while asleep. PostgreSQL expires after
30 days and provides no PITR. API512MB memory is insufficient to guarantee OCR with512MB parser
limits plus the API; lower concurrency does not establish capacity. Dev outbox files are ephemeral.
Keep this a disposable demonstration; do not invite real users or upload real bank statements.

The first Render build failed because Dockerfile was sought at repo root. Corrected path/context
built successfully; runtime then correctly refused the missing signing secret. A quoted shell
override was rejected by Render's command parsing, motivating the Python entry point. Eight real
subprocess/PostgreSQL entry-point tests and focused Ruff pass locally. Hosted startup and frontend
integration subsequently passed on 2026-10-20 after the signing secret was generated and settings
saved. Backend readiness returns HTTP200. Source commit43d246e passed hosted CI:
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39389982834

Live frontend: https://ai-powered-subscription-recurring-p.vercel.app
Live API: https://ai-powered-subscription-recurring.onrender.com/api/v1

Vercel Production has the public `VITE_API_BASE_URL` set to that API URL. Deployment
6PvaC2kJE9qQH1rJEvmoMWSeM6zB rebuilt successfully with the setting; direct `/login` routing works.
Remote disposable-account API smoke checks passed: registration/login,399 inserted rows,16 products
matched independently against ground truth, Decimal summary expectations, exact-origin CORS,
repeat upload with zero inserts, duplicate-music recommendation, verified offline chat and account
cleanup. The deployed browser also registered successfully and loaded the current-clock demo:
399 rows,16 products,12 subscriptions and4 fixed bills; monthly equivalent26312.85, yearly315754.24,
subscription monthly4015.80, fixed-bill monthly22297.05 and potential savings343.00 (INR).
These are synthetic-demo observations, not capacity, real-bank or production certification.

Historical incident: a database credential appeared in browser accessibility output even after
the field was hidden. No value is repeated here. The owner confirmed rotation on2026-10-22;
external ingress remains blocked. Exact incident evidence and rotation procedure are in
[SECURITY_INCIDENT](SECURITY_INCIDENT.md). Never reproduce connection values or read raw
secret-bearing accessibility output. Future credential entry/changes remain owner actions.

## Public-demo hardening build

The new account-security build disables hosted password registration/login and every CSV/PDF/image
upload/preview path. Visitors start isolated disposable sessions and load synthetic data only.
No refresh cookie crosses the Vercel/Render sites; tokens are memory-only and reload loses the session.
The persistent banner warns against real statements/personal data. Accounts expire within24 hours;
startup/15-minute purge removes expired visitors and the reserved shared development account.
Free-service sleeping can delay physical purge; expired access is still rejected immediately.
Console outbox remains ephemeral and no real-user beta/email/backup reliability is promised.
These controls have local browser/API evidence; see PROJECT_INFO for actual deployment verification.
