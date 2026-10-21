# Credential exposure — owner action pending

Updated 2026-10-21. Do not reproduce the credential or rewrite Git history.

## Location and evidence

The preserved deployment record (`docs/FREE_DEMO_HOSTING.md`) identifies the disclosure as a
Render database credential appearing in a **browser accessibility-tool response in this chat**
while inspecting the database connection/credential interface, even after hiding the field.
It was not an intended application log. The original tool-call identifier and exact UI field
are not available in the retained context, so those details cannot honestly be reconstructed.
There is no evidence identifying a commit, CI log, screenshot or tracked handoff containing the
credential value. The handoff records the incident, never the value. Scanning cannot prove that
unavailable external logs or earlier chat attachments contain no copies.

2026-10-21 checks: Gitleaks8.30.1 scanned **44 commits / 2.26 MB**, exit0, no unreviewed
findings. Three previously reviewed exact historical synthetic JWT exceptions remain in
`.gitleaksignore`. Full directory scan found10 matches:2 in ignored local `.env`,6 in installed
SQLAlchemy code,2 in the downloaded Gitleaks README. Values were not printed. Source-only scan
(tracked plus non-ignored untracked files) scanned1.78 MB, exit0, no findings. No `.env`, `.eml`
or outbox files are tracked. Committed statement fixtures/screenshots are synthetic. No history
rewrite or credential rotation was performed. CI now scans full history and current source.

## Network verification

2026-10-21 Render database Info → Networking: **“All internet traffic is blocked by PostgreSQL
inbound IP rules”**; External Database URL reports external traffic not allowed. Higher-level
workspace/environment rule labels do not override that database restriction. The deployed API
uses Render's private connection. This is a dashboard configuration check, not a penetration test
or proof of account-level least privilege. Keep external ingress blocked during rotation.

## Owner rotation procedure

1. Open `subtrack-demo-db` → **Info** → **Credentials** → **+ New default credential** →
   **Create Credential**. Complete these steps yourself; do not paste the value into chat.
2. In the existing Render API service → **Environment**, replace **DATABASE_URL** with the new
   **Internal Database URL**, using the `postgresql+psycopg://` driver prefix. Preserve the rest
   of the URL exactly; do not use the external URL. Save and redeploy.
3. Update every other database consumer if present (worker, migration job, staging, operator
   environment). Currently only the free demo API is deployed; Vercel must never receive DB
   credentials. Blueprint references require a sync if used in future.
4. Check `/api/v1/health/ready` returns200, migration head matches, and a synthetic isolated demo
   session can load data. Confirm new connections work and the old role has no active connections.
5. Return to Credentials and delete/deactivate the **old** credential. Render cannot delete the
   current default; its original role is deactivated rather than physically removed.
6. Recheck readiness and the demo after restarting the API. Confirm completion to change this
   incident from **owner action pending**. Neither external ingress restrictions nor a clean
   repository scan replaces rotation.

Official procedure: https://render.com/docs/postgresql-credentials (checked2026-10-21).

## Foundation CI evidence

Successor fixture-fix run **39401421431**, source
`19f0098bf896adf25c21cee4c2e252ca53852c21`: GitHub API checked2026-10-21,
status completed, conclusion success. Repository public, default branch master.
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39401421431

## Public-demo exposure before remediation

2026-10-21 hosted login probe for the publicly documented local-only credential returned401 (not
accepted). This does not establish whether the account row exists. Earlier hosted synthetic smoke
checks on2026-10-20 successfully registered users and uploaded CSV, proving those paths were open
on that revision; PDF/image extraction routes are also exposed by that API contract. No real user
file was uploaded during this audit. The current patch disables password registration/login and
all CSV/PDF/image upload/preview HTTP paths before body parsing in public-demo mode, replaces entry
with isolated disposable synthetic visitors, and removes the reserved shared account on startup/
scheduled purge if present. Deployment and a fresh hosted control probe must still verify this fix.
