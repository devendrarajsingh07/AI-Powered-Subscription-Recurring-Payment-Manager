# SubTrack — current state and coding-agent handoff

Updated 2026-10-20. The repository root is the workspace; do not create a nested subtrack folder.

## Current state

Phases 1–7 were released as v1.0.0 at 7dba254a2f84b62f525ee39595b1dfe907a03d04.
The tag is published. It means demo-complete for that scope, not production-ready.
Release/tag CI passed, including all 13 browser flows on Ubuntu:
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39368517177

The owner supplied a combined Phases 7/7.5/8 prompt. Additional Part 1 Gemini requirements
are complete: both hosted jobs passed on 4b36e5a (run39372903888). Part 2 implementation and local
verification are complete; both hosted jobs passed on764a3c9 (run39381573641). After Part 2, stop before Part 3
and request the Vercel/domain/container-host/managed-PostgreSQL/email/paid-Gemini prerequisites.
Do not invent accounts or deploy/invite real users automatically.

Stack unchanged: React/Vite/TypeScript/Tailwind/Recharts/TanStack Query/Router,
FastAPI/SQLAlchemy/Alembic/PostgreSQL16. Decimal money, decimal-string APIs, Alembic only.
Gemini is the sole live adapter; fake remains offline default. No live evaluation has run.
Recommendations/emails remain deterministic. No original statements or real user data in git.
Local web http://localhost:5173; API http://localhost:8000/docs. Development-only demo login:
subtrack-demo@example.org / SubTrackDemo2026!. make seed is implemented and idempotent.
After .env copy: docker compose up --build --wait, then make seed.

## Current verification

Part2 local:330 PostgreSQL backend tests,55 frontend tests; extraction matrix18 variants, silent0,
all rows flagged for review; clean text field accuracy1.000. Earlier detector gates remain1.0000.
OpenAPI/type drift, lint/typecheck/build and dependency audits pass. Available-browser13/13 pass;
the final review-position/screenshot rerun also passes13/13. Hosted checks/e2e pass on764a3c9; details are below.
Runtime image646058096bytes, non-root. No live Gemini/real-bank/manual screen-reader claim.

### Historical combined baseline

Combined baseline: ignored var/combined-baseline-20261020-095823/.
make dev, verify, test, lint, evaluate exit0. 287 PostgreSQL backend tests,46 frontend tests;
OpenAPI/TypeScript drift pass. Detector TP/FP/FN: synthetic16/0/0, handwritten bank3/0/0,
handwritten products5/0/0; precision/recall/F1=1.0000 each. Real-bank accuracy is unmeasured.
make e2e Windows:10 passed,3 failed; Firefox157 native launch fails before app execution.
The redundant available-engine baseline rerun had9 pass/1 fail: mapping preview state was lost
during a Vite reconnect while generated types were being written. Subsequent edits and browser
checks were serialized. Stable final addendum run:10/10 Chromium/WebKit flows pass. No browser
is removed and no assertions weakened. Ubuntu release and addendum checks/e2e passed.

Codex Process Jobs refused win32 as unsupported, so normal command execution is used. A local
Firefox repair copied the exact manifest embedded in its mozglue DLL to a sidecar. Launch still
failed, so that sidecar was removed and the original installation restored.

## Part 1 addendum — decisions before implementation

- Reuse Gemini and consent-reset migration0007. Do not rebuild the demo loader, repeat migrations,
  rewrite history or move published v1.0.0. New additive requirements get separate commits.
- Keep existing httpx REST transport. LLM_MODEL must be explicitly configured; no guessed default.
  Exactly fake|gemini. Key remains SecretStr in x-goog-api-key header, never URL/query/log output.
- Rechecked the official sources below on 2026-10-20. Sanitize schemas only at the adapter boundary:
  inline local references, keep a documented conservative subset, strip unsupported keywords.
  Server-side extra=forbid Pydantic validation stays authoritative and unchanged.
- Categorization uses constrained JSON structured output and server-side enum validation. Its only
  user data is the normalized merchant. Suggestions remain unconfirmed and never override choices.
- Process parallel function calls in provider order within existing caps. Malformed arguments become
  safe tool errors consuming a round; they never reach repositories. Five-round cap stays.
