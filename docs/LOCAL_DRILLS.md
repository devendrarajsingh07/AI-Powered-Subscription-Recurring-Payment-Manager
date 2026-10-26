# Local operational drills

Status: local drills completed; final regression/publication gates recorded below. Synthetic data only;
no hosted configuration changes are made and the real-user beta stays locked.

## Decisions recorded before execution (2026-10-26)

- Use a separate Compose project, `subtrack-drills`, with its own database and volumes.
  Never load the normal `.env`, access hosted credentials, or dump the normal application DB.
  Generate ephemeral development-only settings under ignored `var/drills/`.
- Run two API containers, one separate worker, a credential-free/network-free restricted
  extractor and a local static web/reverse proxy. Keep the original stack intact. Publish
  no ports: probes run inside the internal drill network, which has no outbound access.
  Docker Desktop does not publish ports on internal networks. LLM stays fake, SMTP stays off.
- Exercise actual HTTP requests and container kills. Database locks may deliberately hold real
  work at a known boundary; no fake handlers, fabricated successes or financial fixture inserts.
- Measure restore using PostgreSQL 16 custom-format dump and transactional `pg_restore` into a
  second disposable PostgreSQL container. Quiesce source writers; compare every table's count
  and canonical row digest before checking restored application behavior. Managed PITR remains
  owner-blocked. The normal pytest harness creates separate test databases, so its results must
  never be described as verification of the restored rows themselves.
- Use the official Grafana k6 image for a bounded local workload, never the free hosting URLs.
  Report machine/runtime limits, workload, p50/p95 and error rates; make no production capacity
  claims. Explicit test-only quota overrides, if used, must be recorded with the measurements.
- Use the official OWASP ZAP image for a time-bounded local baseline scan. Keep detailed
  reports private/ignored; publish sanitized finding summaries. A passive baseline is not a
  penetration test or a claim of authenticated coverage.
- Rehearse source rollback locally with immutable Git-archive images. Require exact revision
  and readiness checks; never downgrade the database. Distinguish same-schema rollback from
  an older binary rejected by the migration-head check. No hosted rollback is authorized here.
- Keep only `master`, use additive fixes if drills reveal bugs, and run the relevant/full
  regression gates before committing. Production guards and all existing privacy rules remain.

## External limitations that remain

Managed backup/PITR, deployed worker availability, staging, real sender/domain, monitoring and
incident contacts, legal approval, real-source accuracy, live Gemini and live Gmail are not
established by local stand-ins. Do not turn any of these results into beta approval.

## References

