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
visibility decision. MIT LICENSE is present (copyright 2026 DEVENDRA RAJ SINGH).

See [implementation decisions](PHASE8_PLAN.md) and [operator procedures](RUNBOOK.md).

Status 2026-10-21: suppression/unsubscribe, support reports, legal-version recording, kill switch,
retention and metrics are implemented and locally tested but remain **blocked for launch** on the
owner prerequisites above. See DOD.md for the exact evidence and what has not been verified.

## Mailbox/interest expansion gates (2026-10-26)

- Implemented locally, not launch approval: synthetic consent, bounded leased fixture sync,
  separate receipt evidence, explicit bank matching and independent voluntary interests.
- OAuth PKCE/state/credential/HTTP protocol foundation is stand-in-tested only. Actual Google
  consent callback/orchestration, real inbox incremental sync and revocation delivery remain
  Not done. Google restricted-scope/security review, keys, legal/operational approval and private
  accuracy checks are required before activation. MAILBOX_LIVE_ENABLED=true currently fails.
- No provider agreement, offer, price, discount, entitlement sharing, fulfilment or billing is
  implemented. Provider negotiation/licensing is owner-led; no one was contacted by this work.
- Public demo keeps MAILBOX_LAB_ENABLED=false. All previous custom-domain/worker/sender/PITR,
  staging, incident response, legal and accessibility gates remain; free hosting is not beta-ready.

## Local operations evidence update (2026-10-26)

Eight two-API/worker coordination checks, synthetic 30-table restore equality, a nine-flow bounded
load test, local source rollback/re-promotion and limited ZAP baselines have run. See
[measured results and limits](LOCAL_DRILLS.md). The October28 strict-CSP rescan has zero high/medium/low findings; informational discovery findings remain.
These remove the previous "never run locally" gaps only. Managed PITR, hosted rollback, a
CI-enforced provider gate, separate staging, encrypted backup operations, real sender/domains,
worker availability and incident routing remain unverified. This remains **NO-GO**.

## October28 hardening update

Production style policy is self-only for styles/elements and denies inline attributes. Nine
compiled-build browser checks pass across Chromium, Firefox and WebKit; see
[CSP behavior and limits](CSP_HARDENING.md). Native exact-commit CI/API gating and paired hosted
publication/rollback receipts are maintained in [RELEASE_GATE](RELEASE_GATE.md). Earlier
statements about never-tested hosted behavior describe their historical date; current receipts
control. Managed PITR, staging and real-user launch remain blocked.