- Blocked, empty or truncated completions discard buffered model text and yield deterministic fallback
  with verified=false. No unverified token reaches the browser. Retry transient failures only, with
  existing bounds; cancellation closes upstream. Test with local HTTP, never live keys in CI.
  Unknown tools/extra identity fields still fail closed; only malformed wire-argument markers get
  the recoverable tool-error path. Existing injection/identity tests remain intact.
- Consent names Google Gemini and discloses tier differences. Unpaid Services terms permit product
  improvement and human review and prohibit sensitive/personal submissions. Paid Services terms
  exclude improvement use but permit limited safety/legal retention. The app cannot infer key tier.
  Operator must read the applicable terms before sending financial data; offline stays default.
- Active docs/errors/contract metadata name the configured provider; historical facts live under
  docs/history. Do not reapply superseded no-remote or phase-stop instructions from those logs.

Official sources (no live model calls):
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/function-calling
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/billing
- https://ai.google.dev/gemini-api/terms

## Limits and human-owned checks

Compose is dev/demo, not production. One API process; in-process workers/scheduler/limiters/chat gate,
no durable queue; INR only; nominal renewal dates; figure verification proves provenance, not prose.
SMTP is at-least-once across accepted-send/commit crashes. Exported/delivered data cannot be recalled.
Human screen-reader, private real-statement checks, and live Gemini evaluation remain unperformed.
Owner selected MIT; explicit instructions leave LICENSE absent for owner application.

Prior release audits: npm0/pip no known vulnerabilities; Gitleaks has three exact reviewed historical
synthetic JWT exceptions, no unreviewed findings. No .env/outbox/eml/private statements tracked.
Re-run scans for each new part; historical results do not certify new changes.

History preserving decisions/results/failures:
- [Phases1–5](docs/history/PHASES_1_5.md)
- [Phase6](docs/history/PHASE_6.md)
- [Phase7 release](docs/history/PHASE_7.md)

Priority: correct numbers > data safety > working demo > polish > extra features.
Part 2 implementation is starting. Part 3 requires the external-prerequisite handoff after Part 2.

## Part 1 addendum verification — 2026-10-20

Logs: var/combined-part1-20261020-102403/ (ignored). make dev/verify/test/evaluate exit0;
307 real PostgreSQL tests,46 frontend tests,18 independent offline questions; OpenAPI/TS drift pass.
Initial focused run53 pass/2 fail: disclosure assertion wording and too-broad invalid-tool recovery.
Both were fixed, preserving fail-closed user-id rejection; focused rerun55 pass, then one wire-schema
test added and the full307 passed. No known-answer expected values or evaluator were changed.

First make lint/build failed because the generated response type required provider in the typed
MSW fixture. Added explicit fake/gemini fixture providers. Repeated make lint, npm --prefix frontend
run build, npm --prefix frontend test -- --run all exit0 (46 tests). No source changes during the
stable browser verification: python scripts/run_e2e.py --project=chromium --project=webkit exit0,
10 passed (Chromium7/WebKit3). Hosted addendum checks/e2e passed on 4b36e5a; run39372903888:
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39372903888

npm --prefix frontend audit --audit-level=low:0 vulnerabilities. pip-audit against requirements.lock
in disposable Python3.12 container: no known vulnerabilities. Gitleaks full32-commit history: no
unreviewed findings, retaining only the3 exact historical synthetic-test exceptions. Post-commit scan covered33 commits including the addendum with no unreviewed findings. No .env/private statements/eml/LICENSE tracked; .env.example only.
Production bundle: main346.56KB/109.50KB gzip; lazy charts389.93KB/114.22KB gzip, unchanged.
One existing Starlette TestClient deprecation warning remains. No live Gemini, real-bank or human
screen-reader claim. Do not move v1.0.0; this is an additive post-release correction.

## Phase 7.5 decisions — recorded before implementation

- Local extraction only, never LLM/cloud OCR. Use pdfminer.six for positioned text (MIT), pypdf
  for decryption (BSD-3-Clause), Pillow for normalization (MIT-CMU), ReportLab for synthetic fixtures
  (BSD). Current PyPI metadata checked before dependency selection:20260107/6.21.1/13.0.0/5.0.1
  respectively. Check actual installed/transitive licenses after locking. No AGPL dependency.
  Tesseract CLI (Apache2) and poppler CLI (main GPL-2, component GPL-2-or-GPL-3/GPL-3) run as separate local programs, not linked libraries.
