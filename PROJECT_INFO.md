# SubTrack — current-state handoff

Updated 2026-10-25. This section is the sole source of current instructions. Historical
records preserve prior facts, failures and superseded directions; do not execute their old steps.

## Current work

The October 25 review found six issues: unstable current-price totals, consent not checked on
provider retries, pypdf advisories, stale renewal-alert dates, missing static-host CSP, and a
stale handoff. Fixes and regression tests are verified locally on `codex/review-fixes`, based on
remote master `91007a4`. The owner requested a direct push to the default branch, **master**
(the repository has no main branch). Do not force-push or rewrite history. The older local
master history is preserved; the remote's history had already changed before this work.

Design decisions were recorded before implementation in `docs/REVIEW_FIXES_2026_10_25.md`.
Migration 0016 adds/backfills a nullable Decimal billing projection independently of transient
price-increase notices. Historical averages and user decisions remain unchanged. API changes
are additive. Consent, account existence, kill switch and quota are checked before provider
attempts, including retries. Renewal alerts use the shared explicit-clock projection.

Local full gates pass: 486 PostgreSQL tests (425.83s, one upstream deprecation warning),
75 frontend tests, OpenAPI/type drift, lint/typecheck/build, detector and extraction evaluators.
Detector P/R/F1 is 1.0000 on synthetic and both handwritten groups. Python/npm audits are clean
with pypdf 6.21.2; Gitleaks scanned all 72 reachable commits plus current source, no leaks.
Production-CSP mobile Chromium probe passed registration/demo ingestion/charts/renewals/deletion
without page errors or CSP violations. Browser suite: 16 passed (Chromium 10, Firefox 3, WebKit 3), plus strict sibling-host TLS 1
and isolated public-demo 1 passed. Hosted CI must certify the direct-push commit after publication.
Exact commands and results are in docs/DOD.md; baseline was 477 backend and 73 frontend tests.

## Owner decisions and release gates

Keep hosting free and the real-user beta locked. No paid resources, new third-party accounts or
terms acceptance, live Gemini calls, real financial data/users, beta tags or history rewriting.
Architecture A, PostgreSQL coordination, bcrypt, strict SameSite/CSRF, and fail-closed production
remain mandatory. Hosted mode is fake/offline, isolated disposable visitors, synthetic data only,
no password registration/login or file uploads, with the persistent public-demo warning.

Push only after local gates pass. Existing demo deployment requires green hosted CI for the exact
commit. `deploy-demo` is opt-in and was skipped on base 91007a4. Hosted base checks run 39989916999
passed all four jobs; this does not certify subsequent fixes or an automated release.

## Runtime, deployments and limits

React/Vite/TypeScript/Tailwind/Recharts/TanStack Query/Router; FastAPI/SQLAlchemy/Alembic/PostgreSQL16.
Money is Decimal and decimal-string JSON; no LLM arithmetic. Gemini is the only live adapter,
tested against local HTTP stand-ins only. Fake remains the default and hosted mode.

Frontend: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1
Observed in the read-only October 25 review: frontend revision 91007a4, API revision f1b901e;
public_demo_only=true, session_mode=demo, legal acceptance disabled. No claim that newer fixes
are deployed until revision/header/readiness checks establish it.

Render's free database expires **2026-11-19**, without PITR. Owner-confirmed database credential
rotation completed 2026-10-22; see `docs/SECURITY_INCIDENT.md`. Do not reproduce secrets.
Remote master now includes the chosen MIT LICENSE, copyright 2026 DEVENDRA RAJ SINGH.

Local-only demo credential: subtrack-demo@example.org / SubTrackDemo2026!. Never enable this shared
account on a hosted instance. Disposable hosted accounts expire after 24 hours; sleeping free
instances delay physical purge, while expired sessions are rejected and startup catches up.

## Remaining verification and launch blockers

- Record actual two-API/worker crash and shared-limit Compose evidence, restore, load and ZAP drills.
- Verify release/rollback against the configured providers; current release-script tests use stand-ins.
- Add managed PostgreSQL/PITR before expiry (or accept demo-data loss), separate staging, sibling
  custom domains, transactional sender/SPF/DKIM/DMARC, monitoring and an incident contact.
- Paid-tier Gemini billing/spend controls and a private live eval are owner tasks; no live call
  is authorized here. Per-user opt-in and disclosure remain required before live use.
- Legal drafts remain unapproved; acceptance is off. Lawyer review, a human screen-reader pass,
  private real-statement accuracy checks and repository visibility are owner decisions.
- Detector metrics cover synthetic and handwritten fixtures only. OCR is imperfect and requires
  review. Renewal projections are estimates. SMTP has send/commit ambiguity. Chat verification
  proves figure provenance, not prose or associations. Production startup remains blocked.

## Preserved history

- docs/history/HANDOFF_BEFORE_REVIEW_FIXES_2026_10_25.md
- docs/history/DOD_BEFORE_REVIEW_FIXES_2026_10_25.md
- docs/history/PHASE8_WP3.md and PHASE8_BEFORE_CONTINUATION.md
- docs/history/PHASES_1_5.md, PHASE_6.md, PHASE_7.md

Priority: correct numbers > data safety > working demo > polish > extra features.

## October 25 fix commits

- 5338f0c: billing projection/backfill, shared renewal scheduling, provider retry consent/account checks,
  generated contract, regression tests and the release-test script mount.
- 644681f: pypdf 6.21.2 hash-locked patch and static Vercel CSP with config/smoke checks.
- Documentation commit: current handoff/DOD/README/architecture, prior records archived unchanged.

Local receipts: `make verify test lint evaluate` passed, followed by `make test lint evaluate`
after the FX edge-case refinement. Linux Playwright ran 16 standard plus both special profiles
against real Compose, preserving the strict configured origin and restoring the clock/mode.
The production-CSP probe used the built artifact and Vercel header config, not Vite headers.
Dependency audits and complete history/current-source scans passed. No live-provider call was made.
Exact-commit hosted CI status is reported through the master checks workflow; the preceding base
run is historical evidence only. Demo deployment remains gated on successful exact-commit CI.
