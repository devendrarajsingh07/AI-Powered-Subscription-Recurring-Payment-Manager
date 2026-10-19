import type { Page } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { setTimeout } from "node:timers/promises";

type Options = NonNullable<Parameters<Page["screenshot"]>[0]> & {
  path: string;
};

export async function capture(page: Page, options: Options) {
  const { path: destination, ...settings } = options;
  const pixels = await page.screenshot(settings);
  await fs.mkdir(path.dirname(destination), { recursive: true });
  for (let attempt = 0; ; attempt++) {
    try {
      await fs.writeFile(destination, pixels);
      return;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (
        attempt >= 9 ||
        !["UNKNOWN", "EBUSY", "EPERM", "EACCES"].includes(code || "")
      )
        throw error;
      // Some Windows readers/scanners temporarily deny overwrite. Capture pixels once;
      // retry only their file publication, never the browser action or assertions.
      await setTimeout(Math.min(1000, 100 * (attempt + 1)));
    }
  }
}
