import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import type { components } from "../src/api/schema";
import { formatMoney } from "../src/lib/money";

const root = path.resolve("..");
const pictures = path.join(root, "docs/screenshots");
const factors = { weekly: 52n, monthly: 12n, quarterly: 4n, yearly: 1n };
type Truth = {
  patterns: {
    merchant: string;
    category: string;
    kind: string;
    cadence: keyof typeof factors;
    avg_amount: string;
  }[];
};
function expectedMusicSaving() {
  const truth = JSON.parse(
    fs.readFileSync(path.join(root, "backend/data/ground_truth.json"), "utf8"),
  ) as Truth;
  // Independent integer/rational arithmetic from labels, never the detector or API aggregation.
  const amounts = truth.patterns
    .filter((item) => item.kind === "subscription" && item.category === "music")
    .map((item) => {
      const [whole, fraction = ""] = item.avg_amount.split(".");
      return (
        (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"))) *
        factors[item.cadence]
      );
    });
  const largest = amounts.reduce((a, b) => (a > b ? a : b));
  const cents = (amounts.reduce((a, b) => a + b, 0n) - largest + 6n) / 12n;
  return `${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
}
async function token(page: Page) {
  return page.evaluate(
    () =>
      JSON.parse(sessionStorage.getItem("subtrack.session")!).token as string,
  );
}
async function read<T>(page: Page, endpoint: string): Promise<T> {
  const result = await page.request.get("/api/v1" + endpoint, {
    headers: { Authorization: `Bearer ${await token(page)}` },
  });
  expect(result.ok()).toBeTruthy();
  return result.json() as Promise<T>;
}
function runAlerts(day: string) {
  execFileSync("make", ["run-alerts", `AS_OF=${day}`], {
    cwd: root,
    encoding: "utf8",
    timeout: 60_000,
  });
}
function outbox(userId: string) {
  const script = `import json, sys
from email import policy
from email.parser import BytesParser
from app.config import get_settings
folder = get_settings().outbox_dir / sys.argv[1]
result = []
for file in sorted(folder.glob('*.eml')):
    message = BytesParser(policy=policy.default).parsebytes(file.read_bytes())
    result.append(dict(id=file.stem, kind='budget' if 'budget' in str(message['Subject']) else 'renewal', multipart=message.is_multipart(), notice='educational' in message.get_body(preferencelist=('plain',)).get_content()))
print(json.dumps(result))`;
  return JSON.parse(
    execFileSync(
      "docker",
      ["compose", "exec", "-T", "api", "python", "-c", script, userId],
      { cwd: root, encoding: "utf8", timeout: 30_000 },
    ),
  ) as { id: string; kind: string; multipart: boolean; notice: boolean }[];
}
async function accessibility(page: Page) {
  await page.addScriptTag({
    path: path.resolve("node_modules/axe-core/axe.min.js"),
  });
  const violations = await page.evaluate(async () =>
    (
      await (
        window as unknown as {
          axe: {
            run: (
              node: Document,
            ) => Promise<{
              violations: { id: string; nodes: { target: string[] }[] }[];
            }>;
          };
        }
      ).axe.run(document)
    ).violations.map((value) => ({
      id: value.id,
      targets: value.nodes.map((node) => node.target),
    })),
  );
  expect(violations).toEqual([]);
}

test("real insights, renewal and budget delivery are grounded and idempotent", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type()))
      errors.push(message.text());
  });
  await page.goto("/register");
  await expect(page).toHaveTitle(/SubTrack/);
  await page
    .getByLabel("Email address")
    .fill(`phase5-${Date.now()}@example.org`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("SyntheticPhase5Pass42!");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
  const user = await read<components["schemas"]["UserOut"]>(page, "/auth/me");
  const mode = await read<components["schemas"]["AlertSettingsOut"]>(
    page,
    "/settings/alerts",
  );
  expect(mode.delivery_mode).toBe("console"); // Never run a test job against a real SMTP deployment.
  await page
    .getByRole("link", { name: "Upload statement", exact: true })
    .first()
    .click();
  await page
    .getByLabel("Choose CSV file")
    .setInputFiles(path.join(root, "backend/data/sample_transactions.csv"));
  await page.getByRole("button", { name: "Confirm and import" }).click();
  await expect(
    page.getByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Recommendations", exact: true })
    .click();
  const music = page.getByRole("article", {
    name: "Music overlap",
    exact: true,
  });
  const expected = expectedMusicSaving();
  await expect(music).toContainText(formatMoney(expected));
  const records = await read<components["schemas"]["Page_RecommendationOut_"]>(
    page,
    "/recommendations?limit=100",
  );
  const duplicate = records.items.find(
    (item) => item.type === "duplicate" && item.members[0].category === "music",
  )!;
  expect(duplicate.est_monthly_saving).toBe(expected);
  const before = await read<components["schemas"]["Page_SubscriptionOut_"]>(
    page,
    "/subscriptions?limit=100",
  );
  await accessibility(page);
  await page.screenshot({
    path: path.join(pictures, "recommendations-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await accessibility(page);
  await page.screenshot({
    path: path.join(pictures, "recommendations-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use light theme" }).click();
  await page.setViewportSize({ width: 360, height: 800 });
  await accessibility(page);
  await page.screenshot({
    path: path.join(pictures, "recommendations-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await music.getByRole("button", { name: "Record review intent" }).click();
  await expect(
    page.getByText(
      "Review or cancellation intent recorded. Subscription statuses are unchanged.",
    ),
  ).toBeVisible();
  const after = await read<components["schemas"]["Page_SubscriptionOut_"]>(
    page,
    "/subscriptions?limit=100",
  );
  expect(after.items.map((item) => [item.id, item.status])).toEqual(
    before.items.map((item) => [item.id, item.status]),
  );
  await page.getByLabel("Recommendation status").selectOption("accepted");
  await expect(
    page.getByRole("article", { name: "Music overlap" }),
  ).toContainText("Intent recorded");
  // Product links open the actual charge drawer, with the real scoped detail request.
  await page
    .getByRole("article", { name: "Music overlap" })
    .getByRole("link")
    .first()
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: "Underlying charges" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/settings");
  await page
    .getByLabel("Notification email (optional)")
    .fill("phase5-notify@example.org");
  await page
    .getByRole("button", { name: "Save preferences", exact: true })
    .click();
  await expect(
    page.getByText(
      "Preferences saved. Due alerts are checked by the daily job.",
    ),
  ).toBeVisible();
  const next = before.items
    .filter(
      (item) =>
        item.kind === "subscription" &&
        item.status === "active" &&
        !item.possibly_cancelled,
    )
    .sort((a, b) => a.next_expected.localeCompare(b.next_expected))[0];
  const sendOn = new Date(`${next.next_expected}T12:00:00Z`);
  sendOn.setUTCDate(sendOn.getUTCDate() - 3);
  const day = sendOn.toISOString().slice(0, 10);
  runAlerts(day);
  const first = outbox(user.id);
  expect(first.filter((item) => item.kind === "renewal")).toHaveLength(1);
  expect(first[0].multipart && first[0].notice).toBe(true);
  const alerts = await read<components["schemas"]["Page_AlertOut_"]>(
    page,
    "/alerts?limit=100",
  );
  expect(alerts.items.find((item) => item.id === first[0].id)?.status).toBe(
    "sent",
  );
  runAlerts(day);
  expect(outbox(user.id)).toEqual(first);
  await page.getByLabel("Monthly limit (₹)").fill("1.00");
  await page.getByRole("button", { name: "Save budget", exact: true }).click();
  await expect(page.getByText("Budget saved: ₹1.00.")).toBeVisible();
  runAlerts(day);
  const both = outbox(user.id);
  expect(both.filter((item) => item.kind === "renewal")).toHaveLength(1);
  expect(both.filter((item) => item.kind === "budget")).toHaveLength(1);
  runAlerts(day);
  expect(outbox(user.id)).toEqual(both);
  await page.getByRole("button", { name: "Refresh alerts" }).click();
  await expect(page.getByText("Sent", { exact: true })).toHaveCount(2);
  await accessibility(page);
  await page.screenshot({
    path: path.join(pictures, "alert-deliveries.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Delete my data", exact: true })
    .click();
  await page.getByLabel("Confirmation word").fill("DELETE");
  await page.getByRole("button", { name: "Permanently delete data" }).click();
  await expect(
    page.getByText("Your account and data were deleted.", { exact: true }),
  ).toBeVisible();
  expect(outbox(user.id)).toEqual([]);
  expect(errors).toEqual([]);
});
