# Remaining Phase 8 account security — implementation decisions

2026-10-20. Keep bcrypt and the existing strength policy, with an offline common-password check.
Email verification is enforced before login and every authenticated business operation when enabled;
the gate rejects existing unverified bearer sessions before upload ingestion. Default off only for
development. Existing
accounts remain unverified until explicitly verified. Production requires verification and remains
blocked by the independent launch gate while other requirements are unfinished.

Opaque email codes are single-use, HMAC-hashed, expiring and entered in a form. They never appear in
URLs or application logs. Mail uses the existing Notifier after the token transaction commits, in a
bounded background call. Delivery failures record a safe event; users request a new code to retry.
Only email receives the raw code; no persistent plaintext mail queue is introduced. Console delivery
is a development fallback, not evidence of real inbox delivery or provider bounce handling.

Access JWTs bind an account version and a revocable session UUID. Every authenticated request checks
both. Refresh tokens rotate atomically under the account/session locks, with used digests retained
until expiry for reuse detection. Reuse revokes the entire family, including its access JWTs. Reset
and logout-everywhere revoke all families and increment the account version. Authentication rows
cascade with account deletion and are excluded from export.

Refresh cookies are host-only, HttpOnly, SameSite=Strict; Secure for HTTPS or non-development.
Cookie refresh requires exact Origin and a server-derived CSRF header. Bootstrap retrieves the CSRF
value only after exact-Origin validation; business APIs continue to require bearer authorization.
An anonymous/expired bootstrap returns a normal null result, not a spurious console401. A distinct
shared session-endpoint rate bucket avoids consuming login attempts on page reload. Cookie logout
uses the same Origin/CSRF proof to revoke a family even after the access JWT expires; bearer
logout remains available for the synthetic demo. Logout-everywhere requires current access.
Access tokens move to memory, never localStorage/sessionStorage. Cookies across the free Vercel and
Render domains are cross-site: deployed `AUTH_SESSION_MODE=demo` issues no refresh cookie, only a
short-lived revocable bearer session; reloading requires starting a new isolated disposable session.
This mode requires `PUBLIC_DEMO_ONLY=true`, offline fake AI, console delivery, synthetic loader and
disabled file uploads/password registration/login. It cannot activate in production. Production
requires explicit HTTPS sibling origins and `AUTH_COOKIE_SITE`; the independent launch block remains.
Do not relax SameSite to hide that limitation; sibling custom domains remain a beta prerequisite.

Local TLS stand-in: `python scripts/prepare_auth_tls.py`, then
`docker compose -f docker-compose.yml -f docker-compose.auth-test.yml up --build --wait`.
The test-only Nginx proxy uses ignored two-day self-signed fixtures and Docker DNS aliases for
app/api.subtrack.test. Playwright accepts that local fixture certificate ONLY when explicitly
configured with E2E_LOCAL_TLS=1 and E2E_BASE_URL=https://app.subtrack.test:8443. No system CA is
installed; no deployed cookie, CSRF or certificate validation setting changes. This tests browser
same-site behavior, not public DNS or a trusted production certificate. Restore normal local mode
with `docker compose up -d --wait api web` after the drill.

Account-level exponential backoff uses HMAC email keys in PostgreSQL for known and unknown addresses,
in addition to the shared peer-address limiter. No email/IP/password enters audit metadata. Optional
TOTP and production email/provider/domain verification remain separate launch gates.

WP3 verification in progress2026-10-21: full PostgreSQL suite394 passed (293.08s), frontend65 passed
before the page-title regression test was added. Further gates, TLS browser flow and hosted CI must
pass before publication; these intermediate counts are not a completion claim. SMTP account-mail
delivery is exercised against an actual local aiosmtpd server, not a mocked happy path. Real inbox,
SPF/DKIM/DMARC and public-domain verification remain owner-blocked.

Sources checked: [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
