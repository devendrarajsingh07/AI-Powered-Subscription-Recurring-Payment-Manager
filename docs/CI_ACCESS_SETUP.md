# Free demo CI access — owner handoff

The code and local tests are complete; activation is blocked on these owner credential steps.
Do not put credential values in chat, source, screenshots, logs or VITE-prefixed variables.
No paid resources, new service accounts, live AI or real-user processing are involved.

Current receipt (2026-10-28): RENDER_DEPLOY_HOOK_URL is saved and its repository-secret name
was verified. The existing hook was transferred only after explicit owner authorization; no new
credential was generated. GITHUB_RELEASE_READ_TOKEN is not yet saved in Vercel. The owner's
one-time GitHub token tab closed; GitHub cannot retrieve that value. The owner must use a retained
copy or create a replacement themselves. Activation remains off. No secret values are in this receipt.

## 1. Render service hook → GitHub Actions

In the existing Render API Settings → Deploy Hook, use Copy on its masked field. Save the value
in this repository → Settings → Secrets and variables → Actions → Repository secrets, named
**RENDER_DEPLOY_HOOK_URL**. This gives the guarded workflow permission to redeploy this one
existing free service. Do not generate a global Render API key or rotate the hook unnecessarily.

## 2. GitHub read credential → Vercel Production

Owner creates a fine-grained token on the existing GitHub account, expiry30days, Only select
repositories → SubTrack repository. Repository permissions: **Actions: Read-only** and
**Contents: Read-only**; metadata read is implicit. No write/account/email permissions.
Follow [GitHub's token instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

Save it as a **Production Secret** on the existing Vercel project, named
**GITHUB_RELEASE_READ_TOKEN**. It is used by the server-side build to read commit/CI metadata,
never financial data. CI verification uses its built-in ephemeral read-only token instead.
A literal credential scan runs on compiled assets; tests prove token scoping and error redaction.
This complements trusted build code; it is not proof against every possible encoded exfiltration.
Renew/revoke the token before expiry; expiration fails the build closed and preserves the old UI.

## Activation after owner confirmation

- Set repository variables DEPLOY_STRATEGY=api-hook and DEPLOY_ENABLED=true.
- Set Render native Auto-Deploy Off so there is one API release controller. A specific-ref hook
  also disables native deploys. Keep all source/build/runtime settings and free plan unchanged.
- Push the verified code on master. All4 hosted CI jobs must pass before the workflow can use
  the hook. It checks exact push CI, repository/master/current SHA before checkout/deployment
  credentials. Superseded automatic jobs skip; API-hook manual releases require current head.
- The hook releases exact SHA, waits for matching health revision and readiness; no Vercel
  deployment credential or promotion API is used. The existing Vercel Git integration builds
  only after its exact-CI/API gate passes. Its read token goes only to repository metadata URLs.
- Automatic post-deploy verification checks paired source versions and24 read-only smoke checks.
  Record actual hosted success before marking this implemented setup as Done.

Rollback uses the tested same-schema provider-artifact procedure in RUNBOOK.md. To contain CI
access, disable DEPLOY_ENABLED, remove the Actions hook secret, and revoke/remove the Vercel
read token. Owner rotates the Render hook if exposure is suspected; never paste its value here.
