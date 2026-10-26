# SubTrack — current-state handoff

Updated2026-10-26. This is the sole current instruction source. Earlier handoffs are historical
facts in docs/history/, including the exact preceding receipt-UI handoff. Read README,
docs/EXPANSION_PLAN.md, docs/MAILBOX_LAB.md, docs/DOD.md and the real code before editing.

## Current state: locally verified expansion foundation

Implemented and verified locally, **not a live Gmail connection or real-user launch**:
- Development-only synthetic mailbox consent and actual separate-worker fixture sync. Fixed
  allowlisted16 EMLs run through the real bounded parser; no canned extracted results.
- Scoped versioned consent, one active sync per connection, global32-job admission, SKIP LOCKED
  claims,30-second fenced leases, per-item checkpoints, three attempts/backoff and30-minute TTL.
  Automatic hourly sync runs only while the opted-in local worker is awake. Every item rechecks
  consent/generation; disconnect fences work and purges evidence, jobs, OAuth state and credentials.
- Separate receipt-evidence table, never input to financial summary/detection/savings/chat tools.
  Candidates: same-owner bank/demo debits, exact INR Decimal amount and normalized merchant,
  payment dates within three days; legacy receipt-derived transactions are excluded. No automatic
  match, even with one candidate. Explicit confirmation links evidence without changing totals.
  User edits/ignored/matched decisions survive resync. Existing legacy no-mixing guard is retained.
- Extracted evidence fields clear after30 days from creation/review; minimal digest/status/link
  tombstones remain until disconnect/deletion so discarded evidence cannot be resurrected by sync.
  Sync records purge seven days past expiry; five-minute OAuth state purges at hourly maintenance.
  Safe account export includes new data and excludes all token/verifier ciphertext and claim tokens.
- OAuth protocol/encryption foundation only: PKCE, hashed scoped single-use state, independent
  Fernet key, exchange/refresh/revocation/raw/history methods, bounded HTTP and safe errors, tested
  with injected responses AND an actual loopback HTTP server. Default live construction refuses.
  Runtime Gmail authorization is hard-disabled; MAILBOX_LIVE_ENABLED=true fails configuration.
- Separate voluntary category-interest declarations with separate consent/withdrawal. No financial
  or mailbox model queries for cohorts. Internal ops-secret-gated counts exclude stale consent and
  suppress groups below10. No offer, provider contact, partnership, discount or plan sharing exists.
- Lazy-loaded local `/mailbox` UI: explicit synthetic labelling, consent, true sync progress,
  editable evidence, match confirmation, status filters/pagination, typed disconnect/purge and
  independent interest controls. Link is absent from public-demo upload UI; default-off/disabled
  page has no live connection controls. Existing themes, plain-text rendering and money rules apply.
- Additive migration0017_mailbox_lab; no create_all, stack change, new package or destructive backfill.
  `MAILBOX_LAB_ENABLED=false` is the default and remains false on hosted demos. No key is needed
  for the lab; MAILBOX_TOKEN_KEY is generated ephemerally for local protocol tests only.

## Verification receipts (final local source)

Logs are ignored under `var/expansion-verification/`; no private statements/emails were used.
- `make dev verify`: exit0. Focused PostgreSQL/migration suite34 passed49.00s.
- `make test lint evaluate`: exit0; **554 PostgreSQL tests**,545.73s, one upstream
  Starlette/TestClient/httpx deprecation warning; **99 frontend tests**,11 files. OpenAPI/type drift,
  Ruff/ESLint/TypeScript passed. Detector P/R/F1=1.0000 on synthetic/handwritten bank/handwritten
  products; extraction gate passed and receipt exact outcomes16/16. Real-source accuracy unmeasured.
- Real-worker mailbox Chromium flow passed25.6s initially; final all-browser rerun passed18.4s
  after a checkbox-label layout correction. Checks independently labelled evidence counts,
  zero spend before bank ingestion, unchanged exact summary after match/replay/purge, separate
  interest consent/withdrawal, user deletion, runtime/console health, desktop and360px light/dark
  axe and no overflow. Screenshot outside repo was visually inspected.
