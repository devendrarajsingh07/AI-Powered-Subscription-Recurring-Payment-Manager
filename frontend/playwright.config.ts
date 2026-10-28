import { defineConfig, devices } from "@playwright/test";
const tls = process.env.E2E_LOCAL_TLS === "1";
if (
  tls &&
  !/^https:\/\/app\.subtrack\.test:8443\/?$/.test(
    process.env.E2E_BASE_URL || "",
  )
)
  throw new Error(
    "Local TLS fixtures are restricted to app.subtrack.test:8443",
  );
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    ignoreHTTPSErrors: tls, // Disposable test certificate only; never a product/browser setting.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    {
      name: "firefox",
      testMatch:
        process.env.E2E_PRODUCTION_CSP === "1"
          ? "**/csp.spec.ts"
          : "**/main.spec.ts",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      testMatch:
        process.env.E2E_PRODUCTION_CSP === "1"
          ? "**/csp.spec.ts"
          : "**/main.spec.ts",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
