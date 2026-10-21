import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import { authHandlers } from "../auth-test-handlers";
import {
  clearSession,
  getToken,
  logout,
  refreshSession,
  saveSession,
} from "../lib/session";
import { Auth } from "../pages/Auth";
import { AccountRecovery } from "../pages/AccountRecovery";
import { PublicDemoNotice } from "./AuthMode";
import UploadPage from "../pages/Upload";
import { App } from "../App";

const server = setupServer(...authHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
  sessionStorage.clear();
  localStorage.clear();
});
afterAll(() => server.close());
const token = {
  access_token: "synthetic-access",
  token_type: "bearer",
  expires_in: 300,
  csrf_token: "synthetic-csrf",
} satisfies components["schemas"]["Token"];
function view(ui: React.ReactNode, path = "/login") {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
function demo() {
  server.use(
    http.get("*/api/v1/auth/config", () =>
      HttpResponse.json({
        public_demo_only: true,
        session_mode: "demo",
        notice: "Public demo — do not upload real statements or personal data",
      } satisfies components["schemas"]["AuthConfig"]),
    ),
  );
}

test("access token and CSRF stay out of browser storage", () => {
  saveSession(token);
  expect(getToken()).toBe(token.access_token);
  expect(sessionStorage.length).toBe(0);
  expect(localStorage.length).toBe(0);
  clearSession();
  expect(getToken()).toBeUndefined();
});

test("expired access can still revoke the refresh family using CSRF cookie logout", async () => {
  saveSession({ ...token, expires_in: -1 });
  let revoked = false;
  server.use(
    http.post("*/api/v1/auth/logout-cookie", ({ request }) => {
      expect(request.credentials).toBe("include");
      expect(request.headers.get("X-CSRF-Token")).toBe(token.csrf_token);
      revoked = true;
      return HttpResponse.json({
        message: "Signed out",
      } satisfies components["schemas"]["MessageResult"]);
    }),
  );
  await logout();
  expect(revoked).toBe(true);
  expect(getToken()).toBeUndefined();
});

test("parallel refresh callers share one rotating request with cookie and CSRF", async () => {
  let count = 0;
  server.use(
    http.post("*/api/v1/auth/csrf", () =>
      HttpResponse.json({
        csrf_token: "synthetic-csrf",
      } satisfies components["schemas"]["CsrfResult"]),
    ),
    http.post("*/api/v1/auth/refresh", ({ request }) => {
      count++;
      expect(request.credentials).toBe("include");
      expect(request.headers.get("X-CSRF-Token")).toBe("synthetic-csrf");
      return HttpResponse.json(token);
    }),
  );
  expect(await Promise.all([refreshSession(), refreshSession()])).toEqual([
    true,
    true,
  ]);
  expect(count).toBe(1);
  expect(getToken()).toBe(token.access_token);
});

test("demo mode never attempts cookie bootstrap or refresh", async () => {
  demo();
  expect(await refreshSession()).toBe(false);
  expect(getToken()).toBeUndefined();
});

test("logout-everywhere revokes on server; failed revocation can be retried", async () => {
  saveSession(token);
  server.use(
    http.post(
      "*/api/v1/auth/logout-all",
      () => new HttpResponse(null, { status: 503 }),
    ),
  );
  await expect(logout(true)).rejects.toThrow("retry");
  expect(getToken()).toBe(token.access_token);
  server.use(
    http.post("*/api/v1/auth/logout-all", ({ request }) => {
      expect(request.headers.get("Authorization")).toBe(
        `Bearer ${token.access_token}`,
      );
      return HttpResponse.json({
        message: "All sessions revoked",
      } satisfies components["schemas"]["MessageResult"]);
    }),
  );
  await logout(true);
  expect(getToken()).toBeUndefined();
});

test("public demo offers isolated session without email/password or upload control", async () => {
  demo();
  server.use(http.post("*/api/v1/auth/demo", () => HttpResponse.json(token)));
  view(
    <>
      <PublicDemoNotice />
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="/" element={<p>Isolated workspace</p>} />
      </Routes>
    </>,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Start isolated demo" }),
  );
  expect(await screen.findByText("Isolated workspace")).toBeVisible();
  expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Public demo notice")).toHaveTextContent(
    "do not upload real statements",
  );
});

test("public upload route exposes synthetic loader only", async () => {
  demo();
  server.use(
    http.get("*/api/v1/uploads", () =>
      HttpResponse.json({
        items: [],
        total: 0,
        limit: 100,
        offset: 0,
      } satisfies components["schemas"]["Page_UploadOut_"]),
    ),
  );
  view(<UploadPage />);
  expect(await screen.findByText("Synthetic demo data")).toBeVisible();
  expect(screen.queryByLabelText(/Choose.*file/i)).not.toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Load demo data" }),
  ).toBeVisible();
});

test("registration requiring verification does not attempt login", async () => {
  server.use(
    http.post("*/api/v1/auth/register", () =>
      HttpResponse.json(
        {
          id: "synthetic",
          email: "person@example.org",
          created_at: "2026-10-21T00:00:00Z",
          email_verified: false,
          verification_required: true,
        } satisfies components["schemas"]["UserOut"],
        { status: 201 },
      ),
    ),
  );
  view(
    <Routes>
      <Route path="/register" element={<Auth register />} />
      <Route path="/verify-email" element={<p>Verify next</p>} />
    </Routes>,
    "/register",
  );
  await userEvent.type(
    await screen.findByLabelText("Email address"),
    "person@example.org",
  );
  await userEvent.type(
    screen.getByLabelText("Password"),
    "SyntheticVisitor42!",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Verify next")).toBeVisible();
  expect(getToken()).toBeUndefined();
});

test("recovery shows generic delivery result and accessible code form", async () => {
  server.use(
    http.post("*/api/v1/auth/password/request", () =>
      HttpResponse.json(
        {
          message:
            "If this address is eligible, an email will arrive with a single-use code",
        } satisfies components["schemas"]["MessageResult"],
        { status: 202 },
      ),
    ),
  );
  const { container } = view(<AccountRecovery kind="reset" />);
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "missing@example.org",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Send a new code" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "If this address is eligible",
  );
  expect((await axe(container)).violations).toEqual([]);
  expect(window.location.search).not.toContain("token");
});

test("recovery route announces the correct page title", async () => {
  view(<App />, "/reset-password");
  expect(
    await screen.findByRole("heading", { name: "Reset your password" }),
  ).toBeVisible();
  expect(document.title).toBe("Reset password · SubTrack");
});
