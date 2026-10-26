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

## Phase 7 release polish

Browser plugin not available; regular Playwright is the requested fallback. Flow under test:
register → clock-relative demo ingestion → review → grounded chat → actual mail artifacts → deletion.
Screenshot evidence: demo-dashboard.png and release-chat-{light,dark}-360.png, synthetic only.

| Reference comparison | Rendered evidence / outcome |
| --- | --- |
| Existing slate/teal concept and shell | Preserved typography, sidebar, panel radii and spacing; no redesign/new visual system. |
| Dashboard hierarchy | Real import progress is dismissible after success, leaving API KPI figures and charts visible. |
| Navigation and theme reachability | Sidebar scrolls when short viewport cannot fit settings/user/theme controls; system/light/dark preference is guarded and applied before paint. |
| Mobile drawer | At360, title/close, offline disclosure, wrapped prompts and composer remain visible; conversation scrolls independently. |
| Honest data provenance | Demo badge carries explicit generation date; fixed bills, possible stopped/price notices and no-estimate recommendations remain distinct. |
| Charts | API values retained in tooltip and table alternatives; palette uses theme tokens, labels accompany colors. |
| Focus/errors | Skip link, route title/status announcement and main focus; native dialog Escape/return focus; auth/budget/preferences/delete errors associated with forms. |

### State checklist

Every row is implemented; automated unit/network/browser coverage is described in the last column.
An empty form is an initial state, not a successful response.

| View/action | Loading / empty | Error / success | Evidence |
| --- | --- | --- | --- |
| Login/register | Submitting disabled; blank labelled form | Generic credentials/429/server feedback; redirect | app.test and main e2e |
| Overview summaries/charts | Loading panels; upload/demo invitation | Retry panels; exact API KPI/legend/table values | component and demo e2e |
| Demo load | Checking availability, preparing, real row/stage polling | Safe failure/retry/removal path; completed counters and dismiss action | demo.test, test_demo, demo e2e |
| Demo removal | Confirmation, disabled removing action | Safe error in dialog; removed status, account retained | demo.test, test_demo, browser audit |
| Upload preview/mapping | File initial state, busy preview/import | Safe invalid CSV/row warnings; editable mapping and results | app.test, bank/malformed e2e |
| Upload progress | Pending/processing, persisted counters | Failed safe reason; done counts with unreadable-remainder warning | app.test and PostgreSQL progress tests |
| Upload history | Loading; no uploads | Retry error; paginated history | Upload component and real API |
| Subscriptions filters/page | Loading; no matches | Retry; sort/filter/page server responses | app.test and main e2e |
| Charge drawer/PATCH | Loading and disabled saving; no charges | Safe failure/rollback; server-confirmed notices/status | component, API and main e2e |
| Renewals | Loading; no upcoming items | Retry; dates and uncertainty labels | real browser and shared API tests |
| Categories/suggestion | Loading; all reviewed | Retry/manual fallback; unconfirmed suggestion/user confirmation | component/API/main e2e |
| Recommendations | Loading; no recommendations/filter matches | Safe action errors; accepted/dismissed server response, no estimate | insights.test and real insights e2e |
| Savings panel | Loading; no open estimates | Safe retry; server total | insights.test and demo e2e |
| Budget/preferences | Loading/current or no budget; saving | Associated errors; saved live status | API/component/demo e2e |
| Recent alerts | Loading; no delivery history | Safe failure reason/retry; actual sent/skipped/retrying | insights component/API/e2e |
| Chat config/history/turn | Disclosure/empty prompts, loading/status, Stop | Safe network/429/provider error; verified/fallback/tool sources | seven component tests, injection and chat e2e |
| Chat consent/clear | Disabled consent-dependent send/clearing | Safe error; consent saved/history cleared | typed MSW/API/e2e |
| Delete account | Typed gating and deleting | Safe retained dialog on failure; counts and logged-out receipt | component/API/e2e |
| Session expiry | Protected redirect | Clear sign-in message; reauth returns intended route | component/API auth tests |
| 404/global boundary | Explicit page or loading fallback | Plain-language reload/back action; never blank/raw error | page audit and boundary component |

