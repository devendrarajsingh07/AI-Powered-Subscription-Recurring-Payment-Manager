// Production build gate: public read-only metadata, never credentials or financial endpoints.
import { pathToFileURL } from "node:url";

export const repository =
  "devendrarajsingh07/AI-Powered-Subscription-Recurring-Payment-Manager";

export async function waitForVerifiedRelease({
  sha,
  mode = "build",
  github = "https://api.github.com",
  api,
  web,
  fetcher = fetch,
  timeoutMs = 25 * 60 * 1000,
  pollMs = 45000,
  now = Date.now,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  log = () => {},
}) {
  if (!/^[a-f0-9]{40}$/.test(sha || "") || !["build", "verify"].includes(mode))
    throw new Error("Release metadata is invalid");
  if (!(timeoutMs > 0 && timeoutMs <= 25 * 60 * 1000 && pollMs > 0))
    throw new Error("Release time limits are invalid");
  const deadline = now() + timeoutMs;
  const root = `${github}/repos/${repository}`;
  async function read(url, pending = false) {
    const remaining = deadline - now();
    if (remaining <= 0) throw new Error("Release verification timed out");
    const signal = AbortSignal.timeout(Math.min(30000, remaining));
    try {
      const response = await fetcher(url, {
        headers: {
          Accept: "application/vnd.github+json",
          "User-Agent": "subtrack-release-gate",
          "Cache-Control": "no-cache",
        },
        redirect: "error",
        signal,
      });
      if (!response.ok) {
        if (pending) return null;
        throw new Error("Release metadata request failed");
      }
      let size = 0;
      const parts = [];
      for await (const chunk of response.body) {
        size += chunk.length;
        if (size > 512000)
          throw new Error("Release metadata exceeds its limit");
        parts.push(chunk);
      }
      return JSON.parse(Buffer.concat(parts).toString("utf8"));
    } catch (error) {
      if (now() >= deadline || (signal.aborted && remaining <= 30000))
        throw new Error("Release verification timed out");
      if (pending && error.message !== "Release metadata exceeds its limit")
        return null;
      throw new Error("Release metadata unavailable or invalid");
    }
  }
  async function approvedHistory() {
    const head = await read(`${root}/commits/master`);
    if (head.sha === sha) return;
    if (mode === "verify") {
      const comparison = await read(`${root}/compare/${sha}...${head.sha}`);
      if (comparison.status === "ahead") return; // Approved older master release / rollback.
    }
    throw new Error(
      "Automatic release was superseded or is outside master history",
    );
  }
  async function wait(label, check) {
    while (now() < deadline) {
      if (await check()) return;
      log(label);
      await sleep(Math.min(pollMs, Math.max(1, deadline - now())));
    }
    throw new Error("Release verification timed out");
  }
  await approvedHistory();
  await wait("Waiting for exact-commit CI", async () => {
    const data = await read(
      `${root}/actions/workflows/ci.yml/runs?head_sha=${sha}&event=push&per_page=10`,
    );
    if (!Array.isArray(data.workflow_runs))
      throw new Error("CI metadata is invalid");
    const run = data.workflow_runs.find(
      (item) =>
        item.head_sha === sha &&
        item.head_branch === "master" &&
        item.event === "push" &&
        item.path === ".github/workflows/ci.yml" &&
        item.head_repository?.full_name === repository,
    );
    if (!run || run.status !== "completed") return false;
    if (run.conclusion !== "success")
      throw new Error("Exact-commit CI did not pass");
    return true;
  });
  await wait("Waiting for verified API revision and readiness", async () => {
    const health = await read(`${api}/api/v1/health`, true);
    if (health?.revision !== sha) return false;
    const ready = await read(`${api}/api/v1/health/ready`, true);
    return ready !== null;
  });
  if (mode === "verify") {
    await wait(
      "Waiting for verified frontend revision",
      async () => (await read(`${web}/version.json`, true))?.revision === sha,
    );
  }
  await approvedHistory(); // A newer push during CI/deploy wait must not authorize this build.
  log("Verified release gate passed");
}

export async function main(env = process.env, args = process.argv.slice(2)) {
  const verify = args.length === 1 && args[0] === "--verify";
  if (args.length && !verify) throw new Error("Unsupported release-gate mode");
  if (
    !verify &&
    (env.VERCEL !== "1" ||
      env.VERCEL_ENV !== "production" ||
      env.VERCEL_GIT_REPO_OWNER !== repository.split("/")[0] ||
      env.VERCEL_GIT_REPO_SLUG !== repository.split("/")[1] ||
      env.VERCEL_GIT_COMMIT_REF !== "master")
  )
    throw new Error("Production release context is missing or unsupported");
  const sha = verify ? env.DEPLOY_SHA : env.VERCEL_GIT_COMMIT_SHA;
  if (!/^[a-f0-9]{40}$/.test(sha || ""))
    throw new Error("Release metadata is invalid");
  let api, web;
  try {
    api = new URL(verify ? env.DEMO_API_URL : env.VITE_API_BASE_URL);
    web = verify ? new URL(env.DEMO_WEB_URL) : null;
    for (const url of [api, web].filter(Boolean)) {
      if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash)
        throw new Error();
    }
    if (!/^\/api\/v1\/?$/.test(api.pathname) || (web && web.pathname !== "/"))
      throw new Error();
  } catch {
    throw new Error("Explicit HTTPS release endpoints are missing or invalid");
  }
  await waitForVerifiedRelease({
    sha,
    api: api.origin,
    web: web?.origin,
    mode: verify ? "verify" : "build",
    log: (message) => console.log(message),
  });
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  main().catch((error) => {
    console.error(`Release blocked: ${error.message}`);
    process.exitCode = 1;
  });
}
