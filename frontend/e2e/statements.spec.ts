import { observeAuth, observedToken } from "./auth";
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import type { components } from "../src/api/schema";
import { formatMoney } from "../src/lib/money";
import { capture } from "./evidence";

const fixtures = path.resolve("../backend/data/extraction");
type GoldenRow = {
  date: string;
  description: string;
  amount: string;
  type: string;
};
const corpus = JSON.parse(
  fs.readFileSync(path.join(fixtures, "manifest.json"), "utf8"),
) as {
  variants: { file: string; rows: GoldenRow[] }[];
};
async function headers(page: Page) {
  return {
    Authorization: `Bearer ${await observedToken(page)}`,
  };
}
async function read<T>(page: Page, route: string) {
  const response = await page.request.get("/api/v1" + route, {
    headers: await headers(page),
  });
  expect(response.ok()).toBe(true);
  return response.json() as Promise<T>;
}
async function register(page: Page) {
  test.setTimeout(180_000);
  await page.goto("/register");
  await page
    .getByLabel("Email address")
    .fill(
      `statement-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.org`,
    );
  await page.getByLabel("Password", { exact: true }).fill("SyntheticDemo42!");
  async function submit() {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/auth/register") &&
        r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Create account" }).click();
    return response;
  }
  let response = await submit();
  if (response.status() === 429) {
    const delay = Number(response.headers()["retry-after"]);
    expect(Number.isInteger(delay) && delay > 0 && delay <= 60).toBe(true);
    await expect(page.getByRole("alert")).toContainText("try again shortly");
    await page.waitForTimeout(delay * 1000 + 100);
    response = await submit();
  }
  expect(response.status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
}
async function choose(page: Page, name: string) {
  await page.goto("/upload");
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/uploads/preview") &&
      r.request().method() === "POST",
  );
  await page
    .getByLabel("Choose statement file")
    .setInputFiles(path.join(fixtures, name));
  const started = await response;
  expect(started.status()).toBe(202);
  const job =
    (await started.json()) as components["schemas"]["StatementPreviewOut"];
  expect(job.status).toBe("pending");
  return job;
}
async function review(page: Page) {
  await expect(
    page.getByRole("heading", { name: "Review every extracted row" }),
  ).toBeVisible({ timeout: 45_000 });
  await expect(
    page.getByRole("button", { name: "Import reviewed rows" }),
  ).toBeDisabled();
}
async function importReviewed(page: Page) {
  await page
    .getByRole("button", { name: "I reviewed every extracted row" })
    .click();
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/uploads") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Import reviewed rows" }).click();
  const result = await response;
  expect(result.status()).toBe(202);
  const job = (await result.json()) as components["schemas"]["UploadOut"];
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible({ timeout: 30_000 });
  return read<components["schemas"]["UploadOut"]>(page, "/uploads/" + job.id);
}
async function audit(page: Page) {
  await page.addScriptTag({
    path: path.resolve("node_modules/axe-core/axe.min.js"),
  });
  const violations = await page.evaluate(async () =>
    (
      await (
        window as unknown as {
          axe: {
            run: (document: Document) => Promise<{
              violations: { id: string; nodes: { target: string[] }[] }[];
            }>;
          };
        }
      ).axe.run(document)
    ).violations.map((v) => ({
      id: v.id,
      targets: v.nodes.map((n) => n.target),
    })),
  );
  expect(violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}
async function remove(page: Page) {
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Delete my data", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Confirmation word").fill("DELETE");
  await dialog.getByRole("button", { name: "Permanently delete data" }).click();
  await expect(
    page.getByText("Your account and data were deleted.", { exact: true }),
  ).toBeVisible();
}
test.afterEach(async ({ page }) => {
  const token = await observedToken(page).catch(() => null);
  if (token)
    await page.request.delete("/api/v1/me/data", {
      headers: await headers(page),
    });
});

test("text PDF real review imports all ground-truth products; axe light/dark/mobile", async ({
  page,
}) => {
  // Registration deliberately handles 429/Retry-After above. Scope this console assertion
  // to the PDF flow so a successfully handled auth throttle is not a PDF runtime failure.
  await register(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type()))
      errors.push(message.text());
  });
  await choose(page, "text_single.pdf");
  await review(page);
  for (const theme of ["light", "dark"]) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByLabel("Theme preference").selectOption(theme);
    await page.setViewportSize({ width: 360, height: 900 });
    await audit(page);
    await page
      .getByRole("heading", { name: "Review every extracted row" })
      .scrollIntoViewIfNeeded();
    await capture(page, {
      path: path.resolve(
        `../docs/screenshots/statement-review-${theme}-mobile.png`,
      ),
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByLabel("Theme preference").selectOption("light");
  await capture(page, {
    path: path.resolve("../docs/screenshots/statement-review-desktop.png"),
  });
  const imported = await importReviewed(page);
  expect(imported.inserted_count).toBe(399);
  expect(imported.source_type).toBe("pdf_text");
  const truth = JSON.parse(
    fs.readFileSync(path.resolve("../backend/data/ground_truth.json"), "utf8"),
  ) as { patterns: { merchant: string; cadence: string }[] };
  const subscriptions = await read<
    components["schemas"]["Page_SubscriptionOut_"]
  >(page, "/subscriptions?limit=100");
  expect(
    subscriptions.items.map((s) => `${s.merchant}:${s.cadence}`).sort(),
  ).toEqual(truth.patterns.map((s) => `${s.merchant}:${s.cadence}`).sort());
  expect(errors).toEqual([]);
  await remove(page);
});

