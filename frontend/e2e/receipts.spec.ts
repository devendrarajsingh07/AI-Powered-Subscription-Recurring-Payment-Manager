import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { observeAuth, observedToken } from "./auth";
import type { components } from "../src/api/schema";

let cleanupToken: string | undefined;

test.afterEach(async ({ request }) => {
  if (cleanupToken) {
    const response = await request.delete("/api/v1/me/data", {
      headers: { Authorization: `Bearer ${cleanupToken}` },
      timeout: 15_000,
    });
    expect([200, 401]).toContain(response.status());
    cleanupToken = undefined;
  }
});

const fixtures = path.resolve("../backend/data/receipts");
const truth = JSON.parse(
  fs.readFileSync(path.join(fixtures, "ground_truth.json"), "utf8"),
) as {
  cases: Record<
    string,
    { detect?: boolean; date?: string; description?: string; amount?: string }
  >;
  patterns: {
    merchant: string;
    cadence: "monthly" | "yearly";
    avg_amount: string;
  }[];
};
async function headers(page: Page) {
  return { Authorization: `Bearer ${await observedToken(page)}` };
}
async function pick(page: Page, filename: string) {
  await page
    .getByLabel("Choose synthetic receipt")
    .setInputFiles(path.join(fixtures, filename));
  await expect(
    page.getByRole("heading", { name: "Review receipt payment" }),
  ).toBeVisible();
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
            run: (doc: Document) => Promise<{ violations: { id: string }[] }>;
          };
        }
      ).axe.run(document)
    ).violations.map((v) => v.id),
  );
  expect(violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

test("synthetic receipts: review, real ingestion, dedupe, independent totals, safe errors and deletion", async ({
  page,
}) => {
  test.setTimeout(180_000);
  page.setDefaultTimeout(15_000);
  observeAuth(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/register");
  await page
    .getByLabel("Email address")
    .fill(`receipt-ui-${Date.now()}@example.org`);
  await page.getByLabel("Password", { exact: true }).fill("SyntheticDemo42!");
  const registered = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/auth/register") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Create account" }).click();
  let response = await registered;
  if (response.status() === 429) {
    const delay = Number(response.headers()["retry-after"]);
    expect(Number.isInteger(delay) && delay > 0 && delay <= 60).toBe(true);
    await page.waitForTimeout(delay * 1000 + 100);
    const retry = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/auth/register") &&
        r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Create account" }).click();
    response = await retry;
  }
  expect(response.status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
  cleanupToken = await observedToken(page);
  {
    await page.goto("/upload");
    await page.getByLabel("Import source").selectOption("receipt");
    const imports = Object.entries(truth.cases).filter(
      ([, value]) => value.detect,
    );
    for (const [index, [filename, expected]] of imports.entries()) {
      await pick(page, filename);
      await expect(page.getByLabel("Row 1 date", { exact: true })).toHaveValue(
        expected.date!,
      );
      await expect(
        page.getByLabel("Row 1 description", { exact: true }),
      ).toHaveValue(expected.description!);
      await expect(
        page.getByLabel("Row 1 amount", { exact: true }),
      ).toHaveValue(expected.amount!);
      const confirm = page.getByRole("button", {
        name: "Import reviewed rows",
      });
      await expect(confirm).toBeDisabled();
      if (index === 0) {
        expect(
          await page
            .locator(".statement-review iframe, .statement-review img")
            .count(),
        ).toBe(0);
        for (const theme of ["light", "dark"]) {
          await page.setViewportSize({ width: 1280, height: 900 });
          await page.getByLabel("Theme preference").selectOption(theme);
          await page.setViewportSize({ width: 360, height: 900 });
          await audit(page);
          if (process.env.E2E_RECEIPT_SCREENSHOT)
            await page.screenshot({
              path: process.env.E2E_RECEIPT_SCREENSHOT.replace(
                ".png",
                `-${theme}-mobile.png`,
              ),
              fullPage: true,
            });
        }
        await page.setViewportSize({ width: 1280, height: 900 });
        await page.getByLabel("Theme preference").selectOption("light");
        await audit(page);
        if (process.env.E2E_RECEIPT_SCREENSHOT)
          await page.screenshot({
            path: process.env.E2E_RECEIPT_SCREENSHOT,
            fullPage: true,
          });
      }
      await page.getByLabel("Verify row 1").check();
      const accepted = page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/v1/uploads") &&
          r.request().method() === "POST",
      );
      await confirm.click();
      expect((await accepted).status()).toBe(202);
      await expect(
        page.getByRole("heading", { name: "Review receipt payment" }),
      ).not.toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Receipt processed" }),
      ).toBeVisible({ timeout: 30_000 });
      await expect(
        page.getByRole("region", { name: "Upload progress" }),
      ).toContainText("Inserted");
    }
    const subscriptionsResponse = await page.request.get(
      "/api/v1/subscriptions?limit=100",
      { headers: await headers(page) },
    );
    const subscriptions =
      (await subscriptionsResponse.json()) as components["schemas"]["Page_SubscriptionOut_"];
    expect(
      subscriptions.items.map((s) => `${s.merchant}:${s.cadence}`).sort(),
    ).toEqual(truth.patterns.map((s) => `${s.merchant}:${s.cadence}`).sort());
    // Independent integer cents from labelled plan inputs; never use application math.
    const cents = (value: string) => BigInt(value.replace(".", ""));
    const money = (value: bigint) =>
      `${value / 100n}.${String(value % 100n).padStart(2, "0")}`;
    const yearly = truth.patterns.reduce(
      (sum, p) =>
        sum + cents(p.avg_amount) * (p.cadence === "monthly" ? 12n : 1n),
      0n,
    );
    const summaryResponse = await page.request.get("/api/v1/summary", {
      headers: await headers(page),
    });
    const summary =
      (await summaryResponse.json()) as components["schemas"]["Summary"];
    expect(summary.yearly_total).toBe(money(yearly));
    expect(summary.monthly_equivalent).toBe(money((yearly + 6n) / 12n));

    await pick(page, imports[0][0]);
    await page.getByLabel("Verify row 1").check();
    const replayed = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/uploads") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Import reviewed rows" }).click();
    const replay = (await (
      await replayed
    ).json()) as components["schemas"]["UploadOut"];
    await expect
      .poll(async () => {
        const result = await page.request.get(`/api/v1/uploads/${replay.id}`, {
          headers: await headers(page),
        });
        return ((await result.json()) as components["schemas"]["UploadOut"])
          .status;
      })
      .toBe("done");
    const replayResult = await page.request.get(
      `/api/v1/uploads/${replay.id}`,
      { headers: await headers(page) },
    );
    const counts =
      (await replayResult.json()) as components["schemas"]["UploadOut"];
    expect(counts.inserted_count).toBe(0);
    expect(counts.duplicate_count).toBe(1);
    // A missing payment date cannot borrow the header date; cancel leaves no import.
    await pick(page, "header-date-is-not-payment.eml");
    await expect(page.getByLabel("Row 1 date", { exact: true })).toHaveValue(
      "",
    );
    await page.getByLabel("Verify row 1").check();
    await expect(
      page.getByRole("button", { name: "Import reviewed rows" }),
    ).toBeDisabled();
    await page.getByRole("button", { name: "Cancel preview" }).click();
    expect(errors).toEqual([]);
    await page
      .getByLabel("Choose synthetic receipt")
      .setInputFiles(path.join(fixtures, "failed-is-not-paid.eml"));
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByLabel("Choose synthetic receipt")).toBeEnabled();
  }
  {
    await page.goto("/settings");
    await page
      .getByRole("button", { name: "Delete my data", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Confirmation word").fill("DELETE");
    await dialog
      .getByRole("button", { name: "Permanently delete data" })
      .click();
    await expect(
      page.getByText("Your account and data were deleted.", { exact: true }),
    ).toBeVisible();
  }
});
