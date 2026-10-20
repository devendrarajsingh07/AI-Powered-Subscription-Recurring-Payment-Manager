# Changelog

## Unreleased — combined-prompt Part 1 addendum — 2026-10-20

- Harden Gemini wire schemas, JSON category suggestions, blocked/empty/truncated fallback,
  malformed-argument handling and local HTTP protocol/security tests.
- Add tier-dependent Google data-use disclosure and configured provider in chat config.
- Archive the Phase 7 handoff facts; keep the published v1.0.0 tag unchanged.
- PDF/image import and hosted beta remain pending their sequential gates.

## 1.0.0 — 2026-10-19 — demo scope

- Phase 1: Compose, FastAPI/Vite scaffold, migration readiness, CI and locked Python dependencies.
- Phase 2: Decimal normalization/detection, amount clustering, synthetic truth and handwritten evaluations.
- Phase 3: PostgreSQL persistence, scoped JWT APIs, background idempotent imports, summaries and deletion.
- Phase 4: typed React UI, upload mapping/progress, charts, review drawers, budget and privacy controls.
- Phase 5: deterministic recommendations, advisory decisions, scheduler, atomic dev outbox and SMTP retries.
- Phase 6: read-only tool chat, server figure verifier, offline policy, opt-in live provider and category suggestions.
- Phase 7: relative-clock demo loader/seed/removal, production guards, Gemini replaces Claude per owner request,
  system theme, accessibility/responsive and cross-browser checks, headers, dependency remediation and release docs.

1.0.0 denotes completion of the measured demo scope, not production readiness. See docs/DOD.md
and docs/ARCHITECTURE.md for evidence and limits. MIT was selected by the owner; no LICENSE file
is included in this phase under the explicit instruction not to add one.