- Full standard browser invocation: **18 passed6.7m**, two profile skips. Strict same-site TLS
  **1 passed11.7s**; expanded public demo **1 passed11.1s**. **20 distinct browser cases passed**;
  do not double-count the initial focused mailbox rerun. Public checks reject connect/sync/live
  authorize/interest writes, hide the link and confirm the lab capability is disabled.
- Production build passed14.57s: main354.65kB/gzip111.74, lazy mailbox11.84/gzip3.90,
  lazy chart389.93/gzip114.22. No performance SLA is claimed.
- `npm audit --audit-level=low`:0; `pip-audit -r backend/requirements.lock --disable-pip`: no known
  vulnerabilities. Gitleaks entire78-commit pre-commit history and current source: clean. Existing
  exact historical synthetic JWT exceptions and16-file EML allowlist were not broadened.
- Owner-only private receipt checker executed on a synthetic fixture: passed, terminal-only,
  no network/file output. Never interpret this as a real-provider accuracy measurement.
- All normal API/worker flags and clocks were restored; existing tracked screenshots were restored
  byte-for-byte. Windows-native test cache limitations use Docker/Linux browsers; Codex Process
  Jobs is unsupported on win32, so finite verification used foreground terminal sessions.

## Publication and hosting rule

Use an isolated codex/ branch for exact-commit green hosted CI first, then fast-forward master
without a PR/force push, and manually deploy that same commit to the existing free Render demo.
This keeps Vercel's Git auto-deploy behind an already-green commit. Latest exact-commit checks
are authoritative; read `/health.revision` and `/version.json` before claiming a live revision.
Never treat a push or an old CI run as proof of a new deployment. Do not enable lab/live flags on
hosted demos. Current actions are available from the repository's checks workflow:
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/workflows/ci.yml

Historical verified baseline: receipt UI master7c56cb1, CI40289738439 (all four jobs green), Render
dep-dbfhdtm7bikc73dipktg succeeded/live, exact revisions on Vercel/Render and23 smoke checks passed;
receipt capability false and preview403. This is historical evidence, not a new release assertion.

Frontend: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1
Default branch is **master**, not main. The owner authorized direct promotion and demo updates
once local/hosted gates pass. Do not force-push, rewrite history or tag a beta.

## Owner decisions, real limits and remaining work

Keep hosting **free**, production fail-closed, real-user beta locked. No paid resources, new
third-party accounts/terms, real users/financial data, live Gmail/Gemini calls or provider contact.
Architecture A and PostgreSQL coordination, bcrypt, strict SameSite/CSRF, Fake deployed mode,
deterministic Decimal money and educational/demo notices remain mandatory. Legal drafts are
unapproved; acceptance stays off. Existing public visitors remain isolated/disposable/synthetic;
password registration/login and all file uploads stay disabled on hosted public demo.

**Not done:** actual Gmail consent callback/orchestration, real inbox incremental sync and real
revocation delivery; OAuth protocol tests are only a foundation. Needs owner/Google approvals,
credentials, operational/legal review, completed runtime integration and private accuracy checks.
No full real-bank reconciliation, invoice identity, FX matching or mail-only financial ledger is
claimed. New evidence links existing bank charges only; legacy imports retain their known limits.
Provider agreements/licensing, offers, fulfilment/billing cannot be fabricated and are not built.
Voluntary interests do not grant redistribution rights or permission to share Gmail-derived data.

Existing launch gaps remain: two-API/worker operational drill evidence, local restore/load/ZAP and
exercised rollback; managed PostgreSQL/PITR before free DB expiry **2026-11-19** (or accept demo
loss), separate staging, sibling custom domains, deployed worker, real sender/SPF/DKIM/DMARC,
monitoring/incident contact, paid-tier Gemini/billing/spend alerts, legal review, human screen-reader
pass, private real-statement/receipt measurement and live Gemini eval. Managed backup deletion
and delivered emails cannot be guaranteed by a SQL delete. Owner confirmed credential rotation
on2026-10-22; historical pre-rotation instructions are superseded, never print secrets.

Earlier phases/demo/bank detection/alerts/chat remain intact. Their detailed history and actual
verification limits are in docs/history/, docs/ARCHITECTURE.md, docs/PRIVACY.md and docs/DOD.md.
