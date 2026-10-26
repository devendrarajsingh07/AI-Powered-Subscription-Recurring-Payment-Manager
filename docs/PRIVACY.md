# Privacy and deletion

Use synthetic or locally redacted data. This is an educational/demo application, not a bank connection.

Account-security build: access tokens remain in browser memory only. Strict same-site deployments
use a host-only Secure/HttpOnly/SameSite=Strict rotating refresh cookie. The current cross-site demo
uses disposable memory-only sessions instead; no refresh cookie is issued. Hashed refresh/action
tokens, session expiry/revocation/version and account backoff digests are stored; raw action codes
appear only in the requested email/private dev outbox. Account deletion cascades authentication
rows and purges dev outbox copies; anonymous rate buckets are not identity-linked and expire later.
See PROJECT_INFO for which revision has been verified/deployed. Operational retention periods are
listed in the next section.

Public-demo-only mode disables file upload/preview and password registration/login. Visitors get
isolated generated identities and may load synthetic data only. Accounts expire within24 hours and
are purged on startup/every15 minutes while the free service is awake. Expired access is rejected
even before the physical purge; sleeping/free-service downtime can delay physical deletion.

The hosted free instance is synthetic-only; Phase 8 beta remains blocked. It additionally stores
HMAC invitation/email digests, invite expiry/use/revocation times, minimal security-event UUIDs/kinds/
timestamps, and HMAC peer-address fixed-window rate counters. Signing-key rotation invalidates the
digests. Counters expire and are removed on later limited requests; no immediate timed-purge promise
is made. Anonymous failed-login audit retention still needs a purge policy before beta.
Security events linked to an account and issued invitations cascade with account deletion; anonymous
events have no stored account/email association. There are no public invitation/audit admin endpoints.

Settings can download a scoped JSON export with transactions, subscriptions/charge links,
recommendations, alerts, budgets/preferences, upload metadata, category decisions, chat and statement
usage counters. Passwords, authentication material and ephemeral statement previews are excluded.
Downloaded exports contain private descriptions; deletion cannot remove copies from your device.

Stored in PostgreSQL: normalized login email, bcrypt password hash, upload metadata/progress and
provenance, transaction dates/descriptions/amounts/currency, derived subscriptions and charge links,
category decisions, budget, alert preferences/recipient and payload/delivery snapshots,
recommendation decisions, live-provider consent and chat messages/tool-call metadata.
Raw descriptions are retained unchanged in storage but displayed as safe text. Application logs
contain IDs/counts and safe failure categories, not financial content, credentials or mail bodies.

Default offline assistant: no external AI calls. Opted-in Gemini receives redacted question and
bounded recent chat history, system instructions/tool schemas and scoped tool results containing
subscription merchant names, categories, amounts, dates, counts and uncertainty. Raw transaction
descriptions, login/notification email, tokens, IDs and credentials are excluded. Do not type
personal material into chat: redaction is not a general PII classifier. Categorization sends only
the normalized unknown merchant and a fixed category schema/instructions, no financial records.
Consent defaults off, is checked server-side before live calls, and can be withdrawn in the drawer.
Withdrawal prevents new sends; it cannot recall data already processed by a provider.

### Google Gemini tier-dependent data use

