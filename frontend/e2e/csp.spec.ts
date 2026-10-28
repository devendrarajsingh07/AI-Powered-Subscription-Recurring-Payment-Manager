import { test, expect, type Page } from "@playwright/test";
import { observeAuth, observedToken } from "./auth";
import { formatMoney } from "../src/lib/money";
import type { components } from "../src/api/schema";

type CspWindow = Window & {
  cspViolations: string[];
  nativeSelectCount: number;
  nativeSelectReports: number;
};

test.beforeEach(async ({ page }) => {
  test.skip(
    process.env.E2E_PRODUCTION_CSP !== "1",
    "Requires compiled static CSP profile",
  );
  // Observe native construction without changing its arguments/result/styles. WebKit emits
  // an attr report even for document.createElement('select') with no attributes or insertion.
  // WebKit attributes this observed constructor call to Playwright's bootstrap, while app
  // writes retain their asset source. The negative probes below must still report all payloads.
  await page.addInitScript({
    content: `
    window.cspViolations = [];
    window.nativeSelectCount = 0;
    window.nativeSelectReports = 0;
    const nativeCreate = Document.prototype.createElement;
    Document.prototype.createElement = function(...args) {
      if (String(args[0]).toLowerCase() === 'select') window.nativeSelectCount++;
      return Reflect.apply(nativeCreate, this, args);
    };
    document.addEventListener('securitypolicyviolation', event => {
      if (event.effectiveDirective === 'style-src-attr' &&
          event.sourceFile === 'web-inspector://bootstrap.js') {
        window.nativeSelectReports++;
      } else {
        window.cspViolations.push(event.effectiveDirective);
      }
    });
  `,
  });
});

test("native-select CSP reporting is characterized separately from application CSS", async ({
  page,
  browserName,
}) => {
  await page.goto("/login");
  await page.evaluate(() => {
    document.createElement("div");
    document.createElement("select");
    document.createElement("select");
  });
  await expect
    .poll(() => page.evaluate(() => (window as CspWindow).nativeSelectReports))
    .toBe(browserName === "webkit" ? 2 : 0);
  expect(
    await page.evaluate(() => (window as CspWindow).nativeSelectCount),
  ).toBe(2);
  expect(
    await page.evaluate(() => (window as CspWindow).cspViolations),
  ).toEqual([]);
});

test("production CSP blocks inline CSS payloads while allowing trusted property updates", async ({
  page,
}) => {
  const response = await page.goto("/login");
  const policy = response!.headers()["content-security-policy"];
  expect(policy).not.toContain("'unsafe-inline'");
  for (const directive of [
    "style-src 'self'",
    "style-src-elem 'self'",
    "style-src-attr 'none'",
    "script-src 'self'",
  ])
    expect(policy.split(";").map((part) => part.trim())).toContain(directive);
  await expect(
    page.getByRole("heading", { name: "Good to see you" }),
  ).toBeVisible();
  const results = await page.evaluate(() => {
    const target = document.createElement("div");
    target.id = "csp-style-probe";
    target.style.color = "rgb(1, 2, 3)";
    document.body.append(target);
    const trusted = getComputedStyle(target).color;
    target.setAttribute("style", "color: rgb(4, 5, 6)");
    const attribute = getComputedStyle(target).color;
    const stylesheet = document.createElement("style");
    stylesheet.textContent =
      "#csp-style-probe { color: rgb(7, 8, 9) !important }";
    document.head.append(stylesheet);
    const element = getComputedStyle(target).color;
    const markup = document.createElement("div");
    markup.innerHTML =
      '<span style="color: rgb(10, 11, 12)">synthetic CSS probe</span>';
    document.body.append(markup);
    const inline = getComputedStyle(markup.firstElementChild!).color;
    stylesheet.remove();
    target.remove();
    markup.remove();
    return { trusted, attribute, element, inline };
  });
  expect(results.trusted).toBe("rgb(1, 2, 3)");
  expect(results.attribute).not.toBe("rgb(4, 5, 6)");
  expect(results.element).not.toBe("rgb(7, 8, 9)");
  expect(results.inline).not.toBe("rgb(10, 11, 12)");
  await expect
    .poll(() => page.evaluate(() => (window as CspWindow).cspViolations.length))
    .toBe(3);
  expect(
    await page.evaluate(() => (window as CspWindow).cspViolations.sort()),
  ).toEqual(["style-src-attr", "style-src-attr", "style-src-elem"]);
});

async function register(page: Page) {
  observeAuth(page);
  await page.goto("/register");
  await page
    .getByLabel("Email address")
    .fill(`csp-${crypto.randomUUID()}@example.org`);
  await page.getByLabel("Password", { exact: true }).fill("SyntheticDemo42!");
  for (let attempt = 0; attempt < 2; attempt++) {
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/auth/register") &&
        r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Create account" }).click();
    const response = await pending;
    if (response.status() !== 429) {
      expect(response.ok()).toBe(true);
      return;
    }
    const seconds = Number(response.headers()["retry-after"]);
    expect(Number.isInteger(seconds) && seconds > 0 && seconds <= 60).toBe(
      true,
    );
    await page.waitForTimeout(seconds * 1000 + 100);
  }
  throw new Error(
    "Synthetic registration remained throttled after server-directed backoff",
  );
}

