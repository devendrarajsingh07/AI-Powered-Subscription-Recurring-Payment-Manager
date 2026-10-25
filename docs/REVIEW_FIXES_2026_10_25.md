# Review fixes — decisions recorded before implementation

Scope: fix the six findings from the October 25 review, add regression coverage, update
the current handoff, and push directly to the existing default branch (`master`). No paid
infrastructure, live Gemini calls, real data, or beta activation is authorized.

- Add a nullable `subscriptions.billing_amount` NUMERIC(12,2) through an additive migration.
  Historical averages remain unchanged. A currently detected increase uses its latest charge;
  after consecutive eligible higher charges it establishes a new price (amounts may vary), and subsequent latest
  charges supply the billing projection even after the temporary price-increase notice resolves. A lone FX/usage spike does not permanently
  replace the average. Histories without that signal retain their average. Backfill charge-linked subscriptions
  using the same historical rule, frozen in the migration; user decisions are untouched.
- API money remains decimal strings. Expose the optional billing projection to renewal
  displays and read-only chat tools; no financial arithmetic moves into the browser.
- Recheck account existence and live-AI consent before every provider attempt, including
  retries and categorization, as well as the shared kill switch and quota reservation.
- Alert planning uses the same explicit-clock projection as the renewals API. Dates that
  have passed roll forward; two missed cycles remain uncertainty and suppress reminders.
- Upgrade only pypdf to its patched 6.21.2 release and regenerate its hash-locked entry.
- Configure CSP on the actual Vercel static server. External API connections are restricted
  to the existing Render demo origin; same-origin requests support local/proxy builds.
  Inline styles remain necessary for chart positioning; scripts do not permit inline code.
- Preserve prior handoff facts in docs/history; replace stale current instructions with
  actual commits, verification results, and explicit remaining launch/drill blockers.

## Verification

Full PostgreSQL suite: 486 passed (425.83s); frontend: 75 passed. Full lint/typecheck,
OpenAPI/type drift, detector/extraction gates and production build pass. Python and npm audits
are clean. Gitleaks all 72 reachable commits/current source clean. Hash-verified pypdf patch
installation passed. Mobile production-CSP browser probe passed real registration/demo load,
charts/renewals and deletion without CSP violations/page errors. Standard browser suite 16 passed across Chromium/Firefox/WebKit; strict TLS and public-demo
profiles each passed separately. Hosted CI receipts follow after push.

The first focused run exposed alert fixtures that relied on old overdue behavior; fixtures now
represent two genuinely missed cycles, and new regressions assert the correct rolling behavior.
The crash/outbox assertion identifies the original alert by id, not arbitrary UUID sort order.
A first CSP probe used a hidden mobile navigation link; using the actual Toggle navigation
control passed. Browser runner clock/origin setup was corrected before the final full run.

Final edge-case refinement: consecutive detected higher charges establish the price even when
FX/usage variation prevents exact equality. A lone spike still falls back to averaging. The
frozen backfill and pure regression use the same rule; the complete final gates passed afterward.