- Python dependencies get explicit pins and hashed requirements.lock. OCR English only. No phone
  photo/handwriting support claim; clean English scans/screenshots approximately200dpi+ are target.
- PDF/image previews become user-scoped PostgreSQL jobs with30-minute row-text TTL. Keep tiny
  content-free daily usage counters separately so cancellation/expiry cannot bypass quotas.
  Purge row payloads on confirm/cancel/expiry; deletion cascades. Confirm metadata/upload pointer
  may remain until TTL for idempotent reconfirmation; it contains no extracted row text.
- Original bytes/password are never stored in DB, logs or request URLs. Extraction runs in a
  subprocess with a private temporary directory, inherited per-process Linux address-space/CPU
  limits, bounded wall time and child-group termination. Remove temp files in finally. Environment
  excludes DB/provider credentials. This is NOT a hardened sandbox; Phase8 needs a separate
  no-network worker container/cgroup limits. No extraction code makes network calls.
- Intakes check magic/extension agreement, PDF10MB/30pages and image10MB/25MP before decoding;
  CSV stays5MB/50k rows. No arbitrary executable or filename interpolation; argument lists only.
- Reconstruct positioned table/list rows, retaining page/confidence and warnings. Join wrapped
  descriptions; remove repeated structural headings. Existing ingestion date/money parser owns
  validation: virtual CSV converts Dr/Cr suffixes into type, preserves Indian-grouped money for
  Decimal parsing, and retains raw descriptions. No second financial aggregation implementation.
- Reconcile Decimal running balances/opening/closing/totals and flag breaks plus neighbors. OCR
  always needs explicit review, even if balances reconcile: high confidence cannot prove a digit.
  Text-only rows also receive a review requirement. Conservative flagging is deliberate; report
  flag rate AND exact field accuracy, rather than presenting zero silent errors as OCR accuracy.
- Strict edits validate every value server-side. Flagged unverified rows are excluded and counted.
  UI disables import until flagged rows are verified, corrected or deleted; a clearly labelled
  bulk acknowledgment is allowed only as an explicit user review action. No auto-confirmed OCR.
- Review uses only a browser object URL for the original local copy, revoked on cleanup. Accessible
  inputs, flags filter, pagination and no client money calculations. Use existing query/API tokens.
- Corpus is synthetic only, generated from committed sample transactions with independent labels.
  Clean text-PDF exact field quality gate>=99%; silent-error gate=0 on every variant. Report OCR
  variants/errors/rejections honestly, including conservative review rate. No real-bank accuracy claim.
- No Phase8 work until this phase's tests/evaluation/audits/CI pass. Then stop for external accounts.

## Phase 7.5 implementation and verification log

Migration0008 adds scoped preview/usage tables, upload source_type and excluded_count. Parser jobs
use resource-limited subprocesses; user edits are strict and locked confirmation queues virtual CSV
through the real pipeline. No DB financial math or earlier known-answer expectations were replaced.
Every extracted row requires explicit review; this deliberately exceeds the minimum OCR guard.
Complete 18-variant measurements, dependency licenses and limits: docs/STATEMENT_IMPORT.md.

Commands/results (2026-10-20; ignored logs var/phase75-*):
- make dev / make verify: Compose health and migration-head checks pass; API uid/gid1000.
- make test: exit0, 330 PostgreSQL backend tests (one existing Starlette TestClient deprecation),
  55 frontend tests, OpenAPI export and generated TypeScript drift checks pass. Includes migrations
  upgrade/down/drift, 18 offline chat questions, parser/API privacy/security and the extraction gate.
- make evaluate (also in make test): synthetic16/0/0, handwritten3/0/0 and products5/0/0 TP/FP/FN;
  precision/recall/F1 all1.0000. Real-bank detection/extraction accuracy remains unmeasured.
- Extraction matrix: clean text field accuracy1.000; zero silent errors; all returned rows flagged.
  Clean synthetic date/amount/row quality floor150dpi. Skew-2 and deliberately corrupt amounts
  retain errors and reconcile as mismatch; skew+2/noise/blur/unreadable reject. No perfect OCR claim.
