# SubTrack — current-state handoff

Updated 2026-10-26. This is the sole source of current instructions. Prior handoffs preserve
historical facts, not new instructions; the exact preceding handoff is archived at
`docs/history/HANDOFF_BEFORE_EMAIL_RECEIPTS_2026_10_26.md`.

## Current work: offline email receipt-import foundation

The owner selected **email receipt-import foundation with synthetic fixtures**. Implementation
is on `codex/email-receipt-foundation`, based on master 1eda459. Gmail is not connected; there is
no OAuth callback, mailbox sync, email-import UI, provider offer or partner contact. Do not claim
that this development foundation grants Gmail access or processes real inboxes.

Decisions were recorded before implementation in `docs/EMAIL_RECEIPT_FOUNDATION.md`.

- New JWT-scoped `POST /api/v1/receipts/preview`: one bounded EML, explicit-label English INR paid
  receipts, locally parsed with the Python standard library. Attachments/remote resources/active
  HTML are ignored. Missing/ambiguous fields remain missing. Headers never supply a payment date.
- Every row requires explicit verified review through existing `POST /uploads`; source_type is
  `email_receipt`. Existing scoped preview read/cancel/expiry, encrypted durable CSV dispatch,
  deterministic detection, Decimal summaries and recommendation generation are reused.
- Original EML bytes/headers/addresses/bodies are never persisted or sent to a provider. Only
  extracted fields enter the expiring preview. Confirm/cancel clears payloads; deletion cascades.
- Receipt and bank/demo histories cannot mix in either direction under the ingestion lock.
  Canonical merchant/date/amount dedupe handles repeat charges; distinct identical charges may
  merge. Invoice/message identity and bank reconciliation remain unimplemented.
- `RECEIPT_IMPORT_ENABLED=false` by default; enabled creation requires development/offline mode.
  Production activation fails. Public-demo requests are rejected before reading a body, even
  with the flag enabled. The live-provider guard also blocks existing receipt workspaces.
- No database migration is needed: existing source columns are strings. OpenAPI and generated
  TypeScript add the source label and guarded route. No dependencies or stack were changed.
- Only the 16 independently labelled synthetic EML fixture filenames may be versioned. Outbox
  and private emails stay ignored; the source scanner enforces the narrow manifest exception.

Verification: `make test lint evaluate` passed with 521 PostgreSQL tests (610.74s, one upstream
TestClient deprecation warning), 75 frontend tests, OpenAPI/type drift, lint/typecheck and all
three evaluators. Detector P/R/F1 remains 1.0000 on synthetic and both handwritten groups.
The receipt evaluator matched 16/16 labelled outcomes; real-provider accuracy is unmeasured.
The 35 receipt tests were additionally rerun after linear blank-line parsing hardening (22.13s).
Real Compose `make dev receipt-demo` passed 8 imports, 3 products, independently computed totals,
duplicate replay and deletion. Production build passed; Python/npm audits clean; Gitleaks full
74-commit local history and current source clean. Standard browsers 16 passed (6.1m), strict TLS
1 passed (16.4s), expanded isolated public-demo profile 1 passed (13.6s), including EML refusal.
Original screenshots were restored from verified backups. Publication/deployment must follow
exact-commit hosted CI; the baseline CI below does not certify new changes.

## How to try it locally

PowerShell: `$env:RECEIPT_IMPORT_ENABLED="true"`, `make dev`, then `make receipt-demo`.
The CLI creates/deletes its own local synthetic account and uses the real API/separate worker.
Remove the environment override and run `make dev` afterward to restore disabled mode.
`make evaluate-receipts` runs the offline fixture gate without enabling any mailbox connection.
Manual preview/review API steps, data boundaries and limitations are in the foundation document.

The existing dashboard, statement UI, alerts and grounded chat are unchanged. Gmail scopes,
verification/security assessment, encrypted token lifecycle, per-user mailbox consent and its UI
need a separate future phase. Commercial interest lists must collect independent voluntary
choices; Gmail-derived data must not feed provider negotiations or advertising in this design.

## Owner decisions and deployment gates

Keep hosting **free** and the real-user beta **locked**. No paid resources, new third-party
accounts/terms, live Gemini/Gmail calls, real financial data/users, beta tags or history rewrite.
Architecture A, PostgreSQL coordination, bcrypt, strict SameSite/CSRF, fail-closed production and
deterministic money remain mandatory. Hosted mode stays fake/offline, disposable isolated
visitors and synthetic data only; registration/login and all file uploads remain disabled.

The owner previously requested direct pushes to the default branch **master** (no main branch)
and updates to the existing Vercel/Render demos after local gates and exact-commit hosted CI.
Do not force-push. Latest exact-commit results are authoritative in the
[master checks workflow](https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/workflows/ci.yml?query=branch%3Amaster).
The receipt foundation stays disabled on hosted demos; no new infrastructure is authorized.

## Baseline evidence and deployment context

Before this feature, master 1eda459 passed all four CI jobs in run 40216300877. Review fixes are
5338f0c (billing/renewals/retry consent), 644681f (pypdf 6.21.2/CSP), 007e76d and 1eda459 (docs).
The October 25 deployed application verification at 007e76d passed 23/23 smoke checks; Render
 dep-dbf3ks29lscs738mgjjg succeeded/live. This is historical evidence, not certification of a new
commit. Read revisions/readiness before claiming a new deployment.

Frontend: https://ai-powered-subscription-recurring-p.vercel.app
API: https://ai-powered-subscription-recurring.onrender.com/api/v1

Vercel's existing Git auto-deployment precedes CI; enforced provider gating is an open operational
gap. Render updates have been manual after exact-commit green CI; the opt-in release workflow
and rollback are not proven by a manual release. Free hosting has no separately deployed worker;
Compose's durable worker/extractor guarantees must not be claimed for the inline hosted demo.

## Remaining launch blockers and limits

- Two-API/worker Compose crash/shared-limit evidence, restore, load, ZAP and exercised rollback.
- Managed PostgreSQL/PITR before the free database expires **2026-11-19**, or accept demo-data loss;
  separate staging, sibling custom domains, real sender/SPF/DKIM/DMARC, monitoring/incident contact.
- Paid-tier Gemini project/billing/spend alerts and private live evaluation remain owner tasks.
- Legal drafts are unapproved; acceptance stays off. Lawyer review, human screen-reader pass,
  private real-statement/receipt accuracy checks and repository visibility remain owner decisions.
- Source detector metrics cover synthetic/handwritten data; receipt metrics cover explicit-label
  synthetic messages only. OCR is imperfect, renewals are estimates, SMTP has send/commit
  ambiguity, and chat verification proves figure provenance rather than prose associations.
- Database credential rotation was owner-confirmed complete 2026-10-22. MIT LICENSE is present,
  copyright 2026 DEVENDRA RAJ SINGH. Do not repeat old pending instructions or reproduce secrets.

Priority: correct numbers > data safety > working demo > polish > extra features.
