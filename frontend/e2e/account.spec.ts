import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

test("same-site TLS verification, cookie reload, reset and session revocation", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_LOCAL_TLS !== "1",
    "Runs in the explicit local sibling-host TLS stack",
  );
  const email = `tls-${Date.now()}@example.org`;
  const original = "SyntheticTlsSecure42!";
  const replacement = "ReplacementTlsSecure42!";
  function readCode(subject: string) {
    const script = `from pathlib import Path; from email import policy; from email.parser import BytesParser; import re; from app.config import get_settings; mails=[BytesParser(policy=policy.default).parsebytes(p.read_bytes()) for p in Path(get_settings().outbox_dir).rglob('*.eml')]; matches=[m for m in mails if m['To']=='${email}' and '${subject}' in str(m['Subject']).lower()]; print(re.search(r'single-use code in SubTrack: ([\\w-]+)',matches[-1].get_body(preferencelist=('plain',)).get_content()).group(1))`;
    return execFileSync(
      "docker",
      ["compose", "exec", "-T", "api", "python", "-c", script],
      {
        cwd: path.resolve(".."),
        encoding: "utf8",
      },
    ).trim();
  }
  async function deliveredCode(subject: string) {
    let value = "";
    await expect
      .poll(() => {
        try {
          value = readCode(subject);
          return Boolean(value);
        } catch {
          return false;
        }
      })
      .toBe(true);
    return value;
  }
  await page.goto("/register");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(original);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Verify your email" }),
  ).toBeVisible();
  await page.getByLabel("Single-use code").fill(await deliveredCode("verify"));
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Email verified" }),
  ).toContainText("Email verified");
  await page.getByRole("link", { name: "Back to sign in" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(original);
  const loginResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/auth/login") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  // Assert the actual response without printing bearer tokens or request credentials.
  expect((await loginResponse).status()).toBe(200);
  try {
    await expect(
      page.getByRole("heading", { name: "Your recurring spend" }),
    ).toBeVisible();
  } catch {
    const notices = await page.getByRole("alert").allTextContents();
    throw new Error(
      `Dashboard absent after login; route=${new URL(page.url()).pathname}; alerts=${notices.join(" | ")}`,
    );
  }
  const cookies = await page
    .context()
    .cookies("https://api.subtrack.test:8443/api/v1/auth");
  const refresh = cookies.find((value) => value.name === "subtrack_refresh")!;
  expect(refresh.httpOnly && refresh.secure).toBeTruthy();
  expect(refresh.sameSite).toBe("Strict");
  expect(refresh.domain).toBe("api.subtrack.test");
  expect(
    await page.evaluate(() => sessionStorage.getItem("subtrack.session")),
  ).toBeNull();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your recurring spend" }),
  ).toBeVisible();
  const rotated = (await page.context().cookies()).find(
    (value) => value.name === "subtrack_refresh",
  )!;
  expect(rotated.value).not.toBe(refresh.value);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send a new code" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "If this address is eligible" }),
  ).toContainText("If this address is eligible");
  await page.getByLabel("Single-use code").fill(await deliveredCode("reset"));
  await page.getByLabel("New password").fill(replacement);
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Password changed" }),
  ).toContainText("Password changed");
  await page.getByRole("link", { name: "Back to sign in" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(replacement);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Sign out everywhere" }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Good to see you" }),
  ).toBeVisible();
});
