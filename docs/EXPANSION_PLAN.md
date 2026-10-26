# Receipt connections, reconciliation and voluntary interest — implementation plan

Owner request: complete the remaining code. Free hosting and all launch locks remain in force.
No live Gmail/Gemini calls, paid resources, new accounts/terms, real data/users or beta tags.

## Decisions before implementation

1. Add a development-only **synthetic mailbox lab**, default off and impossible in production or
   the public demo. It syncs only the committed synthetic EML corpus through the real receipt
   parser. Label it a rehearsal, never a connected Gmail inbox. Live Gmail activation remains
   hard-disabled; an OAuth/HTTP adapter may be tested only with an injected local transport.
2. Persist connection consent/version, scoped OAuth state (hashed, expiring, single-use, PKCE),
   encrypted credential material using an independent encryption key when exercised in tests,
   bounded leased sync progress, and extracted receipt evidence. No email body/header/address is
   retained. Provider message identity is a digest, unique per connection; retries never recreate
   evidence or overwrite a user's decisions. After30 days, clear extracted fields but retain a
   digest/status tombstone until disconnect/deletion so resync cannot resurrect ignored/expired
   evidence. Disconnect cancels work and purges these tombstones as well.
3. New receipt evidence is **not a transaction** and never enters summary/detection/savings math.
   Reconciliation proposes same-owner bank debits with equal INR Decimal amount, normalized
   merchant and a payment-date window of three days. Require explicit user confirmation of a
   returned candidate; ambiguity never silently selects a charge. No candidates means unresolved,
   not a fabricated payment. Legacy receipt-upload workspaces keep their existing no-mixing guard.
4. Reuse the PostgreSQL/worker architecture. Add a small domain sync lease table (no raw inputs)
   consumed by the existing separate worker after its upload queue. Claims use SKIP LOCKED;
   generation fencing and row locks recheck consent at every item. Cap one sync at16 fixtures;
   expose processed/total/accepted/rejected/duplicate counters, retry with attempt/TTL bounds.
   This is verified locally, not a claim about a worker on the free hosted inline demo.
5. Voluntary category-interest declarations use a separate table/purpose/consent version. Never
   query mailbox, transaction, receipt or subscription data for commercial cohorts. No offers,
   prices, affiliation or availability are invented, and no provider is contacted. Real provider
   agreements/fulfilment/billing remain not done; code cannot obtain an agreement for the owner.
6. Additive migration only, model-drift/up/down tests, strict JWT-scoped APIs and generated types.
   UI is hidden on the public demo and shows an explicit synthetic/offline label locally.
7. Publish to an isolated branch for exact-commit CI first, then fast-forward master without a PR
   or force push. This lets Vercel's existing Git auto-deploy start only after that commit is green;
   manually deploy the same green commit to Render. No hosting settings or feature flags change.

## Remaining external gates

Google restricted-scope review/security requirements, approved privacy/retention design and real
OAuth credentials; private real-receipt/bank accuracy measurements; lawful provider agreements;
existing custom-domain/sender/worker/PITR/staging/legal/incident-contact/accessibility launch gates.
Nothing verified with local stand-ins is labelled launch-ready.

Official references checked2026-10-26:
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2/resources/best-practices
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/workspace/gmail/api/guides/sync

Verified local gate:554 PostgreSQL/99 frontend/20 distinct browser cases; lint/type/contract/build,
evaluators, audits and history/tree scans passed. Exact commands/timings are in PROJECT_INFO.md
and MAILBOX_LAB.md. Live Gmail runtime wiring and provider agreements remain Not done.
