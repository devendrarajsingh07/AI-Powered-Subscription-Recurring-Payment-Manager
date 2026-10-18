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
