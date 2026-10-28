import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { main, repository, waitForVerifiedRelease } from "./deploy-gate.mjs";

const sha = "a".repeat(40),
  other = "b".repeat(40);
const validRun = {
  head_sha: sha,
  head_branch: "master",
  event: "push",
  path: ".github/workflows/ci.yml",
  head_repository: { full_name: repository },
  status: "completed",
  conclusion: "success",
};

async function fixture(t, changes = {}) {
  const requests = [];
  const state = { heads: 0, checks: 0, health: 0, ready: 0, ...changes };
  const server = createServer((request, response) => {
    requests.push({
      url: request.url,
      method: request.method,
      auth: request.headers.authorization,
    });
    let body,
      status = 200;
    if (request.url.endsWith("/commits/master")) {
      state.heads++;
      body = { sha: state.head?.(state.heads) || sha };
    }
    else if (request.url.includes("/compare/"))
      body = { status: state.relation || "ahead" };
    else if (request.url.includes("/ci.yml/runs?")) {
      state.checks++;
      body = state.runs?.(state.checks) || {
        workflow_runs: [{ ...validRun, ...state.run }],
      };
      status = state.ciStatus || 200;
    } else if (request.url === "/api/v1/health") {
      state.health++;
      body = { revision: state.apiSha || sha };
    } else if (request.url === "/api/v1/health/ready") {
      state.ready++;
      status = state.readyStatus?.(state.ready) || 200;
      body = { status: "ready" };
    } else if (request.url === "/web/version.json")
      body = { revision: state.webSha || sha };
    else {
      status = 404;
      body = {};
    }
    response.writeHead(status, { "Content-Type": "application/json" });
    response.end(
      state.malformed && request.url.includes("/ci.yml/runs?")
        ? "not json"
        : JSON.stringify(body),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(
    () =>
      new Promise((resolve) => {
        server.closeAllConnections();
        server.close(resolve);
      }),
  );
  const origin = `http://127.0.0.1:${server.address().port}`;
  return {
    state,
    requests,
    options: {
      sha,
      github: origin + "/github",
      api: origin,
      web: origin + "/web",
      timeoutMs: 1500,
      pollMs: 2,
    },
  };
}

test("real HTTP gate checks exact CI, API readiness and head again using read-only requests", async (t) => {
  const f = await fixture(t);
  await waitForVerifiedRelease(f.options);
  assert.equal(f.state.heads, 2);
  assert.equal(f.state.ready, 1);
  assert.ok(
    f.requests.every((r) => r.method === "GET" && r.auth === undefined),
  );
  assert.ok(
    f.requests.every((r) =>
      /commits\/master|ci\.yml\/runs|\/health/.test(r.url),
    ),
  );
});

test("pending CI and API deploy are retried before approval", async (t) => {
  const f = await fixture(t, {
    runs: (n) => ({
      workflow_runs: [
        { ...validRun, status: n === 1 ? "in_progress" : "completed" },
      ],
    }),
    readyStatus: (n) => (n === 1 ? 503 : 200),
  });
  await waitForVerifiedRelease(f.options);
  assert.equal(f.state.checks, 2);
  assert.equal(f.state.ready, 2);
});

for (const [name, changes, reason] of [
  ["failed CI", { run: { conclusion: "failure" } }, /CI did not pass/],
  [
    "foreign repository",
    { run: { head_repository: { full_name: "somebody/else" } } },
    /timed out/,
  ],
  ["wrong branch", { run: { head_branch: "other" } }, /timed out/],
  ["pull request run", { run: { event: "pull_request" } }, /timed out/],
  [
    "wrong workflow",
    { run: { path: ".github/workflows/not-checks.yml" } },
    /timed out/,
  ],
  ["wrong commit", { run: { head_sha: other } }, /timed out/],
  ["anonymous API rate limit", { ciStatus: 403 }, /metadata unavailable/],
  ["malformed metadata", { malformed: true }, /metadata unavailable/],
  [
    "oversize metadata",
    { runs: () => ({ padding: "x".repeat(512001) }) },
    /metadata unavailable/,
  ],
]) {
  test(`fail closed: ${name}`, async (t) => {
    const f = await fixture(t, changes);
    await assert.rejects(
      waitForVerifiedRelease({ ...f.options, timeoutMs: 150 }),
      reason,
    );
    assert.equal(f.state.health, 0);
  });
}

test("healthy old API cannot approve a new release", async (t) => {
  const f = await fixture(t, { apiSha: other });
  await assert.rejects(
    waitForVerifiedRelease({ ...f.options, timeoutMs: 150 }),
    /timed out/,
  );
  assert.equal(f.state.ready, 0);
});
test("automatic build cannot approve a commit superseded during its wait", async (t) => {
  const f = await fixture(t, { head: (n) => (n === 1 ? sha : other) });
  await assert.rejects(waitForVerifiedRelease(f.options), /superseded/);
});
test("post-deploy verification requires frontend revision as well", async (t) => {
  const f = await fixture(t, { webSha: other });
  await assert.rejects(
    waitForVerifiedRelease({ ...f.options, mode: "verify", timeoutMs: 150 }),
    /timed out/,
  );
});
test("verified rollback may use only an approved master ancestor", async (t) => {
  const f = await fixture(t, { head: () => other });
  await waitForVerifiedRelease({ ...f.options, mode: "verify" });
  assert.ok(f.requests.some((r) => r.url.includes("/compare/")));
  f.state.relation = "diverged";
  await assert.rejects(
    waitForVerifiedRelease({ ...f.options, mode: "verify" }),
    /outside master/,
  );
});
test("missing production context or invalid SHA fails before any transport", async () => {
  await assert.rejects(main({}, []), /context is missing/);
  await assert.rejects(main({}, ["--verify"]), /metadata is invalid/);
  await assert.rejects(
    waitForVerifiedRelease({
      sha: "main",
      fetcher: () => assert.fail("transport"),
    }),
    /metadata is invalid/,
  );
});
test("Vercel cannot build production without running the gate first", async () => {
  const config = JSON.parse(
    await readFile(new URL("../vercel.json", import.meta.url), "utf8"),
  );
  assert.equal(
    config.buildCommand,
    "node scripts/deploy-gate.mjs && npm run build",
  );
});

test("release endpoints must be explicit HTTPS origins with the API path", async () => {
  for (const [api, web] of [
    [undefined, undefined],
    ["http://api.example.test/api/v1", "https://app.example.test"],
    ["https://api.example.test/wrong", "https://app.example.test"],
    ["https://user:secret@api.example.test/api/v1", "https://app.example.test"],
    ["https://api.example.test/api/v1?secret=value", "https://app.example.test"],
    ["https://api.example.test/api/v1", "https://app.example.test/wrong"],
  ]) {
    await assert.rejects(
      main({ DEPLOY_SHA: sha, DEMO_API_URL: api, DEMO_WEB_URL: web }, ["--verify"]),
      /endpoints are missing or invalid/,
    );
  }
});

test("read credential goes only to repository metadata, never API or web", async (t) => {
  const f = await fixture(t);
  await waitForVerifiedRelease({ ...f.options, mode: "verify", token: "synthetic-read-token" });
  const metadata = f.requests.filter((request) => request.url.startsWith("/github/"));
  const services = f.requests.filter((request) => !request.url.startsWith("/github/"));
  assert.ok(metadata.length > 0 && services.length > 0);
  assert.ok(metadata.every((request) => request.auth === "Bearer synthetic-read-token"));
  assert.ok(services.every((request) => request.auth === undefined));
});

test("metadata errors never expose the read credential or provider response", async (t) => {
  const token = "synthetic-private-read-token";
  const f = await fixture(t, { ciStatus: 403, runs: () => ({ error: token }) });
  await assert.rejects(
    waitForVerifiedRelease({ ...f.options, token }),
    (error) => /metadata unavailable/.test(error.message) && !error.message.includes(token),
  );
  assert.equal(f.state.health, 0);
});

test("compiled artifact check blocks a credential leak without printing the value", async (t) => {
  const prefix = join(resolve(tmpdir()), "subtrack-bundle-test-");
  const directory = await mkdtemp(prefix);
  t.after(async () => {
    if (!resolve(directory).startsWith(prefix)) throw new Error("Unsafe test cleanup path");
    await rm(directory, { recursive: true, force: true });
  });
  await mkdir(join(directory, "dist"));
  const credential = "synthetic-build-only-credential";
  const asset = join(directory, "dist", "asset.js");
  const script = fileURLToPath(new URL("check-build-secret.mjs", import.meta.url));
  const run = () => spawnSync(process.execPath, [script], {
    cwd: directory,
    env: { ...process.env, GITHUB_RELEASE_READ_TOKEN: credential },
    encoding: "utf8",
  });
  await writeFile(asset, `const exposed = "${credential}";`);
  const blocked = run();
  assert.equal(blocked.status, 1);
  assert.ok(!(blocked.stdout + blocked.stderr).includes(credential));
  await writeFile(asset, "const safe = true;");
  const clean = run();
  assert.equal(clean.status, 0);
  assert.ok(clean.stdout.includes("PASS"));
});
