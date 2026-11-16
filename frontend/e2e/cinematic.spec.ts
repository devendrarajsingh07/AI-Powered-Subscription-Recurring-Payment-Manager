import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import type { AxeResults } from "axe-core";

async function checkAccessibility(page: Page) {
  await page.addScriptTag({
    path: path.resolve("node_modules/axe-core/axe.min.js"),
  });
  const violations = await page.evaluate(async () => {
    const { axe } = window as Window & {
      axe: { run: () => Promise<AxeResults> };
    };
    return (await axe.run()).violations.map(({ id, nodes }) => ({
      id,
      targets: nodes.map(({ target }) => target),
    }));
  });
  expect(violations).toEqual([]);
}

test("the public journey keeps its heading clear and all chapters reachable in reduced motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/journey");
  const heading = page.getByRole("heading", {
    name: "Money moves. Trust stays.",
  });
  await expect(heading).toBeInViewport();
  const bounds = await heading.boundingBox();
  const nav = await page.getByRole("banner").boundingBox();
  expect(bounds!.y).toBeGreaterThanOrEqual(nav!.y + nav!.height);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(360);
  const dock = page.getByRole("navigation", { name: "Journey chapters" });
  await expect(dock.getByRole("link")).toHaveCount(6);
  const safetyNotice = page.getByText(
    "Public demo — do not upload real statements or personal data",
  );
  await expect(safetyNotice).toBeInViewport();
  await expect(page.getByText("Still view")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  for (const chapter of [
    "Permission",
    "Movement",
    "Evidence",
    "Connection limits",
    "The next move",
  ]) {
    const link = dock.getByRole("link", { name: chapter, exact: true });
    await link.click();
    await expect(link).toHaveAttribute("aria-current", "location");
  }
  await expect(page.getByRole("group", { name: /vault/i })).toBeVisible();
  await expect(safetyNotice).toBeInViewport();
  await checkAccessibility(page);
  await page
    .getByRole("banner")
    .getByRole("link", { name: "System notes" })
    .click();
  await expect(
    page.getByRole("heading", { name: "How SubTrack works" }),
  ).toBeInViewport();
  await checkAccessibility(page);
});

test("WebGL failure preserves the journey through a chapter still", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      ...args: Parameters<typeof getContext>
    ) {
      if (args[0] === "webgl2") return null;
      return Reflect.apply(getContext, this, args);
    } as typeof getContext;
  });
  await page.goto("/journey");
  await expect(page.getByRole("button", { name: "Retry 3D" })).toBeVisible();
  await expect(page.getByText("Still view")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Retry 3D" }).click();
  await expect(page.getByRole("button", { name: "Retry 3D" })).toBeVisible();
});
