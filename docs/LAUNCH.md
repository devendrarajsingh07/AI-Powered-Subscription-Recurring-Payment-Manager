# Private beta launch gate

**NO-GO for real users.** The owner selected free hosting on 2026-10-20. The current public URL
is a synthetic-data demo, not a completed Phase 8 beta. Do not send invitations to real users.

Stage 0: synthetic staging only. Run baseline/security suites, multi-instance crash recovery,
deployed browser tests, restore and rollback drills, modest load measurements and scans. Separate
staging and production projects/databases are required before continuing; none is provisioned yet.

Stage 1: a small trusted group selected privately by the owner, only after every launch gate passes.
Never commit invitee names, email addresses, statements or feedback attachments to this repository.
Stage 2: widen only after first-week content-free metrics and incidents are reviewed by the owner.

Go/no-go requires verified invite-only accounts and revocable sessions; shared limits/durable jobs;
isolated OCR; actual backup restore; tested real email and suppression; paid Gemini with consent,
caps and spend alerts; legal review; incident contact; deployed security headers; green CI and
rollback evidence. Existing demo tests do not certify these new requirements.

Feedback: ask for route, approximate time, safe error code and steps to reproduce with synthetic
data. Never request statements, screenshots of financial records, chat contents or passwords.
Reproduce privately with a synthetic fixture, record severity, test a fix, then notify the reporter
through the owner's chosen support channel. No support address is configured yet.

Human prerequisites: domain and sibling web/API DNS; verified email sender/SPF/DKIM/DMARC;
managed PostgreSQL/PITR and separate worker budget; paid Gemini billing and spend alerts; legal
review including India's DPDP Act and applicable rules; incident/grievance contact; invitee selection;
screen-reader pass; private CSV/PDF/image accuracy checks; live Gemini evaluation; repository
visibility decision. MIT was selected, but applying a license remains owner-controlled.

See [implementation decisions](PHASE8_PLAN.md) and [operator procedures](RUNBOOK.md).