test("compiled UI charts, tooltips, dialogs and themes work without application CSP violations", async ({
  page,
  browserName,
}, info) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const consoleErrors: string[] = [];
  let registered = false;
  let nativeConsoleReports = 0;
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      // WebKit's native constructor also prints this generic message. Its exact count must
      // match the independently observed constructor reports; app CSP violations remain fatal.
      if (
        browserName === "webkit" &&
        message.text() ===
          "Refused to apply a stylesheet because its hash, its nonce, or 'unsafe-inline' does not appear in the style-src directive of the Content Security Policy."
      ) {
        nativeConsoleReports++;
        return;
      }
      // Registration's explicitly handled 429/backoff is validated by the helper; collect
      // all other runtime errors for the entire turn and UI console errors after registration.
      if (registered) consoleErrors.push(message.text());
    }
  });
  await register(page);
  registered = true;
  expect(
    await page.evaluate(() => (window as CspWindow).cspViolations),
  ).toEqual([]);
  const token = await observedToken(page);
  const auth = { Authorization: `Bearer ${token}` };
  try {
    await page
      .getByRole("button", { name: "Load demo data", exact: true })
      .first()
      .click();
    await expect(
      page.getByRole("heading", { name: "Statement processed" }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: /dashboard/i })
      .first()
      .click();
    await expect(page).toHaveURL((url) => url.pathname === "/");
    await expect(page).toHaveTitle("Overview · SubTrack");
    const response = await page.request.get("/api/v1/summary", {
      headers: auth,
    });
    expect(response.ok()).toBe(true);
    const summary = (await response.json()) as components["schemas"]["Summary"];
    await expect(page.getByTestId("monthly-total")).toHaveText(
      formatMoney(summary.monthly_equivalent),
    );
    await expect(page.locator(".recharts-pie-sector").first()).toBeVisible();
    await expect(page.locator(".recharts-area-curve").first()).toBeVisible();
    await page.locator(".recharts-sector").first().hover();
    await expect(
      page.locator(".chart-tooltip").filter({ visible: true }).first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Show data tables" }).click();
    await expect(page.getByRole("table").first()).toBeVisible();
    await page.getByRole("button", { name: "Show charts" }).click();
    for (const theme of ["light", "dark"]) {
      await page.getByLabel("Theme preference").selectOption(theme);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      for (const width of [360, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        await expect
          .poll(() =>
            page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
          )
          .toBe(true);
        // Playwright's WebKit screenshot preparation injects a style tag (body {}), which the
        // policy correctly blocks. Keep WebKit's zero-violation functional check untouched;
        // collect visual evidence in Chromium/Firefox without injecting screenshot CSS.
        if (browserName !== "webkit") {
          const screenshot = await page.screenshot({
            caret: "initial",
            animations: "allow",
          });
          await info.attach(`production-csp-${theme}-${width}`, {
            body: screenshot,
            contentType: "image/png",
          });
        }
      }
    }
    await page.setViewportSize({ width: 1280, height: 900 });
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Subscriptions", exact: true })
      .click();
    await page
      .getByRole("button", { name: /^Review / })
      .first()
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Ask SubTrack" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    for (const [route, name] of [
      ["/upload", "Upload statement"],
      ["/renewals", "Renewals"],
      ["/recommendations", "Recommendations"],
      ["/categories", "Categories"],
      ["/settings", "Settings"],
      ["/", "Overview"],
    ]) {
      await page
        .getByRole("navigation", { name: "Main navigation" })
        .getByRole("link", { name, exact: true })
        .click();
      await expect(page).toHaveURL((url) => url.pathname === route);
      await expect(page).toHaveTitle(`${name} · SubTrack`);
      await expect(page.locator("main h1")).toBeVisible();
    }
    await expect
      .poll(() => page.evaluate(() => (window as CspWindow).cspViolations))
      .toEqual([]);
    const nativeCount = await page.evaluate(
      () => (window as CspWindow).nativeSelectCount,
    );
    expect(nativeCount).toBeGreaterThan(0);
    await expect
      .poll(() =>
        page.evaluate(() => (window as CspWindow).nativeSelectReports),
      )
      .toBe(browserName === "webkit" ? nativeCount : 0);
    expect(nativeConsoleReports).toBe(
      browserName === "webkit" ? nativeCount : 0,
    );
    expect(errors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  } finally {
    const deleted = await page.request.delete("/api/v1/me/data", {
      headers: auth,
    });
    expect(deleted.ok()).toBe(true);
  }
});
