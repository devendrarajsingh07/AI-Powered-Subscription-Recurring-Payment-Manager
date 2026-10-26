# Offline mailbox rehearsal and reconciliation

This is a development-only synthetic workflow, not connected Gmail. The public demo and
production cannot activate it. No Google account, key, real inbox, live Gemini or SMTP server is
used by this phase. Live Gmail authorization is explicitly unavailable; the protocol foundation
is tested with injected transports and an actual loopback HTTP server only.

## Run locally

Start the existing stack with the offline assistant (default), then in PowerShell:

```powershell
$env:MAILBOX_LAB_ENABLED = "true"
make dev
```

Register an isolated synthetic local account. Open **Upload statement → Open the offline receipt
inbox lab** (or `/mailbox`). Read the disclosure and explicitly consent to the synthetic rehearsal.
Click **Sync synthetic receipts**. The separate PostgreSQL-coordinated worker runs the real MIME
parser on the committed16 EML fixtures. The UI polls real processed/total, accepted, unsupported
and duplicate counters; unsupported messages do not become charges. Sync may repeat hourly while
the local worker is awake. Consent withdrawal stops/fences work between every committed item.

Evidence is separate from transactions. Before a bank upload, summary spend stays zero even when
receipts exist. Upload a synthetic bank CSV through the ordinary statement flow. The inbox
suggests the caller's INR bank/demo debits only when normalized merchant, exact Decimal amount
and payment date within three days agree. Legacy receipt-derived transactions are excluded.
Multiple candidates remain ambiguous. Correct receipt fields explicitly, save them, then select
one candidate and separately confirm it is the same payment. Corrections clear the existing link.
No candidate means unresolved evidence, not a guessed charge. Matching never changes any total,
transaction or detector output. Existing legacy receipt-only uploads keep their no-mixing guard.

The optional group-plan section requires **separate** voluntary consent. Its categories are chosen
by the user; no emails, evidence, subscriptions or transactions are consulted. There are no offers,
discounts or provider agreements in this app, and no provider is contacted. The operator-only
cohort endpoint suppresses groups below10 declarations and is disabled without its existing ops
secret and the private lab flag. This is not an anonymity guarantee or permission for commercial
sharing. Withdraw declarations independently; disconnecting mail does not withdraw this other
purpose's consent.

Use **Disconnect and remove evidence**, type DISCONNECT, and confirm to purge mailbox evidence,
OAuth state and sync records. Bank history is untouched. Delete-my-data cascades all new tables
as well. To return to normal mode:

```powershell
Remove-Item Env:MAILBOX_LAB_ENABLED
make dev
```

The lab needs no MAILBOX_TOKEN_KEY. That independent Fernet key is used only by developer-run
OAuth protocol tests (generated ephemerally), not by the fixture connection. Never set
MAILBOX_LIVE_ENABLED=true: startup refuses it. Approval of a synthetic disclosure does not grant
Google mailbox permissions or consent to a future live integration.

## Data boundaries and retention

- Store scoped consent/version/generation, sync metadata and extracted merchant/date/INR amount,
  flags and an optional caller-owned bank-transaction link. Hash message identity for idempotency.
  Never retain raw EML bytes, original headers/body, attachments, mailbox addresses or remote HTML.
- Every sync claim uses PostgreSQL SKIP LOCKED, a30-second fenced lease, cursor checkpoint per item,
  three attempts, retry backoff,30-minute TTL and bounded admission (one active sync per connection,
  at most32 active jobs). Terminal failure and safe failure codes remain visible through polling.
  There is no second queue service or new hosted infrastructure. Upload jobs take worker priority.
- Replays do not overwrite ignored, edited or matched evidence. Clear extracted fields after30
  days from creation/review; retain only digest/status/link tombstones until disconnect/deletion
  so full resync cannot resurrect expired or ignored evidence. Sync records are purged seven days
  after expiry. OAuth states expire after five minutes and are removed at hourly maintenance.
- Export includes safe mailbox consent, sync/evidence and declared interests, never token/verifier
  ciphertext, OAuth state or claim tokens. SQL deletion does not promise immediate erasure from
  backups; backup/PITR retention remains an operator/launch task. Voluntary interests persist until
  withdrawal/account deletion; only current-consent declarations enter internal cohort counts.
- The live-provider guard refuses existing receipt/mailbox workspaces, including transport retries.
  Existing read-only chat tools are unchanged and do not query evidence or interest declarations.

## OAuth protocol foundation, not a live connection

Internal test seams build a read-only Gmail authorization request with random scoped state and
PKCE-S256; store only a state digest and independently encrypted verifier; atomically consume
once with five-minute expiry and wrong-user rejection. Exchange/refresh/revocation/raw-message
and history methods use fixed Google hosts, no redirects or ambient proxies, time/size caps,
strict token scope/lifetime validation and safe errors. Encrypted refresh storage preserves an
existing refresh token if a refresh response omits it. Key rotation requires reconnecting.
No runtime route can complete a Gmail connection; the default protocol constructor refuses live
networking. Expired history produces an explicit resync-required error, not a guessed cursor.

Remaining live work/gates: approved Gmail consent/callback/orchestration wiring, Google restricted-
scope verification/security requirements, operational/legal approval, real provider credentials,
private receipt accuracy evaluation, revocation delivery/retries against the real provider and
real inbox incremental-sync evaluation. Do not label this stand-in-tested foundation launch-ready.
Provider agreements, licensing, offer fulfilment and billing require separate owner-led work.

## Private accuracy check (owner-run, never uploaded)

Redact addresses, account/reference numbers and personal content locally first. Keep copies in
an ignored private directory or outside this repository; never commit them or paste the output
into a public issue. The optional checker writes nothing and contacts no network; it prints only
extracted candidate fields and safe rejection codes. Compare each field against your redacted
source manually and report misses separately. No real-provider accuracy has been measured here.

The fixture-only command used to verify the checker is:

```sh
docker compose exec -T api python scripts/check_private_receipts.py data/receipts/netflix-1.eml
```

For private files use the same script in a local Python environment with the locked backend
requirements, passing local `.eml` paths. This owner step was not run on personal files.

## Verification (2026-10-26)

`make dev verify`, `make test lint evaluate`, production build, contract/type drift and audits all
passed. **554 PostgreSQL tests** (545.73s; one upstream deprecation warning), **99 frontend tests**
(11 files); focused PostgreSQL/migration34 passed49.00s. Detector P/R/F1=1.0000 on its existing
synthetic/handwritten gates; receipt fixture outcomes16/16. These are not real-provider metrics.

Real-worker browser rehearsal passed25.6s initially and18.4s in the final regression after a
checkbox-label layout correction. Standard browsers18 passed6.7m, separate TLS1 passed11.7s and
expanded public demo1 passed11.1s:20 distinct cases. Public writes/connect/sync/authorize/interests
are disabled. Screenshots outside the repo were visually reviewed. All prior screenshots and the
normal API/worker clock/flags were restored afterward. No manual screen-reader pass is claimed.

Production build14.57s: main354.65kB/gzip111.74; lazy lab11.84/gzip3.90. npm audit0; pip-audit no
known vulnerabilities; Gitleaks entire78-commit pre-commit history and current tree clean. The
private checker ran on one synthetic fixture, never a personal file. Exact-commit branch CI and
master/deployment revisions must be checked independently; latest hosted checks are authoritative.
