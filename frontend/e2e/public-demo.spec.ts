import { test, expect } from "@playwright/test";
import { observeAuth, observedToken } from "./auth";
import { capture } from "./evidence";
import path from "node:path";
import fs from "node:fs";

test("public visitors are isolated, file uploads disabled, synthetic demo works without shared login", async ({
  page,
  browser,
}) => {
  test.skip(
    process.env.E2E_PUBLIC_DEMO !== "1",
    "Runs in the explicit public-demo-only stack",
  );
  observeAuth(page);
  await page.goto("/login");
  await expect(page.getByLabel("Public demo notice")).toContainText(
    "do not upload real statements or personal data",
  );
  await page.getByRole("button", { name: "Start isolated demo" }).click();
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
  const auth = { Authorization: `Bearer ${await observedToken(page)}` };
  const user = (await (
    await page.request.get("/api/v1/auth/me", { headers: auth })
  ).json()) as { id: string };
  expect(
    (await page.context().cookies()).some((c) => c.name === "subtrack_refresh"),
  ).toBe(false);
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Upload statement", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Synthetic demo data" }),
  ).toBeVisible();
  expect(await page.locator('input[type="file"]').count()).toBe(0);
  for (const extension of ["csv", "pdf", "png"]) {
    for (const endpoint of ["/uploads", "/uploads/preview"]) {
      const rejected = await page.request.post("/api/v1" + endpoint, {
        headers: auth,
        multipart: {
          file: {
            name: "synthetic." + extension,
            mimeType: "application/octet-stream",
            buffer: Buffer.from("synthetic rejection test"),
          },
        },
      });
      expect(rejected.status()).toBe(403);
      expect((await rejected.json()).error.code).toBe("demo_data_only");
    }
  }
  await page.getByRole("button", { name: "Load demo data" }).click();
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
  const subscriptions = (await (
    await page.request.get("/api/v1/subscriptions?limit=100", { headers: auth })
  ).json()) as { items: { id: string }[]; total: number };
  const truth = JSON.parse(
    fs.readFileSync(path.resolve("../backend/data/ground_truth.json"), "utf8"),
  ) as { patterns: unknown[] };
  expect(subscriptions.total).toBe(truth.patterns.length);
  const secondContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
  });
  try {
    const other = await secondContext.newPage();
    observeAuth(other);
    await other.goto("/login");
    await other.getByRole("button", { name: "Start isolated demo" }).click();
    await expect(
      other.getByRole("heading", { name: "Your recurring spend" }),
    ).toBeVisible();
    const otherAuth = { Authorization: `Bearer ${await observedToken(other)}` };
    const second = (await (
      await other.request.get("/api/v1/auth/me", { headers: otherAuth })
    ).json()) as { id: string };
    expect(second.id).not.toBe(user.id);
    expect(
      (
        await (
          await other.request.get("/api/v1/subscriptions", {
            headers: otherAuth,
          })
        ).json()
      ).total,
    ).toBe(0);
    expect(
      (
        await other.request.get(
          "/api/v1/subscriptions/" + subscriptions.items[0].id,
          { headers: otherAuth },
        )
      ).status(),
    ).toBe(404);
    expect(
      (
        await other.request.delete("/api/v1/me/data", { headers: otherAuth })
      ).ok(),
    ).toBeTruthy();
  } finally {
    await secondContext.close();
  }
  for (const theme of ["light", "dark"]) {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.getByLabel("Theme preference").selectOption(theme);
    await page.setViewportSize({ width: 360, height: 800 });
    await page.addScriptTag({
      path: path.resolve("node_modules/axe-core/axe.min.js"),
    });
    const violations = await page.evaluate(async () => {
      const audit = (
        window as unknown as {
          axe: {
            run: (node: Document) => Promise<{ violations: { id: string }[] }>;
          };
        }
      ).axe;
      return (await audit.run(document)).violations.map((item) => item.id);
    });
    expect(violations).toEqual([]);
  }
  await capture(page, {
    path: path.resolve("../docs/screenshots/public-demo-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Start isolated demo" }),
  ).toBeVisible();
  expect(
    (await page.request.delete("/api/v1/me/data", { headers: auth })).ok(),
  ).toBeTruthy();
});