### Automated scope and manual tasks

demo.spec audits login/register and all eight protected/404 pages with browser axe in both themes
at360px, plus chat and remove-demo dialog; all routes also check overflow at768/1280. Existing
main-flow tests check the charge drawer and account-delete dialog. No axe rules were suppressed.
Prefer-reduced-motion styles remain in place. Full final browser counts/results are in DOD.
Human to-do: screen-reader reading order, dynamic announcements, native-dialog keyboard tour,
zoom200–400%, high-contrast OS mode and touch-device usability. Automated axe is not a manual pass.

Final measured suites:286 PostgreSQL tests,46 frontend tests; available Windows Chromium7/WebKit3 pass.
Ubuntu hosted run39246044919 passed all13 browser flows, including Firefox3. Windows Firefox native
mozglue activation failure is documented, not skipped by the default suite. No screen reader claim.
# Combined-prompt Part 1 addendum — 2026-10-20

Browser plugin not available; existing Playwright workflow used. No React product layout changes.
Consent copy is served as plain text: Google Gemini, unpaid product improvement/human review,
paid safety/legal retention, operator responsibility for tier. Typed MSW live-consent test asserts
the provider/caveat and opt-in gate. Stable real-stack Chromium7/WebKit3 flows pass, including
all-page axe light/dark360 and responsive768/1280 checks. Native Windows Firefox launch remains
blocked; all three engines stay enabled for Ubuntu CI. Human screen-reader pass remains pending.
An earlier redundant run lost upload state during Vite reconnect while types were regenerated;
edits and final browser checks were serialized. No assertion/time limit was weakened.

## Statement-import audit — 2026-10-20

The frontend debugging skill was applied; its browser plugin was unavailable, so the existing
Playwright/axe workflow was used. Synthetic review screenshots are under docs/screenshots/statement-*.

| Async view/action | Loading / empty | Error / success | Evidence |
| --- | --- | --- | --- |
| File/password intake | Reading state, labelled keyboard picker | Size/format guidance; memory-only password cleared; preview job | typed MSW + real encrypted retry |
| Extraction | Pending/processing stage and page counts, backoff | Safe failure/readable re-export guidance; ready status | PostgreSQL lifecycle + real OCR |
| Review | Empty/query error; 25-row pagination | Reconciliation and uncertainty notices; plain-text hostile description | component + real PDF/image flows |
| Edit/verify/remove/filter | Unverified rows disable import | Edits reset verification; per-row/bulk acknowledgment; remove/undo | nine statement component tests |
| Confirm | Disabled invalid rows; importing state | Safe validation feedback; upload results/excluded counts | API validation/idempotency + real import |
| Cancel/unmount | Cancelling; polling cleanup | Safe failure; cleared payload and local object URL | component/API; StrictMode regression |
| Expiry/account deletion | No retained stale result | Scoped 404, TTL purge/account cascades | real PostgreSQL tests |

Browser axe covers review in light/dark at360px with no rule suppression; mobile overflow is
asserted. The text/scanned/JPEG paths assert independent ground-truth products and amounts;
PNG cancellation uses a real local image. Hostile descriptions stay plain text; password retries
and unreadable input are exercised. No console/page errors are allowed in the text-review flow.
An initial browser run found React.StrictMode cleanup cancelling a newly opened job. Cleanup now
distinguishes effect replay from unmount; a dedicated regression test and rerun cover both paths.
Human screen-reader/zoom/high-contrast/touch checks remain to-do; automated axe is not that pass.

Final Phase7.5 available-engine rerun:13/13 pass. Hosted implementation764a3c9 checks/e2e
passed run39381573641, including the unchanged Ubuntu three-engine configuration (16 flows).
# Phase 8 foundation supplement — 2026-10-20