- [PostgreSQL 16 pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- [ZAP baseline scan](https://www.zaproxy.org/docs/docker/baseline-scan/)
- [k6 scenarios](https://grafana.com/docs/k6/latest/using-k6/scenarios/)

## Measured local results (2026-10-26)

The application source was `67d5a31` during these drills; this tooling was developed locally.
The full local regression gate passed; command receipts and limits are recorded below.

| Drill | Actual result |
| --- | --- |
| Multi-instance | Eight distinct checks passed: real worker SIGKILL/reclaim, concurrent upload dedupe/isolation, shared preview quota, shared chat cap, API SIGKILL/chat expiry, shared queue capacity/queued deletion, running-extraction deletion, and shared login window |
| Worker recovery | Attempt two reclaimed accepted work; exactly 399 transactions and 16 labelled products, no duplicate charge rows; encrypted input purged |
| Shared admission | Queue 8 and per-user 3; login 10 then 429 across API instances; chat 2 then 429 and preview 2 then 429 using explicit test settings |
| Account deletion | Queued/running jobs and owned records removed; no orphan financial rows or extraction temporary directories |
| Restore | 310,478-byte custom-format archive; all 30 table counts/digests and 5,808 rows matched, including 3,591 transactions |
| Restore behavior | Ten exact API comparisons; login, ownership 404, duplicate re-upload and Alembic drift passed. Deleting a restored user left its source user intact |
| Restore timing | pg_dump 1.188s; pg_restore 1.953s. Final CLI 102.922s, including quiescence, transfer, restarts and verification; not a production RTO |
| Bounded k6 load | Three VUs × three iterations: 9 verified flows, 553 HTTP requests, 580 checks, 0% HTTP failure rate |
| HTTP latency | p50 11.59ms; p95 79.60ms. Frequent progress polls dominate this aggregate |
| Full-flow latency | p50 14.14s; p95 19.30s. CSV plus real text/OCR extraction, explicit scripted source-label review/import, exact totals and verified offline chat |
| Local rollback | Both archived frontend/API served 92b9ae6, preserved every row digest and summary, then re-promoted 67d5a31. Verify phase 41.72s; full CLI 89.0s including builds/cleanup |
| Incompatible rollback | 7c56cb1 has Alembic head 16 and correctly returned readiness 503 against head 17. No DB downgrade |
| Isolation | API/worker/static web non-root, read-only roots, dropped capabilities; internal-only network and no published ports. Extractor has no credentials/network, 1 CPU, 768MiB and 64 PID limit |

Machine: AMD Ryzen 7 8840HS with Radeon 780M; Windows 11 build 26200, Docker Desktop engine 29.8.2,
16 Docker-visible CPUs and 15.26GiB RAM. APIs/worker had no per-container CPU cap; extractor had
1 CPU/768MiB, k6 had 1 CPU/256MiB. The normal development stack remained running idle. This is
a small local sanity workload, not sustained stress or capacity evidence for free Render.

The k6 profile temporarily raised auth login/register limits to 1000, chat minute/day to 60/500,
and preview daily to 100. It kept queue 8/per-user 3 and one separate worker. The coordination
profile separately proved real shared throttling; no production setting was weakened. The
original private drill configuration was restored after every profile.

## ZAP baseline findings

Both time-bounded scans completed and retained ZAP exit 2 (warnings) in the private receipts.
The wrapper reports completed scans, not a clean security certification. No rules were hidden.

| Target | Finding | Disposition |
| --- | --- | --- |
| Static web | CSP style-src unsafe-inline (10055), medium | Remains: existing chart/UI inline styles. Requires a style/nonce policy audit before a stronger production claim; script-src remains self-only |
| Static web | Modern Web Application (10109), informational | Traditional unauthenticated spider has limited SPA coverage; no authenticated/Ajax/pentest claim |
| API | Authentication Request Identified (10111), informational | Discovery notice, not proof of authentication coverage |
| API | Session Management Response Identified (10112), informational | Discovery notice, not proof of session security |

A missing form-action directive in the first **local proxy** policy was corrected to match the
existing Vercel policy; the rescan cleared that warning. API spider also noted its root 404,
which is intentional for the API-only server. There were no high-risk alerts in this limited
baseline; no vulnerability-free claim is made. No scan targeted hosted URLs.

Detailed HTML/JSON reports, fixture account tokens, settings and the **unencrypted synthetic-only**
archive stay in ignored `var/drills/`. Public documentation contains only counts, timings and
finding metadata. The Docker image references are pinned by digest in the driver.

## Reproduce safely

Prerequisites: running Docker Desktop/Engine with Compose, Python 3.12+, GNU Make and several GB
of free image storage. This uses the reserved local project `subtrack-drills`; never point it
at another environment. Run from the repository root.

```sh
python scripts/local_drills.py prepare  # first run only; refuses to overwrite existing settings
make drill-tools                       # pinned official k6/ZAP images
make drill-up
make drill-coordination
make drill-restore
make drill-load
make drill-scan
make drill-rollback
make drill-isolation
make drill-down                        # preserves volumes/evidence, stops only the drill project
```

On subsequent runs reuse the private configuration and start at drill-up. It refreshes only the
source-revision label from Git HEAD before building; existing credentials and volumes are kept. For a legitimate
setup login after the rate-limit test, the driver honors a bounded Retry-After instead of
resetting or bypassing the limiter. Profile changes always restore the original settings.
The rollback source refs are historical master ancestors; if removed or dependencies differ,
the driver fails rather than inventing a revision or silently reusing different dependencies.

A subset can be resumed with `python scripts/local_drills.py coordination --only shared-auth-window`
or `python scripts/local_drills.py scan --only web`; omitted steps never count as passed.

The restore regression suite uses its own disposable test databases on the **restored PostgreSQL
service**. That is separate from the actual restored-row checks described above. Restored
sessions are intentionally retained for exact-copy/login verification; before exposing a real
restored environment, revoke sessions and rotate operator-controlled secrets. Managed restore,
key rotation, staging and backup encryption/retention still need owner-led verification.

## Harness corrections recorded honestly

- Static build initially lacked its checked-in OpenAPI context; the build now receives it explicitly.
- Docker Desktop internal networks did not publish host ports. HTTP probes now run inside the
  network; isolation was kept rather than opening the application network.
- A single psql batch buffered its lock-ready marker until after the wait. Separate commands now
  establish that work is actually in flight before a container is killed. The initial one-attempt
  completion was rejected as crash evidence.
- A killed HTTP stream can end as an incomplete read; the relay reports a safe connection failure.
- Using one nonexistent email confounded account backoff with IP throttling. Distinct synthetic
  emails now isolate the shared IP window.
- The complete sequence exposed a legitimate setup 429 after the intentional throttle test. The
  setup client now obeys Retry-After and the resumed restore passed; the failed receipt is retained.

No hosted deployment, account creation on third-party services, live provider calls, real user
data, paid resources or beta release was used. Current production guards remain unchanged.

## Build-context privacy regression

Harmless nested EML/CSV/environment canaries proved that the old root-only Docker exclusions
copied all three canaries into each proof image. Recursive exclusions now copy zero in both
contexts, preserve exactly the 16 approved backend synthetic email fixtures, and include no
frontend emails. `python scripts/check_build_context.py` repeats the real Docker COPY test in CI.
This establishes a build-context flaw, not evidence that real records or secrets were present.
Private canaries were deleted in finally blocks; no private values are recorded.

The first extra restored-service regression run failed five tests: inherited drill environment
values contradicted standard test defaults, and a fake HTTP fixture released retry headers before
its consent-withdrawal transaction committed. The test process now uses standard environment
semantics, and the fixture commits withdrawal before releasing the 503. Privacy assertions and
runtime behavior are unchanged; the failed receipt is retained privately.

The final restore/isolation rerun passed after assigning the restore API/worker a separate
outbox volume. Its current measurements supersede the earlier 236,830-byte / 3,892-row run.
Starting the real stack again also verified that credentials were preserved and the build
revision matched Git HEAD. Initialization/build took 50.938s; isolation checks took 5.546s.

## Final regression commands and results

- `make dev verify`: passed (47.375s).
- `make test lint evaluate`: passed (674.172s): **568 backend tests** (565.73s) and
  **99 frontend tests** in 11 files. Ruff/ESLint/types and OpenAPI/generated-type drift passed.
  Detector TP/FP/FN: synthetic 16/0/0, handwritten bank 3/0/0, products 5/0/0;
  P/R/F1=1.0000 each. Extraction gate and receipt outcomes 16/16 passed. Real-source accuracy unmeasured.
- Extra full backend run on the restored PostgreSQL service: **568 passed** (547.50s).
  These use separate fixture DBs, not the restored application rows. One upstream
  Starlette/TestClient/httpx deprecation warning remains in each backend run.
- Real-stack Linux/Docker browsers: **18 standard passes** (two profile skips), plus
  **one strict sibling-host TLS pass** and **one isolated public-demo pass**: **20 distinct cases**.
  Chromium/Firefox/WebKit ran; mobile light/dark axe, real imports/chat/outbox/privacy passed.
  Existing tracked screenshots and normal API/worker flags/clocks were restored byte-for-byte.
  Native Windows runner/cache limitations used the established Linux browser equivalent.
- Production build passed: main 354.65kB/gzip111.74, lazy mailbox 11.84/gzip3.90,
  chart 389.93/gzip114.22; Vite build 7.42s (full CLI 20.562s). No performance SLA.
- `npm audit --audit-level=low`: zero; `pip-audit -r backend/requirements.lock --disable-pip`:
  no known vulnerabilities. Root Ruff, k6 ESM syntax, isolated Compose configuration and
  real Docker build-context canary checks passed.
- Gitleaks entire pre-commit history (76 reachable commits) and current non-ignored source:
  no leaks found. Exact historical synthetic-JWT exceptions and the 16-fixture EML allowlist
  were not broadened. No .env/private statements/private emails/outbox are tracked.

| Actual command/profile | Exit | Wall seconds |
| --- | --- | --- |
| make-dev-verify | 0 | 47.375 |
| backend-on-restored-pg | 0 | 556.141 |
| make-test-lint-evaluate | 0 | 674.172 |
| root-tool-lint | 0 | 0.047 |
| production-build | 0 | 20.562 |
| npm-audit | 0 | 2.938 |
| pip-audit | 0 | 13.172 |
| browser-clock | 0 | 29.047 |
| standard-browsers | 0 | 354.89 |
| tls-fixtures | 0 | 0.672 |
| tls-stack | 0 | 26.157 |
| tls-proxy-refresh | 0 | 1.687 |
| same-site-browser | 0 | 18.531 |
| restore-normal-before-public | 0 | 28.515 |
| public-dev-web | 0 | 0.453 |
| public-drill-api | 0 | 18.672 |
| public-demo-browser | 0 | 18.75 |
| restore-private-drill-config | 0 | 17.078 |
| restore-normal-stack | 0 | 2.985 |

Browser profile names above refer to real Docker/Linux Playwright CLI invocations against the
Compose stack, with the same fixed clock and restored settings as make e2e. The strict TLS
and public-demo profiles ran separately; the public-demo profile used the isolated drill DB.
Its Vite test server permits the established axe injection; production static CSP was tested
separately by ZAP. Do not claim the public E2E exercises production CSP.

Final cleanup: `make drill-down` stopped/removed only the isolated project, including restore
services; volumes/evidence remain. No running drill-project containers remained. Subsequent
`make verify` passed the web and both API readiness paths. Normal development stack stays up.

## Hosted browser-runner correction

Run 40359305930 on 52b0f7c passed main checks, secrets and strict auth. The full browser job
stalled before tests while apt downloaded 185 packages from the Ubuntu 26.04/resolute mirror
(selected by floating ubuntu-latest). This was observed in its live GitHub log, not inferred
from a test failure. Browser jobs now pin ubuntu-24.04, matching the successful local Noble
runner, with an eight-minute installation limit and 30-minute job bound. No browser, assertion
or test was disabled; the follow-up commit requires its own complete hosted CI result.

The pinned run 40362767316 reproduced slow Azure-mirror downloads on Noble too; the OS pin alone
was insufficient. CI browser jobs now fetch the same signed Ubuntu packages from Ubuntu's
HTTPS primary archive, retaining signature validation, plus 30-second transport timeouts/two
retries. This changes disposable CI only. The earlier run 40359305930 was canceled after
explicit owner approval, before its browser tests. No test result was fabricated or skipped.
