// Basic local production-build load measurement; no performance SLA.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend/package.json"));
const { chromium } = require("@playwright/test");
const server = spawn(
  process.execPath,
  [
    "node_modules/vite/bin/vite.js",
    "preview",
    "--host",
    "127.0.0.1",
    "--port",
    "4173",
    "--strictPort",
  ],
  { cwd: path.join(root, "frontend"), stdio: "ignore", windowsHide: true },
);
let browser;
try {
  let ready = false;
  for (let i = 0; i < 30; i++) {
    try {
      const result = await fetch("http://127.0.0.1:4173");
      if (result.ok) {
        ready = true;
        break;
      }
    } catch {
      /* Startup only. */
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  if (!ready)
    throw new Error("Preview did not become ready; build frontend first");
  browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const response = await page.goto("http://127.0.0.1:4173/login");
  await page.getByRole("heading", { name: "Good to see you" }).waitFor();
  for (const [name, expected] of [
    ["x-content-type-options", "nosniff"],
    ["x-frame-options", "DENY"],
    ["referrer-policy", "no-referrer"],
  ]) {
    if (response.headers()[name] !== expected)
      throw new Error("Missing web header: " + name);
  }
  if (
    !response
      .headers()
      ["content-security-policy"].includes("frame-ancestors 'none'")
  )
    throw new Error("Missing web CSP");
  const measurement = await page.evaluate(() => ({
    title: document.title,
    domContentLoadedMs: Math.round(
      performance.getEntriesByType("navigation")[0].domContentLoadedEventEnd,
    ),
    resources: performance.getEntriesByType("resource").length,
  }));
  if (errors.length) throw new Error("Production page raised an error");
  console.log(
    JSON.stringify({
      ...measurement,
      pageErrors: errors.length,
      securityHeaders: "pass",
    }),
  );
} finally {
  if (browser) await browser.close();
  server.kill();
}