- python scripts/run_e2e.py --project=chromium statements.spec.ts:3/3 pass. Full available engines
  Chromium10/WebKit3:13/13 pass; final layout/screenshot rerun also13/13 (4.8minutes). All three
  engines remain enabled in hosted Ubuntu CI; native
  Windows Firefox157 cannot launch (SideBySide/mozglue), so no local Firefox app pass is claimed.
- npm audit --audit-level=low:0 vulnerabilities; pip-audit -r requirements.lock --disable-pip in
  disposable Python3.12 container: no known vulnerabilities. Hash-locked new Python dependencies.
- Private checker executed on synthetic list_text.pdf in network-none/read-only Docker with tmpfs:
  exit0,15 rows, terminal JSON only, every row flagged, reconciliation unavailable as labelled.
- API image646058096 bytes; Tesseract/poppler licenses inspected in installed Debian copyright;
  new Python/transitive license metadata reviewed (see statement-import doc). No AGPL dependency.
- Production build after review-position adjustment: main346.57KB/109.50KB gzip;
  lazy charts389.93KB/114.22KB gzip; lazy upload17.08KB/6.03KB gzip; CSS27.24KB/6.78KB gzip.

Failures retained honestly: initial subprocess stdin/communicate loop deadlocked, fixed with bounded
reader/writer threads plus cancellation/process-group cleanup. First OCR run lost low-resolution
rows; bounded upscale improved clean scans and quality rejection now catches degraded pages.
First text precision counter compared decimal string scales (119 vs119.00), fixed to Decimal keys;
labels/thresholds did not change. First new browser run failed3/3 because StrictMode cleanup cancelled
fresh jobs; generation-aware cleanup plus regression tests fixed replay and real unmount. First
lint run had one cleanup-ref warning; capture of the same stable lifecycle object removes it.
Visual inspection found review below the picker; review now precedes intake while active, and
screenshots are regenerated. Existing baseline suite results remain above as historical measurements.

Known gaps: English/INR only; foreign currency text elsewhere in PDF is not reliably detected, so
user must verify currency. Cover-only pages reject. All rows need manual review. Preview30-minute
TTL; counters retain counts until deletion. Subprocess isolation is not a hardened sandbox or OS
network block; same-container parser/API, in-process jobs/caps and restart-failed jobs remain demo
limits. No real statements, live Gemini, staging deployment or manual screen-reader pass performed.
No Phase8 account/session/queue/deployment work has started. Published v1.0.0 stays unchanged.
Optional future vision extraction would need a new explicit owner request, a separate disclosure
and opt-in; no such service or data transfer exists here.

Full-history gitleaks8.30.1:36 commits/~2MB, no unreviewed findings, retaining only the3 exact
historical synthetic-test fingerprints documented in DOD. Initial Windows textconv subprocess
failed despite scanner exit0; reran with --log-opts="--all --no-textconv" and verified all36 commits
were scanned without git errors. Staged backend/frontend scans also pass. git ls-files confirms
no .env, .venv, private-statements, outbox .eml or LICENSE tracked (.env.example is intentional).

## Phase 8 prerequisites — stop here until supplied

Need Vercel project and registrable domain (sibling web/API subdomains), container-host account and
region choice, managed PostgreSQL with PITR and separate staging/production databases, transactional
email account/verified sender, and Google project with paid Gemini billing/key. Configure secrets
through platform secret managers, never paste keys into chat. Prefer architectureA (static Vercel,
container API plus isolated worker, same-region database); no provider/region has been invented.
Human tasks: screen-reader/keyboard/zoom checks; own redacted CSV and PDF/image local checks;
paid Gemini live eval and spend alerts/terms; apply already-selected MIT choice when authorized;
qualified legal/privacy/DPDP review, DNS SPF/DKIM/DMARC, incident contact, invitees kept private,
and decision whether repository stays public. No second license-choice question is needed.

## Phase 7.5 hosted gate — complete

Implementation764a3c9f8eb0ec4fdb667690c2a494791f4a88e1: both checks and e2e passed.
https://github.com/devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager/actions/runs/39381573641
The unchanged browser configuration runs Chromium10/Firefox3/WebKit3 (16 flows) on Ubuntu;
Windows available-engine final run is13/13. Hosted jobs118491650807 (checks) and118491650673
(e2e) completed success. The following commit records docs/screenshots only; its fresh hosted
run is checked after pushing and reported to the owner. Do not retag v1.0.0 or begin Phase8.
