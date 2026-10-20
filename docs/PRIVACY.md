# Privacy and deletion

Use synthetic or locally redacted data. This is an educational/demo application, not a bank connection.

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

Extraction happens on the application's server using local PDF/OCR programs. Original statement
bytes and PDF passwords are not stored in PostgreSQL, logged or sent to a third party. Upload
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
