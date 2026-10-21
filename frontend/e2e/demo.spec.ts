import { observeAuth, observedToken } from "./auth";
import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { capture } from "./evidence";
import { formatMoney } from "../src/lib/money";
import type { components } from "../src/api/schema";

const root = path.resolve("..");
async function headers(page: Page) {
  return {
    Authorization: `Bearer ${await observedToken(page)}`,
  };
}
async function read<T>(page: Page, route: string): Promise<T> {
  const result = await page.request.get("/api/v1" + route, {
    headers: await headers(page),
  });
  expect(result.ok()).toBeTruthy();
  return result.json() as Promise<T>;
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
            run: (node: Document) => Promise<{
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
function job(day: string) {
  execFileSync("make", ["run-alerts", `AS_OF=${day}`], {
    cwd: root,
    timeout: 60000,
    stdio: "pipe",
  });
}
function outbox(userId: string) {
  const code = `import json,sys
from app.config import get_settings
from email import policy
from email.parser import BytesParser
result=[]
for f in (get_settings().outbox_dir/sys.argv[1]).glob('*.eml'):
 m=BytesParser(policy=policy.default).parsebytes(f.read_bytes())
 result.append(dict(id=f.stem,kind='budget' if 'budget' in str(m['Subject']) else 'renewal',notice='educational' in m.get_body(preferencelist=('plain',)).get_content()))
print(json.dumps(sorted(result,key=lambda m:m['id'])))`;
  return JSON.parse(
    execFileSync(
      "docker",
      ["compose", "exec", "-T", "api", "python", "-c", code, userId],
      { cwd: root, encoding: "utf8", timeout: 30000 },
    ),
  ) as { id: string; kind: string; notice: boolean }[];
}
async function register(page: Page, prefix: string) {
  await page.goto("/register");
  await page
    .getByLabel("Email address")
    .fill(`${prefix}-${Date.now()}@example.org`);
  await page.getByLabel("Password", { exact: true }).fill("SyntheticDemo42!");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByRole("button", { name: "Load demo data" }).click();
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
}
async function deleteAccount(page: Page) {
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Delete my data", exact: true })
    .click();
  await page.getByRole("dialog").getByLabel("Confirmation word").fill("DELETE");
  await page.getByRole("button", { name: "Permanently delete data" }).click();
  await expect(
    page.getByText("Your account and data were deleted.", { exact: true }),
  ).toBeVisible();
}

test("written three-minute demo: register, load, review, grounded chat, emails, delete", async ({
  page,
}) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await register(page, "demo");
  const uploads = await read<components["schemas"]["Page_UploadOut_"]>(
    page,
    "/uploads",
  );
  expect(uploads.items[0].source).toBe("demo");
  expect(uploads.items[0].demo_as_of).toBe(process.env.APP_TEST_AS_OF);
  const truth = JSON.parse(
    fs.readFileSync(path.join(root, "backend/data/ground_truth.json"), "utf8"),
  ) as {
    patterns: {
      avg_amount: string;
      cadence: string;
      merchant: string;
      category: string;
    }[];
  };
  const factors: Record<string, bigint> = {
    weekly: 52n,
    monthly: 12n,
    quarterly: 4n,
    yearly: 1n,
  };
  const annual = truth.patterns.reduce(
    (sum, p) =>
      sum + BigInt(p.avg_amount.replace(".", "")) * factors[p.cadence],
    0n,
  );
  const monthly = (annual + 6n) / 12n;
  const decimal = (cents: bigint) =>
    `${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
  const summary = await read<components["schemas"]["Summary"]>(
    page,
    "/summary",
  );
  expect(summary.monthly_equivalent).toBe(decimal(monthly));
  expect(summary.yearly_total).toBe(decimal(annual));
  expect(uploads.items[0].detected_count).toBe(truth.patterns.length);
  await expect(page.getByTestId("monthly-total")).toHaveText(
    formatMoney(summary.monthly_equivalent),
  );
  await page.getByRole("button", { name: "Dismiss import result" }).click();
  await capture(page, {
    path: path.join(root, "docs/screenshots/demo-dashboard.png"),
    fullPage: true,
  });
  await page.goto("/subscriptions");
  await expect(page.getByText(/May have stopped/i).first()).toBeVisible();
  const products = await read<components["schemas"]["Page_SubscriptionOut_"]>(
    page,
    "/subscriptions?limit=100",
  );
  expect(products.items.map((s) => s.merchant).sort()).toEqual(
    truth.patterns.map((p) => p.merchant).sort(),
  );
  await page
    .getByRole("button", { name: "Review spotify", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: "Underlying charges" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Review spotify", exact: true }),
  ).toBeFocused();
  await page.goto("/recommendations");
  const recs = await read<components["schemas"]["Page_RecommendationOut_"]>(
    page,
    "/recommendations?type=duplicate",
  );
  const music = recs.items.find((r) =>
    r.members.every((m) => m.category === "music"),
  )!;
  const musicCents = truth.patterns
    .filter((p) => p.category === "music")
    .map((p) => BigInt(p.avg_amount.replace(".", "")) * factors[p.cadence]);
  const saving =
    (musicCents.reduce((a, b) => a + b, 0n) -
      musicCents.reduce((a, b) => (a > b ? a : b)) +
      6n) /
    12n;
  expect(music.est_monthly_saving).toBe(decimal(saving));
  await expect(
    page
      .getByText(formatMoney(music.est_monthly_saving!), { exact: true })
      .first(),
  ).toBeVisible();
  await page
    .getByRole("article", { name: "Music overlap" })
    .getByRole("button", { name: "Record review intent" })
    .click();
  await expect(
    page.getByText(
      "Review or cancellation intent recorded. Subscription statuses are unchanged.",
    ),
  ).toBeVisible();
  const afterReview = await read<
    components["schemas"]["Page_SubscriptionOut_"]
  >(page, "/subscriptions?limit=100");
  expect(afterReview.items.map((item) => [item.id, item.status])).toEqual(
    products.items.map((item) => [item.id, item.status]),
  );
  await page.getByRole("button", { name: "Ask SubTrack" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "What renews this week?" }).click();
  await dialog.getByRole("button", { name: "Send question" }).click();
  const answer = dialog
    .getByRole("article", { name: "SubTrack answer" })
    .last();
  const upcoming = await read<components["schemas"]["Page_SubscriptionOut_"]>(
    page,
    "/renewals/upcoming?days=7&limit=100",
  );
  for (const item of upcoming.items) {
    await expect(answer).toContainText(item.next_expected);
    await expect(answer).toContainText(`₹${item.avg_amount}`);
  }
  await expect(answer).toContainText("Based on: upcoming renewals");
  await page.keyboard.press("Escape");
  await page.goto("/settings");
  await page.getByLabel("Monthly limit (₹)").fill("99999.00");
  await page.getByRole("button", { name: "Save budget" }).click();
  await expect(page.getByText(/Budget saved/)).toBeVisible();
  const me = await read<components["schemas"]["UserOut"]>(page, "/auth/me");
  const planned = await read<components["schemas"]["Page_AlertOut_"]>(
    page,
    "/alerts?limit=100",
  );
  const alertDay = planned.items
    .filter(
      (item) =>
        item.kind === "renewal" && item.send_on >= process.env.APP_TEST_AS_OF!,
    )
    .map((item) => item.send_on)
    .sort()[0];
  expect(alertDay).toBeTruthy();
  job(alertDay);
  const first = outbox(me.id);
  expect(first.some((m) => m.kind === "renewal" && m.notice)).toBe(true);
  expect(first.some((m) => m.kind === "budget")).toBe(false);
  await page.reload();
  await expect(page.getByText("Sent", { exact: true }).first()).toBeVisible();
  job(alertDay);
  expect(outbox(me.id)).toEqual(first);
  await page.getByLabel("Monthly limit (₹)").fill("1.00");
  await page.getByRole("button", { name: "Save budget" }).click();
  await expect(page.getByText(/Budget saved/)).toBeVisible();
  job(alertDay);
  const delivered = outbox(me.id);
  expect(delivered.filter((m) => m.kind === "budget")).toHaveLength(1);
  job(alertDay);
  expect(outbox(me.id)).toEqual(delivered);
  const alerts = await read<components["schemas"]["Page_AlertOut_"]>(
    page,
    "/alerts?limit=100",
  );
  expect(
    alerts.items.some((a) => a.kind === "budget" && a.status === "sent"),
  ).toBe(true);
  await deleteAccount(page);
  expect(outbox(me.id)).toEqual([]);
  expect(errors).toEqual([]);
});

test("every page: axe both themes at 360px; responsive 768/1280; dialogs and chat", async ({
  page,
}) => {
  test.setTimeout(240000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const theme of ["light", "dark"]) {
    await page.addInitScript(
      (value) => localStorage.setItem("subtrack.theme", value),
      theme,
    );
    await page.setViewportSize({ width: 360, height: 800 });
    for (const route of [
      "/login",
      "/register",
      "/verify-email",
      "/reset-password",
    ]) {
      await page.goto(route);
      // Wait for the routed page, not the auth-bootstrap loading shell, before scanning.
      await expect(page.getByRole("heading").first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      await audit(page);
    }
  }
  await register(page, "audit");
  const routes = [
    "/",
    "/upload",
    "/subscriptions",
    "/renewals",
    "/recommendations",
    "/categories",
    "/settings",
    "/not-found",
  ];
  for (const theme of ["light", "dark"]) {
    await page.addInitScript(
      (value) => localStorage.setItem("subtrack.theme", value),
      theme,
    );
    for (const width of [360, 768, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of routes) {
        if (route === "/" || route === "/not-found") {
          await page.goto(route);
        } else {
          const labels: Record<string, string> = {
            "/upload": "Upload statement",
            "/subscriptions": "Subscriptions",
            "/renewals": "Renewals",
            "/recommendations": "Recommendations",
            "/categories": "Categories",
            "/settings": "Settings",
          };
          const link = page
            .getByRole("navigation", { name: "Main navigation" })
            .getByRole("link", { name: labels[route], exact: true });
          if (!(await link.isVisible())) {
            await page
              .getByRole("button", { name: "Toggle navigation" })
              .click();
          }
          await link.click();
        }
        // Audit real navigation without hammering refresh-cookie bootstrap on every link.
        // Dedicated TLS/reload flows still verify full-document session restoration.
        await expect(page).toHaveURL((url) => url.pathname === route);
        await expect(page.locator("main h1")).toBeVisible();
        await expect(
          page.getByText("Loading your data…", { exact: true }),
        ).toHaveCount(0);
        if (width === 360) await audit(page);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      }
    }
    await page.setViewportSize({ width: 360, height: 800 });
    await page.getByRole("button", { name: "Ask SubTrack" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await audit(page);
    await capture(page, {
      path: path.join(root, `docs/screenshots/release-chat-${theme}-360.png`),
      fullPage: false,
    });
    await page.keyboard.press("Escape");
  }
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Remove demo data", exact: true })
    .click();
  await audit(page);
  await page.getByRole("button", { name: "Confirm remove demo" }).click();
  await expect(page.getByText(/Demo data removed/)).toBeVisible();
  await deleteAccount(page);
  expect(errors).toEqual([]);
});

test.beforeEach(async ({ page }) => {
  observeAuth(page);
});
