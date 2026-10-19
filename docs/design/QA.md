# Phase 4 visual and browser verification

The generated [design reference](subtrack-concept.png) was inspected before implementation.
It is a layout reference, not a screenshot of working software. All screenshots in
[../screenshots](../screenshots) come from the real Compose API with synthetic data.

## Fidelity ledger

| Reference commitment | Implemented result / deliberate difference |
| --- | --- |
| 232px dark slate sidebar, teal active navigation | Same width, grouping and icon/text hierarchy; collapses into a keyboard-operated menu below 700px. |
| Cool canvas, restrained white panels, teal actions | CSS variables support light/dark. Light teal was darkened to `#076f68` after browser axe found insufficient contrast on success text. |
| Title and upload action above a four-part KPI strip | Preserved. Real API totals replace empty reference values; subscriptions and fixed bills remain explicit. |
| Two chart panels with clear headings | Real Recharts trend/donut replace reference empty states. Exact API amounts remain in legends/tooltips and table alternatives. The category legend expands for the actual dataset. |
| Upcoming renewals table followed by future savings notice | Real five-item API results include uncertainty notices, so the populated page is taller than the empty reference. Savings remains clearly Coming soon with no figure. |

The reference and rendered desktop/mobile screenshots were opened and visually compared. The
intended hierarchy, navigation, whitespace, boundaries and reading order are retained. Populated
tables, charts, badges, dark mode and the compact mobile layout are intentional adaptations.
This is not a claim of pixel-identical reproduction of the generated image.

## Browser evidence

Playwright Chromium runs against the real Compose stack with PostgreSQL 16. It checks page title,
meaningful DOM, real upload results, ground-truth products, API-equal dashboard values, persisted
actions, dialog focus/Shift+Tab containment/Escape/focus restoration, budget saving, deletion counts
and logout. A page-error listener covers the main flow. Mobile viewport is 360×800; the test asserts
no document-wide horizontal overflow. Tables may scroll within explicitly keyboard-focusable regions.

Browser axe runs with all default rules on registration, the populated charge drawer, and the
dashboard at desktop/light, desktop/dark and mobile/light sizes. Component axe checks run without
color contrast because jsdom lacks real layout/canvas; browser axe covers contrast. Findings fixed
during implementation: success-message contrast, mobile header landmark, keyboard focusability
for horizontally scrolling tables. Final command counts are in PROJECT_INFO.md.

Images show synthetic accounts and statements only. Browser reports/traces are ignored by Git and
Docker; they can contain short-lived test tokens and must not be published as application assets.

## Phase 5 extension — 2026-10-19

The flow under test is: register → upload committed CSV → review real recommendations →
record review intent → configure notification email → run the real alert CLI twice → inspect
one renewal and one budget delivery → delete account and private outbox copies.
Browser plugin not available: used the explicitly requested regular Playwright Chromium workflow.
No new image generation was needed for this extension to the existing slate/teal design system.

The original concept and the latest desktop dashboard, desktop/light recommendations,
desktop/dark recommendations, 360px recommendations and delivery-settings screenshots were
opened with view_image and compared directly. The screenshots show synthetic data only.

| Comparison point | Phase 5 evidence / intentional adaptation |
| --- | --- |
| Navigation hierarchy and slate rail | Existing rail, icon/text rhythm and teal active state retained; Recommendations is a real additional route. |
| Cool canvas, white panels, restrained borders | New recommendation list and alert table use the same variables, spacing and panel boundaries. Dark mode reuses the existing tokens. |
| Reading hierarchy | Page heading, advisory notice, filters, recommendation heading, estimate and actions remain distinct. No estimate and extra cost have separate labels. |
| Action treatment | Teal Record review intent action waits for server confirmation; bordered Dismiss action is secondary. Affected-product links open the real charges drawer. |
| Dashboard continuity | Existing KPI/chart/renewal order retained. Coming soon is replaced by the API-provided savings panel in the same lower-page position. |
| Mobile behavior | 360px header/menu, wrapping actions, stacked member costs and pagination remain inside the viewport; no document overflow. The long list is intentionally scrollable vertically. |
| Honest delivery and privacy | Settings explicitly labels private development outbox mode and shows actual sent/pending states. Deletion explains which copies can be removed. |

Browser axe found no violations in recommendations at desktop/light, desktop/dark and 360px,
or in the delivered-alert settings screen. Tests also verify meaningful DOM, action outcomes,
drawer Escape/focus behavior, and no page errors or console warnings/errors in the Phase 5 flow.
Component checks cover loading, empty, error, no-estimate, accept/dismiss acknowledgements,
server savings and safe alert states through typed MSW network responses. Browser checks cover
layout and color contrast; jsdom does not implement real canvas/layout.

Final local gates: 208 PostgreSQL tests, 35 frontend tests, four real-stack browser flows.
The Phase 5 browser flow produced actual multipart HTML/plaintext .eml files through ConsoleNotifier,
verified stable artifacts on repeated CLI runs, and verified private copies disappear on deletion.
Real SMTP is tested against a local aiosmtpd server, including the documented crash ambiguity;
no external inbox delivery is claimed. Full commands and hosted CI are in PROJECT_INFO.md.

## Phase 6 extension — grounded assistant

The flow under test is: register → upload sample and a synthetic hostile merchant → open chat →
ask this-week renewals → compare every displayed date/charge amount to the real API → inspect
persisted history → ask injection requests → clear history → delete the account and chat rows.
Browser plugin not available; regular Playwright Chromium used, as in the earlier phases.
The API clock is fixed to the committed truth date during make e2e and restored afterward.

The original subtrack-concept.png and the latest chat-desktop, chat-dark and chat-mobile screenshots
were opened with view_image and compared. This extends the existing system, with no new ImageGen
asset needed. All screenshots and uploaded fixtures are synthetic.

| Reference / interaction point | Final result |
| --- | --- |
| Slate/teal hierarchy | Existing shell and panel tokens retained; chat is a 600px edge drawer, full-width at 360px. |
| Headings and boundaries | Clear title/close action, disclosure, conversation, prompts and composer. Native modal semantics preserve focus and Escape. |
| Light/dark contrast | Uses existing text/panel/accent variables; full browser axe passed in both themes. |
| Honest state | Offline rule-based label stays visible; external sharing is explicit and live consent defaults off. Unverified answers have a separate fallback notice. |
| Conversation readability | Merchant, charge and renewal date are templated from actual tool output; no repeated JSON field prefixes in normal offline renewal replies. Tool sources remain visible below answers. |
| Scroll and mobile controls | Title and composer remain in view; the conversation scrolls independently with keyboard focus. Prompt buttons wrap and the 360px document has no horizontal overflow. |
| Plain-text safety | Hostile strings remain text. No HTML/markdown execution, console message content or browser financial math. |

The first full-page screenshot exposed page/dialog scrolling that hid the composer; fixed by
scrolling only the conversation and capturing the real viewport. Browser axe then found the
new scrollable region needed tabIndex; fixed rather than suppressing the rule. Final desktop,
dark and mobile axe checks pass, as do focus restoration and Escape. Phase 6 browser listeners
report no page errors or console errors/warnings. Seven typed MSW component tests cover consent,
stream/status/Stop, rate-limit and provider error feedback, fallback notices, hostile plain text,
clear history and structural accessibility. The full frontend suite has 42 tests.

See PROJECT_INFO.md for final backend/evaluation/CI evidence and verifier limitations. This is a
figure-provenance guarantee, not a claim that all natural-language prose is correct.
