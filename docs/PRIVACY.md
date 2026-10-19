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
The Gemini upgrade revokes existing Claude-era consent in migration0007. A previous provider's
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
