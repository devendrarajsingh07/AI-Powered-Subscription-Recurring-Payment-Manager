# Production style CSP hardening

Decisions recorded before implementation, 2026-10-26. Free hosting and the synthetic-only
demo remain; no paid provisioning, live providers, real statements or beta activation.

- Remove the production inline-style exception. Explicitly require `style-src 'self'`,
  `style-src-elem 'self'`, `style-src-attr 'none'`, and keep scripts self-only. Do not introduce
  unsafe hashes, broad origins, dynamic nonces or a framework change to conceal failures.
- Trusted JavaScript may still set individual CSSOM properties. This is not a promise that
  rendered DOM contains no style attributes. The policy must block untrusted inline markup,
  style elements and setAttribute-style payloads, while real charts/tooltips remain usable.
  See [browser behavior](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src-attr).
- Keep Vite development-only HMR/axe exceptions out of production headers. Verify the compiled
  static build through a non-root read-only nginx service, not the development server.
- Add Chromium/Firefox/WebKit positive-flow and negative CSS-injection checks. Capture unexpected
  CSP violations and runtime errors; expected attack probes are separate from positive flows.
- Repeat the local ZAP baseline without suppressing rules. Publish counts/metadata only;
  a clean limited baseline does not establish authenticated penetration-test coverage.
- Preserve the single master branch. Run local gates and exact-commit hosted CI before any
  manual demo release. Hosted CI gating/rollback remains a separate verification item.

Browser plugin not available; use the existing Docker/Linux Playwright fallback. Screenshots
and private diagnostic logs remain outside tracked source.

## Measured 2026-10-28

`make e2e-csp` passed **nine cases**, three each in Chromium, Firefox and WebKit,
against compiled static assets (43.8s standalone; final wrapper 106.265s including build,
startup and restoration). Native-select characterization, three blocked CSS payload forms,
trusted property updates and the real application flow all ran. App-origin CSP violations
and runtime errors remain fatal. Desktop/mobile light/dark captures use synthetic data.

WebKit emits a style-src-attr report for an unstyled native `document.createElement('select')`.
An independent div/select probe reproduced it. Tests observe construction without changing
arguments, results or styles, accept only its bootstrap-origin reports, and require exact
report/constructor counts. All application-source violations and attack probes remain checked.
Playwright's WebKit screenshot preparation injects a style tag, so positive-flow screenshots
are limited to Chromium/Firefox; WebKit functional and negative checks still run. These are
explicit harness/browser limits, not permission to weaken production headers.

The repeated local ZAP baseline has **zero high, medium and low findings**; remaining
informational types are modern-web-app, authentication and session discovery. ZAP's underlying
exit 2 is retained in private reports. This supersedes the October26 inline-style finding;
it does not establish an authenticated pentest or vulnerability-free claim.

Earlier attempts exposed the screenshot injection, resize timing and select reports; they were
fixed in the harness without relaxing CSP. One Docker registry DNS failure occurred before
browser execution and recovered after pulling the official Node image. Failed logs remain
ignored under var/drills; no failed attempt is counted as a pass.
