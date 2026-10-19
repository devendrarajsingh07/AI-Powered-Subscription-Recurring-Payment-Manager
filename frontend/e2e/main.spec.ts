import { capture } from "./evidence";
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import type { components } from "../src/api/schema";
import { formatMoney } from "../src/lib/money";
const data = path.resolve("../backend/data");
const screenshots = path.resolve("../docs/screenshots");
fs.mkdirSync(screenshots, { recursive: true });
const password = "SyntheticDemo42!";
async function accessibility(page: Page) {
  await page.addScriptTag({
    path: path.resolve("node_modules/axe-core/axe.min.js"),
  });
  const violations = await page.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run: (node: Document) => Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    return (await axe.run(document)).violations.map((value) => ({
      id: value.id,
      targets: value.nodes.map((node) => node.target),
    }));
  });
  expect(violations).toEqual([]);
}
async function register(page: Page) {
  const email = `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.org`;
  await page.goto("/register");
  await accessibility(page);
  await capture(page, {
    path: path.join(screenshots, "auth.png"),
    fullPage: true,
  });
  await expect(page).toHaveTitle(/SubTrack/);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
  return email;
}
async function upload(page: Page, filename: string) {
  await page
    .getByRole("link", { name: "Upload statement", exact: true })
    .first()
    .click();
  await page
    .getByLabel("Choose CSV file")
    .setInputFiles(path.join(data, filename));
  await expect(
    page.getByRole("heading", { name: "Check your column mapping" }),
  ).toBeVisible();
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/uploads") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm and import" }).click();
  const started = (await (
    await response
  ).json()) as components["schemas"]["UploadOut"];
  expect(started.status).toBe("pending");
  expect(started.stage).toBe("queued");
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
  return started;
}
async function authed(page: Page, endpoint: string) {
  const token = await page.evaluate(
    () =>
      JSON.parse(sessionStorage.getItem("subtrack.session")!).token as string,
  );
  const result = await page.request.get(`/api/v1${endpoint}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(result.ok()).toBeTruthy();
  return result;
}
async function deleteAccount(page: Page) {
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Delete my data", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const confirm = dialog.getByRole("button", {
    name: "Permanently delete data",
  });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("Confirmation word").fill("DELETE");
  await confirm.click();
  await expect(
    page.getByText("Your account and data were deleted.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Deleted data counts")).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("subtrack.session")),
  ).toBeNull();
}
test("real stack: register, login, import 16 products, review, budget and delete", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const email = await register(page);
  await capture(page, {
    path: path.join(screenshots, "overview-empty.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Log out" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Upload statement", exact: true })
    .first()
    .click();
  await page
    .getByLabel("Choose CSV file")
    .setInputFiles(path.join(data, "sample_transactions.csv"));
  await expect(
    page.getByRole("heading", { name: "Check your column mapping" }),
  ).toBeVisible();
  await capture(page, {
    path: path.join(screenshots, "upload-mapping.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Confirm and import" }).click();
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
  await expect(
    page.getByText("Inserted", { exact: true }).locator(".."),
  ).toContainText("399");
  await expect(
    page.getByText("Detected products", { exact: true }).locator(".."),
  ).toContainText("16");
  await page
    .getByRole("link", { name: "View subscriptions", exact: true })
    .click();
  const truth = JSON.parse(
    fs.readFileSync(path.join(data, "ground_truth.json"), "utf8"),
  ) as {
    patterns: { merchant: string; cadence: string; avg_amount: string }[];
  };
  const subscriptions = (await (
    await authed(page, "/subscriptions?limit=100")
  ).json()) as components["schemas"]["Page_SubscriptionOut_"];
  expect(subscriptions.total).toBe(16);
  await expect(page.getByRole("button", { name: /^Review / })).toHaveCount(16);
  expect(
    subscriptions.items
      .map((item) => `${item.merchant}|${item.cadence}|${item.avg_amount}`)
      .sort(),
  ).toEqual(
    truth.patterns
      .map((item) => `${item.merchant}|${item.cadence}|${item.avg_amount}`)
      .sort(),
  );
  for (const product of truth.patterns)
    await expect(
      page
        .getByRole("button", {
          name: `Review ${product.merchant}`,
          exact: true,
        })
        .first(),
    ).toBeVisible();
  await capture(page, {
    path: path.join(screenshots, "subscriptions.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Review spotify", exact: true })
    .click();
  const drawer = page.getByRole("dialog");
  await expect(
    drawer.getByRole("heading", { name: "Underlying charges" }),
  ).toBeVisible();
  await expect(
    drawer.getByRole("button", { name: "Close dialog" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(drawer).toContainText("linked charges");
  expect(
    await page.evaluate(() =>
      document.querySelector("dialog")!.contains(document.activeElement),
    ),
  ).toBe(true);
  await drawer.getByRole("button", { name: "Confirm detection" }).click();
  await expect(
    drawer.getByRole("button", { name: "Confirm detection" }),
  ).toBeDisabled();
  await drawer.getByLabel("Change category").selectOption("software");
  await drawer
    .getByRole("button", { name: "Save category", exact: true })
    .click();
  await expect(
    drawer.getByRole("status").filter({ hasText: "Changes saved." }),
  ).toBeVisible();
  await capture(page, {
    path: path.join(screenshots, "charge-drawer.png"),
    fullPage: false,
  });
  await accessibility(page);
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review spotify", exact: true }),
  ).toBeFocused();
  await page.reload();
  const spotify = page.getByRole("row").filter({
    has: page.getByRole("button", { name: "Review spotify", exact: true }),
  });
  await expect(spotify).toContainText("Software");
  await expect(spotify).toContainText("Confirmed");
  await page.getByLabel("Sort by").selectOption("avg_amount");
  await page
    .getByRole("combobox", { name: "Direction", exact: true })
    .selectOption("desc");
  await expect(page).toHaveURL(/direction=desc/);
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  const summary = (await (
    await authed(page, "/summary")
  ).json()) as components["schemas"]["Summary"];
  await expect(page.getByTestId("monthly-total")).toHaveText(
    formatMoney(summary.monthly_equivalent),
  );
  await expect(page.getByTestId("yearly-total")).toHaveText(
    formatMoney(summary.yearly_total),
  );
  await page.getByRole("button", { name: "Show data tables" }).click();
  const trend = (await (
    await authed(page, "/summary/trend?months=12")
  ).json()) as components["schemas"]["Trend"];
  for (const point of trend.months)
    await expect(
      page.getByRole("row").filter({
        has: page.getByRole("rowheader", { name: point.month, exact: true }),
      }),
    ).toContainText(formatMoney(point.total));
  await page.getByRole("button", { name: "Show charts" }).click();
  await capture(page, {
    path: path.join(screenshots, "dashboard-desktop.png"),
    fullPage: true,
  });
  await accessibility(page);
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await capture(page, {
    path: path.join(screenshots, "dashboard-dark.png"),
    fullPage: true,
  });
  await accessibility(page);
  await page.getByRole("button", { name: "Use light theme" }).click();
  await page.setViewportSize({ width: 360, height: 800 });
  await capture(page, {
    path: path.join(screenshots, "dashboard-mobile.png"),
    fullPage: true,
  });
  await accessibility(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("Monthly limit (₹)").fill("2000.01");
  await page.getByRole("button", { name: "Save budget", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Budget saved: ₹2,000.01." }),
  ).toBeVisible();
  const budget = (await (
    await authed(page, "/budget")
  ).json()) as components["schemas"]["BudgetOut"];
  expect(budget.monthly_limit).toBe("2000.01");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await capture(page, {
    path: path.join(screenshots, "settings.png"),
    fullPage: true,
  });
  await page.goto("/renewals");
  await expect(
    page.getByRole("heading", { name: "Renewals, on your radar" }),
  ).toBeVisible();
  await expect(page.getByText(/expected renewals/)).toBeVisible();
  await capture(page, {
    path: path.join(screenshots, "renewals.png"),
    fullPage: true,
  });
  await page.goto("/categories");
  await expect(
    page.getByRole("heading", { name: "A little context helps" }),
  ).toBeVisible();
  await expect(page.locator(".panel .loading")).toHaveCount(0);
  await capture(page, {
    path: path.join(screenshots, "categories.png"),
    fullPage: true,
  });
  await deleteAccount(page);
  expect(errors).toEqual([]);
});
test("handwritten bank export uses editable mapping and reports malformed rows", async ({
  page,
}) => {
  await register(page);
  await page
    .getByRole("link", { name: "Upload statement", exact: true })
    .first()
    .click();
  await page
    .getByLabel("Choose CSV file")
    .setInputFiles(path.join(data, "handwritten_bank.csv"));
  await expect(page.getByLabel("Amount layout")).toHaveValue("split");
  await page.getByLabel("Map debit").selectOption("Withdrawal Amt.");
  await page.getByLabel("Map credit").selectOption("Deposit Amt.");
  await page.getByRole("button", { name: "Confirm and import" }).click();
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
  await expect(
    page.getByText("Detected products", { exact: true }).locator(".."),
  ).toContainText("3");
  await expect(
    page.getByText("Malformed rows", { exact: true }).locator(".."),
  ).toContainText("3");
  await deleteAccount(page);
});
test("malformed CSV shows a safe server error and supports retry", async ({
  page,
}) => {
  await register(page);
  await page
    .getByRole("link", { name: "Upload statement", exact: true })
    .first()
    .click();
  await page.getByLabel("Choose CSV file").setInputFiles({
    name: "empty.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(""),
  });
  await expect(page.getByRole("alert")).toContainText("CSV is empty");
  await expect(
    page.getByRole("button", { name: "Confirm and import" }),
  ).not.toBeVisible();
  await upload(page, "handwritten_bank.csv");
  await deleteAccount(page);
});