Registration now has an optional password-type invitation-code field. A typed MSW component test
checks submission, safe closed-registration errors, no saved session and axe. Settings has an export
action with preparing/downloaded/error states; the error/retry component test and real JSON download
assertions in Chromium/Firefox/WebKit pass. Exported test files are synthetic and deleted after checks.
Full current suite:57 frontend tests,16 Linux browser flows; existing every-page both-theme/mobile axe
and responsive checks pass. New auth/settings screenshots reflect the actual synthetic browser runs.

Native Windows Firefox still fails before app startup. The initial local run also overlapped schema
edits and is not accepted as regression evidence (8 passed,8 failed). A first Linux runner used the
hostname `web` and Vite correctly rejected it; that runner was stopped after the first timeout.
Corrected runner shares the web container's network namespace and uses `http://localhost:5173`,
without disabling hostname protection. All16 then passed in5.3minutes. The API test clock was fixed
to2026-10-18 during the run and restored afterward. Official Playwright v1.64.1-noble plus Docker CLI
and Make were used in a local-only image; no production dependency/image change was required.

Manual screen-reader testing, live Gemini, real statements and deployed beta accessibility remain
unperformed. This supplement certifies only the tested synthetic demo foundation.

## Phase8 account-security continuation (2026-10-21)

New views/actions: verification and recovery forms (request/confirm loading, generic response,
safe error/success; labelled password/code controls; no code URLs), logout retry and logout-everywhere,
public-demo-only entry/notice and upload replacement. Typed MSW checks cover memory-only tokens,
single-flight refresh, cookie logout after access expiry, verification navigation, page titles and
recovery axe. The existing full browser audit remains required on each final revision.

Local sibling HTTPS browser flow passed1/1 in17.2s: app/api.subtrack.test, real registration,
console verification code, secure host-only cookie, reload/rotation, reset and revocation. Initial
TLS attempt correctly exposed dev CSP blocking the configured API; fixed with its exact origin,
not a wildcard. Certificates are ignored, short-lived local fixtures only; no system trust change.
The first normal-browser attempt exposed anonymous-bootstrap401 console noise and a reused login
rate bucket causing a11y navigation to lose its session. Fixed in product code and rerunning all
engines; no console assertions or browser projects were removed. Public-demo enforcement and
hosted verification remain separate gates. No manual screen-reader or live-service claim.

## Receipt-import UI slice — verified locally (2026-10-26)

Browser plugin not available; repository Playwright with the existing Linux browser image.
Flow: Upload → synthetic receipt → editable reviewed fields → actual queued upload → receipt
results → repeat/dedupe → missing-field cancellation → safe rejection → deletion.

| Check | Result |
| --- | --- |
| Page identity/nonblank/no framework overlay | Receipt heading and real form rendered on `/upload`; screenshots visually inspected |
| Network component states/actions |12 typed-MSW tests passed: type/size checks;409/422/429 retryable errors; capability visibility/public suppression; Decimal strings; edit clears approval; no empty import; cancel; hostile text; light/dark axe |
| Real pipeline | Eight imports and three independent labelled products/totals; replay inserts0, skips1; missing payment date remains empty; cancellation/rejection/deletion passed |
| Responsive/accessibility | Axe clean at desktop/light and360px/light/dark; no document overflow; table scroll stays inside labelled keyboard-focusable region; no email image/iframe/script |
| Console | No page/runtime/console errors before intentional invalid-receipt422 |
| Evidence | Desktop/light and mobile/light/dark screenshots outside repo; all three visually inspected |
| Regressions |525 PostgreSQL tests,87 frontend tests,19 actual browser passes across profiles; lint/type/contract/build/audits/scans passed |

Two clock-dependent browser failures were caused by the local Docker runner not forwarding the
fixed test clock; both passed after correction. First new receipt run timed out on the hidden
mobile theme selector; the harness now switches themes at desktop width and cleans up on timeout.
TLS first encountered a stale local nginx upstream502 after container recreation; proxy refresh
restored the strict test flow. No product guarantees were weakened. Screenshot originals and the
normal API clock/configuration were restored. Hosted CI is a separate publication gate.