test("scanned PDF and corrected JPEG match independent totals; PNG local preview cancels", async ({
  page,
}) => {
  await register(page);
  await choose(page, "scanned.pdf");
  await review(page);
  expect((await importReviewed(page)).inserted_count).toBe(15);
  await choose(page, "corrupt.jpg");
  await review(page);
  await expect(page.getByText(/Reconciliation:/)).toContainText("mismatch");
  const expectedRows = corpus.variants.find(
    (v) => v.file === "corrupt.jpg",
  )!.rows;
  await page
    .getByLabel("Row 1 amount", { exact: true })
    .fill(expectedRows[0].amount);
  const duplicate = await importReviewed(page);
  expect(duplicate.inserted_count).toBe(0);
  expect(duplicate.duplicate_count).toBe(15);
  // Independent cents arithmetic from labelled source transactions, not application services.
  const cents = (v: string) => {
    const [whole, fraction = ""] = v.split(".");
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  };
  let monthly = 0n;
  for (const merchant of [
    "NETFLIX",
    "SPOTIFY",
    "YOUTUBE",
    "ICLOUD",
    "APPLE MUSIC",
  ]) {
    const rows = expectedRows.filter((r) => r.description.includes(merchant));
    const count = BigInt(rows.length);
    const sum = rows.reduce((total, r) => total + cents(r.amount), 0n);
    monthly += (sum * 2n + count) / (count * 2n);
  }
  const expected = `${monthly / 100n}.${String(monthly % 100n).padStart(2, "0")}`;
  const summary = await read<components["schemas"]["Summary"]>(
    page,
    "/summary",
  );
  expect(summary.monthly_equivalent).toBe(expected);
  await page.goto("/");
  await expect(page.getByTestId("monthly-total")).toHaveText(
    formatMoney(expected),
  );
  const png = await choose(page, "clean.png");
  await review(page);
  await page.getByText("Show my local file", { exact: true }).click();
  await expect(
    page.getByAltText("Local statement file for comparison"),
  ).toHaveAttribute("src", /^blob:/);
  await capture(page, {
    path: path.resolve("../docs/screenshots/statement-local-image.png"),
  });
  const cancellation = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      response.url().endsWith("/uploads/previews/" + png.id),
  );
  await page
    .getByRole("button", { name: "Cancel preview", exact: true })
    .click();
  expect((await cancellation).ok()).toBeTruthy();
  const cancelled = await read<components["schemas"]["StatementPreviewOut"]>(
    page,
    "/uploads/previews/" + png.id,
  );
  expect(cancelled.status).toBe("cancelled");
  expect(cancelled.result).toBeNull();
  await remove(page);
});

test("encrypted PDF password retry, unreadable guidance and hostile text remain safe", async ({
  page,
}) => {
  await register(page);
  await choose(page, "unreadable.jpg");
  await expect(
    page.getByRole("heading", { name: "Statement preview failed" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("alert")).toContainText("CSV");
  await choose(page, "hostile.pdf");
  await review(page);
  await expect(
    page.getByLabel("Row 1 description", { exact: true }),
  ).toHaveValue("<script>steal()</script>");
  expect(
    await page.locator("script").filter({ hasText: "steal()" }).count(),
  ).toBe(0);
  await page
    .getByRole("button", { name: "Cancel preview", exact: true })
    .click();
  await choose(page, "encrypted.pdf");
  await expect(
    page.getByRole("heading", { name: "Statement preview failed" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("alert")).toContainText("password");
  await page
    .getByLabel("PDF password (only if encrypted)")
    .fill("FixtureOnly42!");
  await page.getByRole("button", { name: "Retry local file preview" }).click();
  await review(page);
  await expect(page.getByLabel("PDF password (only if encrypted)")).toHaveValue(
    "",
  );
  expect((await importReviewed(page)).inserted_count).toBe(399);
  await remove(page);
});

test.beforeEach(async ({ page }) => {
  observeAuth(page);
});
