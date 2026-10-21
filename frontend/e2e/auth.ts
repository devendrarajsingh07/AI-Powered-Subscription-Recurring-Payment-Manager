import { expect, type Page } from "@playwright/test";

const captured = new WeakMap<Page, string>();
export function observeAuth(page: Page) {
  page.on("request", (request) => {
    const value = request.headers()["authorization"];
    if (value?.startsWith("Bearer ")) captured.set(page, value.slice(7));
  });
}
export async function observedToken(page: Page) {
  await expect.poll(() => captured.has(page)).toBeTruthy();
  return captured.get(page)!;
}
