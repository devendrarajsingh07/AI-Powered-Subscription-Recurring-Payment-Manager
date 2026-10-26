# Privacy policy draft

**DRAFT — requires review by a qualified lawyer. Not an approved policy or a compliance claim.**
Draft version: 2026-10-20. Operator/contact/grievance channel: **OWNER TO SUPPLY**.

The currently deployed service is a synthetic-data demo. A private beta with real financial data
is not authorized to launch. See [actual current storage and processing](../PRIVACY.md).

Account email and bcrypt password hashes, transaction and derived subscription data, preferences,
alert snapshots, consent and chat history are stored in PostgreSQL. Extraction previews expire
after 30 minutes; statement originals/passwords are not retained after processing. Bank integrations
are absent. Transaction descriptions may contain sensitive text; do not upload real records here.

Current processors: Vercel serves the frontend; Render runs the API and database. Console email
files are private dev outputs. A transactional email provider has not been selected. Google Gemini
is optional and currently disabled in hosted demo mode; live tool-result disclosure and consent
are described in the linked privacy document. Third-party terms, regions, contracts and retention
must be reviewed before real-user launch. Paid Gemini is required for that launch.

Account deletion removes owned application rows and private console outbox copies. Delivered email,
manual exports and external provider retention cannot be recalled. Free demo storage has no PITR;
future backup retention and deletion schedules must be defined before beta. Do not promise a
backup deletion period, cross-border safeguards or breach deadline that has not been approved.

Human review must define lawful purposes/bases, rights and export handling, retention schedules,
processor agreements, international transfers, children/age policy, grievance route and incident
notifications, including obligations under India's DPDP Act and applicable rules. No legal sign-off
has occurred. Users must not be asked to accept this draft as a finalized contract.

## Unapproved technical addendum: synthetic receipt inbox

DRAFT — requires review by a qualified lawyer. This addendum is not approved or required for
acceptance. The local synthetic mailbox rehearsal records separate consent and extracts only
merchant/payment date/INR amount and flags from committed fixtures. Evidence never changes spend;
a user must confirm any link to an existing bank transaction. Original mail bodies/headers and
addresses are not retained. After30 days extracted fields are cleared; minimal digest/status/link
tombstones remain until disconnect/account deletion to prevent resync resurrecting discarded
messages. Consent metadata remains until account deletion; sync records have seven-day retention
past expiry and OAuth state expires in five minutes (purged at hourly maintenance).

Voluntary plan-interest declarations have separate consent, are not inferred from financial or
mailbox data, and can be withdrawn independently. No offers/provider sharing exist in this release.
Actual live Gmail processing is unavailable and needs a separate approved policy and Google review.
See docs/MAILBOX_LAB.md for exact implementation boundaries; backup/email deletion limits remain.
