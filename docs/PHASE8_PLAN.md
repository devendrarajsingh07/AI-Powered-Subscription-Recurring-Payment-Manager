# Phase 8 implementation plan and deployment gate

Decision recorded before implementation, 2026-10-20. The owner explicitly selected:
**keep hosting free; implement and test; the real-user beta stays blocked**.
Changes may be deployed to the existing Vercel frontend and Render demo API after verification.
Do not purchase services, invite real users, enable live financial-data processing, or tag a beta.

## Architecture and decisions

- Keep architecture A: static Vite on Vercel; container API and separate worker with PostgreSQL.
  Direct API uploads remain mandatory. No Vercel Functions backend migration.
- PostgreSQL shared coordination avoids adding Redis. Durable jobs must use bounded payloads,
  leases, SKIP LOCKED claiming, retry limits and crash tests before replacing existing workers.
- Keep bcrypt, adding an offline common-password denylist. Invite codes and account-action tokens
  must be random, expiring, hashed and single-use, with atomic consumption.
- Rotating refresh cookies require sibling web/API custom subdomains. The current vercel.app and
  onrender.com names are cross-site; do not weaken SameSite/CSRF to make this demo appear compliant.
- Production must fail closed until invite-only registration, verified accounts, durable state,
  real email and revocable sessions are implemented. Development remains a labelled synthetic demo.
- No application encryption has been implemented for raw descriptions. This remains a launch risk;
  managed DB encryption/TLS and least-privilege release/app roles also require verification.
- Optional TOTP remains deferred and must be listed as a launch risk, not implied by password auth.
- No new email provider is selected without an operator account/domain. Existing SMTP transport is
  the integration boundary; verification/reset delivery and bounce handling need real tests.
- Paid-tier Gemini, billing alerts and domain/DNS are human prerequisites. Fake stays the deployed
  mode. No live requests, credentials or terms acceptance on the owner's behalf.
- Keep educational/demo notices until the beta gate passes. Legal drafts are unapproved; do not
  require acceptance of unfinished drafts or claim compliance.

## Work packages and evidence needed

1. Baseline gates and hosted CI; inspect actual code and contract.
2. Invite/closed registration, atomic invites, password denylist, security audit events and export.
3. Verified email/reset, refresh-family rotation, revocation/CSRF and memory-only frontend access.
4. Shared rate/chat limits, durable upload jobs and isolated extraction containers; two-instance,
   worker-kill, recovery and deletion tests. Do not persist original uploads indefinitely.
5. Dedicated scheduler/retries, retention and content-free operational/product metrics.
6. Gemini kill switch, shared global quotas, visible fallback, provider metrics and consent.
7. Email suppression/unsubscribe, legal drafts, report path, runbook and launch readiness table.
8. CI-controlled staging/production deployment, headers/CORS tests, restore/rollback/load/security
   drills. Verify browser behavior and APIs before declaring deployment complete.

## External blockers (not implementation completion)

- Free Render database has no PITR and expires 2026-11-19. A managed database with backups and a
  managed restore drill, separate staging DB/project and a separate worker are not provisioned.
- Sibling custom domains, DNS, transactional sender and tested inbox delivery are absent.
- No paid-tier Gemini key, billing/spend alerts, incident contact or legal sign-off.
- Owner confirmed rotation of the previously exposed DB credential on 2026-10-22; the original
  incident/rotation requirement is historical. Never reproduce credentials in evidence.
- Human screen-reader, private real-statement accuracy checks and live Gemini eval remain undone.

Current provider facts checked against official docs on 2026-10-20:
[Render free resources](https://render.com/docs/free),
[Render backups](https://render.com/docs/postgresql-backups),
[Vercel header configuration](https://vercel.com/docs/project-configuration/vercel-json).
Free-host testing cannot establish real-user launch readiness.

## Historical foundation verification checkpoint (superseded by current handoff)

Implemented work-package2 invitation/export/audit foundations and shared auth counters, plus basic
hosting headers. All remaining code work is listed explicitly in PROJECT_INFO and DOD; external
prerequisites do not imply that unimplemented code is complete. The owner has not approved a paid
upgrade or real-user launch. The earlier development registration allowance is superseded:
hosted public demo mode must disable password registration/login and file uploads, using isolated
disposable synthetic sessions. The actual beta must use invite mode after all launch gates pass.

make dev/verify/test/lint/evaluate pass;357 PostgreSQL tests and57 frontend tests. Production build,
npm/pip audits and existing OpenAPI/TS/evaluator gates pass. A real CLI create/revoke smoke test and
all-browser/deployment evidence are recorded with the final verification. New security tables use
additive migrations0009/0010; no runtime create_all or backwards-incompatible business change.

## Local operations update (2026-10-26)

The local two-API/worker, synthetic restore, bounded load, ZAP baseline and same-schema rollback
drills now have measured evidence in [LOCAL_DRILLS](LOCAL_DRILLS.md). Production/managed/hosted
guarantees above remain blocked. PROJECT_INFO.md is the sole current instruction source.