Human screen-reader review remains unperformed. No live Gmail, real mail/statement accuracy or
live model test was performed; those remain explicit owner/launch tasks.

## Mailbox/evidence/interest expansion — verified locally (2026-10-26)

Browser plugin absent; existing Linux Playwright, real Compose API/PostgreSQL and separate worker.
Target: `/mailbox` → synthetic consent → real worker sync → evidence → bank upload → explicit match
without double spend → replay → separate interest consent/withdrawal → typed purge → delete user.

| Check | Result |
| --- | --- |
| Page identity/nonblank/no overlay | Meaningful real receipt form and proper route title; visually inspected screenshot outside repository |
| Component states/actions |12 typed-network tests cover consent/disabled/errors/retry, ambiguity, edits revoke approval, plain hostile text, light/dark axe, typed disconnect, independent interests and queued/running/done/failed progress |
| Real pipeline/numbers/privacy | First mailbox browser25.6s, final18.4s; independent labels/counts, zero spend before bank upload and exactly unchanged API summary after match/replay/purge; interests stay separate and can be withdrawn; deletion passed |
| Responsive/accessibility | Desktop/light and360px/light/dark axe clean; no document overflow; radio/checkbox layout corrected and final regression rerun |
| Runtime/console | No relevant page/runtime/console errors in positive flow |
| Full gates |554 backend/99 frontend;18 standard browsers6.7m + TLS1(11.7s) + public demo1(11.1s); contract/lint/type/build/audit/scans passed |

The public profile confirms the link is hidden and connection/sync/live-authorize/interest writes
are disabled. Screenshot originals and normal local flags/clocks were restored. Hosted exact-commit
CI/deployment evidence is independent. Human screen-reader and real inbox/provider behavior remain
unperformed and are not implied by these local checks. No email is rendered as HTML or sent to AI.


## Hosted release follow-up (2026-10-26)

Commit 6a8e3fa passed all four branch CI jobs in run40310641609 before promotion;
Vercel and Render were verified at that exact revision, with23 smoke checks and four disabled
mailbox/interest write checks passing. Render deployment dep-dbfjbcijnfac73cjk1rg succeeded.
A smoke attempt during rolling startup returned readiness503; the post-startup rerun passed.

Repeat master run40313272133 passed backend/frontend/security/same-site checks, but its PDF
browser flow failed the console assertion after a deliberately handled registration429. The
PDF imported399 rows and all expected products correctly. The registration helper already
waits for Retry-After and retries; console collection now starts after registration and remains
strict for the entire PDF flow. Auth throttling/error behavior remains independently tested;
no limiter, production behavior, retry count, or financial assertion was relaxed. The follow-up
commit requires its own exact-commit CI gate before promotion. Latest hosted runs, rather than
this historical failure, determine the final release status.

The older local master has divergent historical commits and was preserved. The verified checkout
is codex/mailbox-foundation; remote master was fast-forwarded normally, never force-pushed.


## Local operations regression (2026-10-26)

No product UI was changed. The final standard Linux/Docker browser invocation passed 18 cases
(two explicit profile skips); strict sibling-host TLS and isolated synthetic public-demo each
passed once: 20 distinct browser passes. Chromium, Firefox and WebKit main flows ran. Existing
mobile/light/dark axe, CSV/PDF/OCR/receipt/mailbox, chat, outbox and account-deletion checks stay
strict. Screenshot originals and normal clocks/flags were restored byte-for-byte.

568 backend and 99 frontend tests, lint/types/contracts, production build and dependency audits
passed. Local operations/ZAP evidence and limitations are in LOCAL_DRILLS.md. One medium
inline-style CSP warning remains; no authenticated penetration test or human screen-reader
certification is claimed. The public-demo profile uses a development Vite server for axe
injection; production static CSP is checked separately. Human screen-reader pass remains a to-do.
