# SubTrack — current-state handoff

Updated2026-10-21. This section is the only source of current instructions. Historical phase
records preserve facts, failures and superseded instructions; do not execute their old stop/start rules.

Owner decision: keep free hosting; implement and test WP3–8; beta remains locked. No paid services,
third-party account creation/terms acceptance, live Gemini, real invitations/data, beta tags or history rewrite.
Architecture A, PostgreSQL coordination, bcrypt, strict SameSite/CSRF and fail-closed production remain.

## Current work

WP3 account/session work and Step0 public-demo hardening are committed and deployed at f857f1f.
Final local gates:408 PostgreSQL/67 frontend tests;16 standard browser flows,1 TLS and1 public-demo
profile; expanded recovery/mobile/theme axe audit. Hosted branch run39623411405 passed all4 jobs.
Master successor39624799629 completed/success on the same SHA; all4 jobs green.
Render dep-dbcdh3jl550s738devf0 and Vercel21kzXbFuhxHkkZcNatA73hCDSxLn are live at that SHA.
Hosted synthetic probes passed: registration/login403, six file paths403,16 independently expected
products/totals at2026-10-21, loader idempotency, two-visitor isolation/guessed-id404 and cleanup.
Startup purge shared_before=0/removed=0 establishes no reserved shared account at deployment.
WP4 implementation begins on codex/phase8-durable-workers; WP4–8 are NOT complete.

Read docs/PHASE8_PLAN.md, docs/PHASE8_ACCOUNT_SECURITY.md, docs/SECURITY_INCIDENT.md and docs/DOD.md.
The continuation requires full local gates and hosted CI after every package before demo deployment.
Production startup remains unconditionally blocked pending operational/implementation gates.

Step0: full-history Gitleaks44 commits clean with3 exact historical synthetic exceptions; current-source
scan clean. Broad directory scan10 matches in ignored .env/vendor files (no values printed).
Render dashboard PostgreSQL rules block all external ingress. DB rotation: OWNER ACTION PENDING.
No secret found in current tracked source requiring removal. CI full-history/current-source secret scans passed on f857f1f (49 commits).

Public-demo safeguards built and verified locally: disposable generated visitor identity, no password login or registration,
no file uploads, only synthetic loader,24h expiry and15min/startup purge, persistent warning. Hosted API and browser controls were verified2026-10-21. Free sleeping delays physical purge;
expired identities are rejected immediately and startup catches up.

## Runtime and limits

React/Vite/TypeScript/Tailwind/Recharts/TanStack Query/Router; FastAPI/SQLAlchemy/Alembic/PostgreSQL16.
Decimal money and decimal-string APIs. Gemini is sole live adapter; deployed mode fake/offline.
Frontend https://ai-powered-subscription-recurring-p.vercel.app; API
https://ai-powered-subscription-recurring.onrender.com/api/v1. Render free DB expires2026-11-19, no PITR.
Local web localhost5173/API localhost8000. Local-development-only demo login:
subtrack-demo@example.org / SubTrackDemo2026!. Never use this shared account on any hosted instance.

WP3 implements verification/reset tokens, bcrypt denylist, PostgreSQL account backoff,
revocable JWT sessions, rotating refresh families/CSRF, cookie logout after access expiry,
memory-only frontend access, recovery/verification forms and logout-everywhere. Strict cookie behavior
passed the actual sibling-host TLS browser test; real sender/domain/inbox checks are owner-blocked.
certifi was updated to2026.10.19 after PYSEC-2026-4320; npm/pip audits now report no known findings.
All three detector fixture sets remain P/R/F1=1.0000; real-bank accuracy is unmeasured. WP4–8 remain pending
unless later evidence below explicitly records them. Legal drafts unapproved; no acceptance required.

Owner launch actions: credential rotation; managed PostgreSQL/PITR before expiry (or accept demo data loss);
separate staging; sibling custom domains; transactional sender/SPF/DKIM/DMARC; paid-tier Gemini billing/
spend alerts; lawyer review; incident contact; screen-reader pass; private real-statement checks; live eval;
MIT copyright-holder choice and LICENSE application; decide whether repository stays public.

## Preserved history

- docs/history/PHASE8_BEFORE_CONTINUATION.md (prior full handoff, superseded instructions)
- docs/history/PHASE8_WP3.md (continuation verification and deployment receipts)
- docs/history/PHASES_1_5.md
- docs/history/PHASE_6.md
- docs/history/PHASE_7.md

Priority: correct numbers > data safety > working demo > polish > extra features.
