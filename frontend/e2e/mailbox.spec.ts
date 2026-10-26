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
async function headers(page: Page) {
  return { Authorization: `Bearer ${await observedToken(page)}` };
}
async function read<T>(page: Page, route: string) {
  const result = await page.request.get("/api/v1" + route, {
    headers: await headers(page),
  });
  expect(result.ok()).toBe(true);
  return result.json() as Promise<T>;
}
async function sync(page: Page) {
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/mailbox/sync") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sync synthetic receipts" }).click();
  const result = await response;
  expect(result.status()).toBe(202);
  const job = (await result.json()) as components["schemas"]["MailboxSyncOut"];
  await expect
    .poll(
      async () =>
        (
          await read<components["schemas"]["MailboxSyncOut"]>(
            page,
            `/mailbox/sync/${job.id}`,
          )
        ).status,
    )
    .toBe("done");
  return read<components["schemas"]["MailboxSyncOut"]>(
    page,
    `/mailbox/sync/${job.id}`,
  );
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

test("mailbox receipt flow: real worker, explicit matching, independent interests and purge", async ({
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
    .fill(`mailbox-ui-${Date.now()}@example.org`);
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
  await page.goto("/mailbox");
  const consent = page.getByLabel(
    "I consent to the synthetic mailbox rehearsal described above",
  );
  await expect(
    page.getByRole("button", { name: "Start synthetic mailbox lab" }),
  ).toBeDisabled();
  await consent.check();
  await page
    .getByRole("button", { name: "Start synthetic mailbox lab" })
    .click();
  await expect(page.getByText("Synthetic fixture connection")).toBeVisible();
  const first = await sync(page);
  const truth = JSON.parse(
    fs.readFileSync(
      path.resolve("../backend/data/receipts/ground_truth.json"),
      "utf8",
    ),
  ) as {
    cases: Record<string, { verdict: string }>;
    patterns: { merchant: string; avg_amount: string }[];
  };
  const accepted = Object.values(truth.cases).filter(
    (value) => value.verdict === "review",
  ).length;
  expect(first.accepted + first.duplicates).toBe(accepted);
  expect(first.total).toBe(Object.keys(truth.cases).length);
  expect(
    (await read<components["schemas"]["Summary"]>(page, "/summary"))
      .monthly_equivalent,
  ).toBe("0.00");
  const price = truth.patterns.find(
    (p) => p.merchant === "netflix",
  )!.avg_amount;
  await page.goto("/upload");
  await page.getByLabel("Choose statement file").setInputFiles({
    name: "synthetic-matching.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      `date,description,amount,type\n2026-07-01,UPI NETFLIX REF1,${price},debit\n2026-08-01,POS NETFLIX REF2,${price},debit\n2026-09-01,NETFLIX REF3,${price},debit\n`,
    ),
  });
  await page.getByRole("button", { name: "Confirm and import" }).click();
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible({ timeout: 30_000 });
  const before = await read<components["schemas"]["Summary"]>(page, "/summary");
  expect(before.monthly_equivalent).toBe(price);
  await page.goto("/mailbox");
  const evidence = await read<
    components["schemas"]["Page_ReceiptEvidenceOut_"]
  >(page, "/mailbox/evidence?limit=100");
  const item = evidence.items.find(
    (r) => r.merchant === "netflix" && r.charged_on === "2026-07-01",
  )!;
  expect(item.candidates.length).toBe(1);
  const card = page.getByTestId(item.id);
  await expect(card).toBeVisible();
  for (const theme of ["light", "dark"]) {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.getByLabel("Theme preference").selectOption(theme);
    await page.setViewportSize({ width: 360, height: 900 });
    await audit(page);
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByLabel("Theme preference").selectOption("light");
  await audit(page);
  const screenshot =
    process.env.E2E_MAILBOX_SCREENSHOT ||
    (fs.existsSync("/evidence")
      ? "/evidence/mailbox-lab-desktop.png"
      : undefined);
  if (screenshot) {
    await card.scrollIntoViewIfNeeded();
    await page.screenshot({ path: screenshot, fullPage: false });
  }
  await expect(
    card.getByRole("button", { name: "Confirm bank match" }),
  ).toBeDisabled();
  await card.getByRole("radio").check();
  await card.getByLabel("I confirm this is the same payment").check();
  await card.getByRole("button", { name: "Confirm bank match" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Receipt decision saved" }),
  ).toBeVisible();
  expect(await read(page, "/summary")).toEqual(before);
  const replay = await sync(page);
  expect(replay.accepted).toBe(0);
  expect(replay.duplicates).toBe(accepted);
  const interests = page.getByRole("region", {
    name: "Voluntary plan interest",
  });
  await interests.getByLabel("music", { exact: true }).check();
  await expect(
    interests.getByRole("button", { name: "Save voluntary interests" }),
  ).toBeDisabled();
  await interests
    .getByLabel("I separately consent to save these voluntary interests")
    .check();
  await interests
    .getByRole("button", { name: "Save voluntary interests" })
    .click();
  await expect
    .poll(
      async () =>
        (await read<components["schemas"]["InterestOut"]>(page, "/interests"))
          .categories,
    )
    .toEqual(["music"]);
  await page
    .getByRole("button", { name: "Disconnect and remove evidence" })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Confirmation word").fill("DISCONNECT");
  await dialog.getByRole("button", { name: "Purge mailbox evidence" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Mailbox consent withdrawn" }),
  ).toBeVisible();
  expect(
    (
      await read<components["schemas"]["Page_ReceiptEvidenceOut_"]>(
        page,
        "/mailbox/evidence",
      )
    ).total,
  ).toBe(0);
  expect(await read(page, "/summary")).toEqual(before);
  expect(
    (await read<components["schemas"]["InterestOut"]>(page, "/interests"))
      .categories,
  ).toEqual(["music"]);
  await page.getByRole("button", { name: "Withdraw all interests" }).click();
  await expect
    .poll(
      async () =>
        (await read<components["schemas"]["InterestOut"]>(page, "/interests"))
          .categories,
    )
    .toEqual([]);
  expect(errors).toEqual([]);
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Delete my data", exact: true })
    .click();
  const deletion = page.getByRole("dialog");
  await deletion.getByLabel("Confirmation word").fill("DELETE");
  await deletion
    .getByRole("button", { name: "Permanently delete data" })
    .click();
  await expect(
    page.getByText("Your account and data were deleted.", { exact: true }),
  ).toBeVisible();
});
