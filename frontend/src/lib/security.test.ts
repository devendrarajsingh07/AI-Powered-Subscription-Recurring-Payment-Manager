import { expect, test } from "vitest";
import config from "../../vercel.json";

test("the deployed static host has a restrictive CSP with only the configured demo API", () => {
  const header = config.headers[0].headers.find(
    (h) => h.key === "Content-Security-Policy",
  );
  expect(header).toBeDefined();
  const policy = Object.fromEntries(
    header!.value.split(";").map((part) => {
      const [name, ...values] = part.trim().split(/\s+/);
      return [name, values.join(" ")];
    }),
  );
  expect(policy["script-src"]).toBe("'self'");
  expect(policy["frame-ancestors"]).toBe("'none'");
  expect(policy["object-src"]).toBe("'none'");
  expect(policy["connect-src"]).toBe(
    "'self' https://ai-powered-subscription-recurring.onrender.com",
  );
});