The app cannot infer the API key's billing tier. Under Google's [current API terms](https://ai.google.dev/gemini-api/terms),
Unpaid Services may use submitted content and responses to improve Google products, and human
reviewers may process them. Do not send sensitive, confidential or personal financial data to that
tier. Paid Services exclude product-improvement use, but permit limited logging for safety and
legal obligations; paid does not mean zero retention. Read the applicable terms and
[billing documentation](https://ai.google.dev/gemini-api/docs/billing) before opting in.
Offline mode remains the default. No live evaluation, tier verification or legal review was performed.

Rechecked on 2026-10-20, terms effective March23,2026. Exact Paid Services excerpts:
“Google doesn't use your prompts” … “or responses to improve our products”. The section still
permits limited safety/legal logging and transient storage. Gemini API Paid Services status depends
on the API Cloud Project having an active billing account; the operator must verify this, not infer
it from a model name or a successful request. [Official terms](https://ai.google.dev/gemini-api/terms).
No billing was enabled, terms accepted on the owner's behalf, or live request made during this check.

The Gemini upgrade revokes existing previous-provider consent in migration0007. A previous provider's
approval is never silently reused for Google; users must opt in again after reading the new notice.

Console emails are complete HTML/plaintext MIME files in the private Docker outbox volume,
separated by user UUID. `make outbox` exports copies to ignored var/outbox; those exported copies
are under the operator's control. SMTP sends to the configured recipient, with normal mail-server
retention and delivery behavior. Application logs never substitute for a private outbox.

Settings **Delete my data**, after typing DELETE, deletes the account and all owned PostgreSQL
records, including chat, with cascades, and purges private console outbox copies. Tokens stop
working; other users are untouched. Manually exported files, backups, external provider records
and delivered SMTP email cannot be recalled by the application; operators must manage them.

**Remove demo data** preserves the account and real-origin uploads. Normal UI/API policy refuses
real/demo mixing, so use a separate empty account for demonstrations. Demo upload provenance
identifies synthetic records. Remove related detections/cache and, in the demo-only workspace,
recommendations, alerts, chat and private outbox. Defaults for budget/email are removed only if
unchanged since loading; user-edited preferences survive. Failed/in-flight jobs must finish or be
marked failed before removal. A repeated demo load reuses its original clock; reload explicitly
after removal to generate a newer dataset. No real user dates are ever shifted.

Keep personal exports outside the repo or in ignored private-statements/. Never commit keys,
.env, database dumps, browser traces or outbox emails. The optional local checker prints to your
terminal only, writes no result file and makes no network call. Terminal scrollback is still
private data; do not paste it into public issues.

## PDF and image statement import

Extraction happens on the application's server using local PDF/OCR programs. PDF passwords are
never stored, logged or sent to a third party. In the default in-process job mode, statement bytes
are not stored in PostgreSQL either. In durable job mode (`JOB_MODE=postgres`, used with the
separate worker), the file to be processed is stored **temporarily and encrypted** in the
`durable_jobs` table so that another worker can resume it after a crash: a CSV upload, an image, or
for a PDF the password-free cleaned copy produced by the isolated extractor (a password-protected
original is never queued). The ciphertext uses a key derived from the server signing secret, is
bounded in size, and is cleared (set to empty) as soon as the job finishes, fails permanently
(dead-letter) or is cancelled; the remaining metadata-only job row is purged after
`RETAIN_JOB_DAYS` (default 7). Deleting the account removes queued jobs immediately, and a worker
that is still running publishes nothing for a deleted account. A database backup taken while a job
is queued would contain that ciphertext; no backups exist for the free demo database. Nothing is
logged or sent to a third party. The public demo disables all file uploads. Upload
multipart spooling stays in memory within the enforced size limit; extraction can write decrypted
pages and normalized images only inside a private temporary directory. Files are removed after
completion, cancellation or timeout. Startup removes abandoned extraction directories after an
ungraceful process stop; this is not secure erasure or protection against a compromised host.
Passwords are passed through an in-memory pipe, never URL/query parameters; the browser clears
the password input after submission. The API returns safe failure codes without the file content.

User-scoped preview rows contain extracted descriptions, dates, decimal amounts, flags and optional
balances for at most 30 minutes. Confirmation or cancellation immediately clears the row payload;
small status/upload-pointer metadata remains until expiry for idempotent confirmation. A periodic
purge and access-time expiry delete expired previews. Per-user daily counters retain attempts,
failures, flagged-row and edited-row counts until account deletion, with no financial content.
Delete my data cascades through both preview and counter tables. Cancel/expiry does not reset quotas.

The review shows a browser-held local object URL, not a retained server file. Import persists only
the reviewed virtual-CSV transactions and existing derived records. Original extracted row text
is never submitted to an OCR/LLM provider. Later, if the user separately opts into live chat, the
existing disclosure still applies: normalized subscription names, amounts and dates returned by
read-only tools may be sent to Google Gemini; raw transaction descriptions and original files are
excluded. Offline mode sends neither. See [statement scope and private local check](STATEMENT_IMPORT.md).

## Retention, email lifecycle and problem reports

Finished operational records are purged by a scheduled job (the separate worker owns it in
PostgreSQL job mode). Periods are configuration; defaults: finished durable jobs 7 days
(`RETAIN_JOB_DAYS`), chat messages 30 (`RETAIN_CHAT_DAYS`), sent/skipped/failed alerts 180
(`RETAIN_ALERT_DAYS`), account-linked security events 90 (`RETAIN_AUDIT_DAYS`), expired sessions
after one day, expired account codes after expiry. Queued statement input is encrypted, bounded and
cleared when a job finishes. The job logs counts only. Account deletion removes everything at once.
Database backups and provider-side copies are outside this job; none is verified for this free
deployment.

Internal metrics (`/api/v1/ops/metrics`) require a private operator token, are absent from the public
OpenAPI schema, and return counts and ages only: no content, addresses, amounts or identifiers.

Email: a hard bounce or complaint reported by the operator suppresses alert emails for accounts
delivering to that address until a different address is saved. Alert emails carry a signed one-click
unsubscribe link and RFC 8058 headers. The link reveals nothing about whether it was valid.

Problem reports (category plus up to 1,000 characters) reject statements, long digit runs and
currency amounts, are limited per account per day, and are kept until the account is deleted.
Never ask reporters for financial records. When `LEGAL_ACCEPTANCE_REQUIRED` is on, the accepted draft
version and time are stored with the account. The drafts in `docs/legal/` are unreviewed and unapproved.

## Offline receipt foundation

`RECEIPT_IMPORT_ENABLED` defaults off; production activation is refused and the public demo
rejects the route before reading any message body. Local development accepts a bounded EML,
without accessing an inbox. Original bytes, MIME attachments, header addresses and message bodies
are not persisted. Extracted merchant/date/amount/type fields remain in the existing owned preview
for its configured TTL (default 30 minutes); confirmation/cancel clears them and account deletion
cascades. Confirmed charges remain ordinary account-owned transaction records with an
`email_receipt` upload origin. No message/invoice identity or bank reconciliation is implemented;
canonical duplicate counts are visible and source mixing is refused.

Receipt creation requires the offline assistant; live-provider attempts for existing receipt
workspaces are blocked before transmission. No Gmail scopes, keys or tokens are requested or
stored. Future OAuth data use/retention needs its own reviewed design and clear consent.
Only the 16 labelled synthetic messages in `backend/data/receipts/` are repository fixtures.
Private mail belongs outside version control, such as the ignored `private-emails/` directory.
Separate future provider-offer interest declarations must not reuse mailbox-derived data.

## Disabled mailbox rehearsal and voluntary declarations

The optional private development lab reads committed synthetic fixtures only, with explicit
versioned consent; it never connects a Google account. It stores normalized extracted receipt
fields separately from financial transactions. Explicit bank matching links evidence to an
existing same-owner debit without changing spend. Original email bodies/headers/addresses are
never retained or sent to AI. Receipt-only legacy uploads remain subject to their existing guard.

Extracted evidence fields expire after30 days from creation/review; minimal digest/status/link
tombstones persist until disconnect/deletion to prevent resync resurrecting discarded evidence.
Sync records expire from storage seven days after their TTL; scoped OAuth states expire in five
minutes and are purged on hourly maintenance. Independent key-encrypted token/verifier material
exists only in local protocol tests; live Gmail is unavailable. Export excludes all such material.
Disconnect purges mailbox evidence, sync records, credentials and OAuth states. It retains minimal
consent/disconnection metadata and does not alter bank transactions or separate plan interests.
Account deletion cascades all of it. Existing backup/email limitations above still apply.

Plan interests are independent voluntary category declarations, never inferred from financial or
mailbox data. They persist until withdrawal/account deletion. Operator-only cohort counts exclude
old consent versions and suppress groups below10; nothing is shared with providers and no offers
exist. Neither this threshold nor a synthetic consent grants permission for future live processing.
