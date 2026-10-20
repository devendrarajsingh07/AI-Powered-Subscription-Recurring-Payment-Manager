import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import { Auth, passwordError } from "../pages/Auth";
import UploadPage, {
  mappingForLayout,
  mappingValid,
  UploadProgress,
} from "../pages/Upload";
import { DeleteDialog } from "../pages/Settings";
import { filtersFromSearch } from "../pages/Subscriptions";
import { Dialog, Notices } from "./Common";
import { clearSession, saveSession } from "../lib/session";
import { api } from "../api/client";
import { App } from "../App";
import Categories from "../pages/Categories";
const server = setupServer(
  http.get("*/api/v1/uploads", () =>
    HttpResponse.json({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    } satisfies components["schemas"]["Page_UploadOut_"]),
  ),
  http.get("*/api/v1/alerts", () =>
    HttpResponse.json({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    } satisfies components["schemas"]["Page_AlertOut_"]),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  clearSession();
  sessionStorage.clear();
});
afterAll(() => server.close());
function wrapper(ui: React.ReactNode, path = "/login") {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
const upload: components["schemas"]["UploadOut"] = {
  source_type: "csv",
  excluded_count: 0,
  source: "upload",
  id: "upload-1",
  filename: "synthetic.csv",
  row_count: 3,
  total_rows: 3,
  processed_rows: 0,
  status: "pending",
  stage: "queued",
  inserted_count: 0,
  duplicate_count: 0,
  malformed_count: 0,
  detected_count: 0,
  warnings: [],
  error_message: null,
  uploaded_at: "2026-10-18T00:00:00Z",
  remainder_notice: "Unreadable remainder counts as one malformed record.",
};
const subscription: components["schemas"]["SubscriptionOut"] = {
  id: "sub-1",
  merchant: "example",
  category: "unknown",
  kind: "subscription",
  currency: "INR",
  cadence: "monthly",
  avg_amount: "199.00",
  confidence: "0.72",
  regularity: "1",
  amount_cv: "0",
  occurrences: 3,
  last_charge: "2026-10-01",
  next_expected: "2026-10-31",
  status: "active",
  user_confirmed: false,
  requires_confirmation: true,
  cancelled_at: null,
  last_used_at: null,
  possibly_cancelled: true,
  missed_cycles: 2,
  price_increase: {
    previous_amount: "180.00",
    new_amount: "199.00",
    detected_on: "2026-10-01",
  },
};
test("password validation mirrors backend character classes and UTF-8 limit", () => {
  expect(passwordError("longlowercaseonly", true)).toMatch(/three/);
  expect(passwordError("ValidPassword42!", true)).toBeNull();
  expect(passwordError("é".repeat(37), false)).toMatch(/72/);
  expect(passwordError("", false)).toMatch(/Enter/);
});
test("login handles generic invalid credentials via real network client", async () => {
  server.use(
    http.post("*/api/v1/auth/login", () =>
      HttpResponse.json(
        {
          error: {
            code: "invalid_credentials",
            message: "Invalid credentials",
          },
        } satisfies components["schemas"]["ErrorEnvelope"],
        { status: 401 },
      ),
    ),
  );
  wrapper(<Auth />);
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "person@example.org",
  );
  await userEvent.type(screen.getByLabelText("Password"), "WrongPassword42!");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unable to sign in. Check your email and password.",
  );
});
test("rate limiting gets friendly retry wording", async () => {
  server.use(
    http.post("*/api/v1/auth/login", () =>
      HttpResponse.json(
        {
          error: { code: "rate_limited", message: "Limited" },
        } satisfies components["schemas"]["ErrorEnvelope"],
        { status: 429 },
      ),
    ),
  );
  wrapper(<Auth />);
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "person@example.org" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "WrongPassword42!" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "try again shortly",
  );
});
test("register then login uses normalized email and preserves intended destination", async () => {
  let body: components["schemas"]["Register"] | undefined;
  server.use(
    http.post("*/api/v1/auth/register", async ({ request }) => {
      body = (await request.json()) as components["schemas"]["Register"];
      return HttpResponse.json(
        {
          id: "user",
          email: body.email,
          created_at: "2026-10-18T00:00:00Z",
        } satisfies components["schemas"]["UserOut"],
        { status: 201 },
      );
    }),
    http.post("*/api/v1/auth/login", () =>
      HttpResponse.json({
        access_token: "test-token",
        expires_in: 300,
        token_type: "bearer",
      } satisfies components["schemas"]["Token"]),
    ),
  );
  wrapper(
    <Routes>
      <Route path="/register" element={<Auth register />} />
      <Route path="/" element={<p>Signed in workspace</p>} />
    </Routes>,
    "/register",
  );
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "PERSON@example.org" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "ValidPassword42!" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Signed in workspace")).toBeVisible();
  expect(body?.email).toBe("person@example.org");
});
test("a protected 401 clears the stored session", async () => {
  saveSession({
    access_token: "test-token",
    token_type: "bearer",
    expires_in: 300,
  });
  server.use(
    http.get("*/api/v1/budget", () =>
      HttpResponse.json(
        {
          error: { code: "unauthorized", message: "Unauthorized" },
        } satisfies components["schemas"]["ErrorEnvelope"],
        { status: 401 },
      ),
    ),
  );
  await expect(api.GET("/api/v1/budget")).rejects.toThrow("Unauthorized");
  expect(sessionStorage.getItem("subtrack.session")).toBeNull();
});
test("single and split mappings never submit mixed layouts or duplicate columns", () => {
  const mapping = {
    date: "Date",
    description: "Narration",
    amount: "Amount",
    type: "Type",
    debit: "Withdrawal",
    credit: "Deposit",
    currency: "",
  };
  expect(mappingForLayout(mapping, "single")).toEqual({
    date: "Date",
    description: "Narration",
    amount: "Amount",
    type: "Type",
  });
  expect(mappingForLayout(mapping, "split")).toEqual({
    date: "Date",
    description: "Narration",
    debit: "Withdrawal",
    credit: "Deposit",
  });
  expect(mappingValid(mapping, "split")).toBe(true);
  expect(mappingValid({ ...mapping, type: "Amount" }, "single")).toBe(false);
  expect(mappingValid({ date: "Date" }, "single")).toBe(false);
});
test.each(["pending", "processing", "done", "failed"] as const)(
  "upload progress renders %s and real counters",
  (status) => {
    wrapper(
      <UploadProgress
        upload={{
          ...upload,
          status,
          stage: status,
          inserted_count: status === "done" ? 3 : 0,
          processed_rows: status === "done" ? 3 : 0,
          error_message: status === "failed" ? "Safe upload failure" : null,
        }}
      />,
    );
    expect(screen.getByLabelText("Upload progress")).toHaveTextContent(status);
    if (status === "done")
      expect(screen.getByText("Inserted").previousSibling).toHaveTextContent(
        "3",
      );
    if (status === "failed")
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Safe upload failure",
      );
  },
);
test("uncertainty and price increase are notices rather than cancellation claims", () => {
  render(<Notices item={subscription} />);
  expect(screen.getByText(/May have stopped/)).toBeVisible();
  expect(screen.getByText(/Possible price increase/)).toHaveTextContent(
    "₹180.00 → ₹199.00",
  );
  expect(screen.getByText("Needs category confirmation")).toBeVisible();
});
test("server filters, decimal sort, direction and pagination are URL state", () => {
  expect(
    filtersFromSearch(
      new URLSearchParams(
        "sort=avg_amount&direction=desc&status=dismissed&cadence=yearly&kind=fixed_bill&offset=20",
      ),
    ),
  ).toMatchObject({
    sort: "avg_amount",
    direction: "desc",
    status: "dismissed",
    cadence: "yearly",
    kind: "fixed_bill",
    offset: 20,
    limit: 20,
  });
  expect(
    filtersFromSearch(
      new URLSearchParams("offset=-20&sort=injected&status=missing"),
    ),
  ).toMatchObject({ offset: 0, sort: "merchant", status: undefined });
});
test("dialog focuses its close button and restores the invoking control", async () => {
  const trigger = document.createElement("button");
  document.body.append(trigger);
  trigger.focus();
  const view = wrapper(
    <Dialog title="Details" onClose={() => {}}>
      <p>Charge list</p>
    </Dialog>,
  );
  expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();
  view.unmount();
  expect(trigger).toHaveFocus();
  trigger.remove();
});
test("delete is gated by the exact typed word", async () => {
  wrapper(<DeleteDialog onClose={() => {}} />);
  const button = screen.getByRole("button", {
    name: "Permanently delete data",
  });
  expect(button).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Confirmation word"), "delete");
  expect(button).toBeDisabled();
  await userEvent.clear(screen.getByLabelText("Confirmation word"));
  await userEvent.type(screen.getByLabelText("Confirmation word"), "DELETE");
  expect(button).toBeEnabled();
});
test("upload preview uses generated network types and lets user switch amount layout", async () => {
  const preview: components["schemas"]["Preview"] = {
    columns: ["Date", "Narration", "Withdrawal", "Deposit"],
    suggested_mapping: {
      date: "Date",
      description: "Narration",
      debit: "Withdrawal",
      credit: "Deposit",
    },
    rows: [["01/10/2026", "example", "199.00", ""]],
    row_count: 1,
    malformed_csv: false,
    delimiter: ",",
    date_formats: ["DD/MM/YYYY"],
    warnings: [],
    malformed_count: 0,
    remainder_notice: "Unreadable remainder",
  };
  server.use(
    http.get("*/api/v1/uploads", () =>
      HttpResponse.json({
        items: [],
        total: 0,
        limit: 10,
        offset: 0,
      } satisfies components["schemas"]["Page_UploadOut_"]),
    ),
    http.post("*/api/v1/uploads/preview", () => HttpResponse.json(preview)),
  );
  wrapper(<UploadPage />);
  await userEvent.upload(
    screen.getByLabelText("Choose statement file"),
    new File(["date,description\n"], "sample.csv", { type: "text/csv" }),
  );
  expect(await screen.findByLabelText("Map debit")).toHaveValue("Withdrawal");
  expect(
    screen.getByRole("button", { name: "Confirm and import" }),
  ).toBeEnabled();
  await userEvent.selectOptions(
    screen.getByLabelText("Amount layout"),
    "single",
  );
  expect(screen.queryByLabelText("Map debit")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Map amount")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Confirm and import" }),
  ).toBeDisabled();
});
test("auth and delete dialog have no automated accessibility violations", async () => {
  const auth = wrapper(<Auth register />);
  expect(
    (
      await axe(auth.container, {
        rules: { "color-contrast": { enabled: false } },
      })
    ).violations,
  ).toEqual([]);
  auth.unmount();
  const dialog = wrapper(<DeleteDialog onClose={() => {}} />);
  await waitFor(() => expect(screen.getByRole("dialog")).toBeVisible());
  expect(
    (
      await axe(dialog.container, {
        rules: { "color-contrast": { enabled: false } },
      })
    ).violations,
  ).toEqual([]);
});
test("delete receipt survives protected-route redirect and cache is cleared", async () => {
  saveSession({
    access_token: "test-token",
    token_type: "bearer",
    expires_in: 300,
  });
  server.use(
    http.get("*/api/v1/auth/me", () =>
      HttpResponse.json({
        id: "user",
        email: "person@example.org",
        created_at: "2026-10-18T00:00:00Z",
      } satisfies components["schemas"]["UserOut"]),
    ),
    http.get("*/api/v1/budget", () =>
      HttpResponse.json({
        monthly_limit: null,
        currency: "INR",
      } satisfies components["schemas"]["BudgetOut"]),
    ),
    http.get("*/api/v1/settings/alerts", () =>
      HttpResponse.json({
        lead_time_days: 3,
        enabled: true,
        notification_email: null,
        delivery_mode: "console",
        delivery_notice: "Development mode: private outbox.",
      } satisfies components["schemas"]["AlertSettingsOut"]),
    ),
    http.delete("*/api/v1/me/data", () =>
      HttpResponse.json({
        deleted: { users: 1, transactions: 399 },
      } satisfies components["schemas"]["DeleteResult"]),
    ),
  );
  wrapper(<App />, "/settings");
  await userEvent.click(
    await screen.findByRole("button", { name: "Delete my data" }),
  );
  await userEvent.type(screen.getByLabelText("Confirmation word"), "DELETE");
  await userEvent.click(
    screen.getByRole("button", { name: "Permanently delete data" }),
  );
  expect(
    await screen.findByText("Your account and data were deleted."),
  ).toBeVisible();
  expect(screen.getByText("Deleted data counts")).toBeVisible();
  expect(screen.getByText("399")).toBeVisible();
  expect(sessionStorage.getItem("subtrack.session")).toBeNull();
});
test("protected routes keep the intended destination for sign-in", async () => {
  wrapper(<App />, "/subscriptions?status=dismissed");
  expect(
    await screen.findByRole("heading", { name: "Good to see you" }),
  ).toBeVisible();
  server.use(
    http.post("*/api/v1/auth/login", () =>
      HttpResponse.json({
        access_token: "test-token",
        expires_in: 300,
        token_type: "bearer",
      } satisfies components["schemas"]["Token"]),
    ),
    http.get("*/api/v1/auth/me", () =>
      HttpResponse.json({
        id: "user",
        email: "person@example.org",
        created_at: "2026-10-18T00:00:00Z",
      } satisfies components["schemas"]["UserOut"]),
    ),
    http.get("*/api/v1/subscriptions", ({ request }) => {
      expect(new URL(request.url).searchParams.get("status")).toBe("dismissed");
      return HttpResponse.json({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      } satisfies components["schemas"]["Page_SubscriptionOut_"]);
    }),
  );
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "person@example.org",
  );
  await userEvent.type(screen.getByLabelText("Password"), "ValidPassword42!");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByLabelText("Status")).toHaveValue("dismissed");
  expect(
    await screen.findByText(/No payments match these filters/),
  ).toBeVisible();
});
test("unknown merchant categories require a deliberate choice and use the scoped API", async () => {
  let confirmed = false;
  const item: components["schemas"]["CategoryOut"] = {
    id: "category-1",
    merchant: "synthetic merchant",
    category: "unknown",
    source: "rule",
    confirmed: false,
    suggestion_attempted: false,
  };
  server.use(
    http.get("*/api/v1/categories/unconfirmed", () =>
      HttpResponse.json({
        items: confirmed ? [] : [item],
        total: confirmed ? 0 : 1,
        limit: 20,
        offset: 0,
      } satisfies components["schemas"]["Page_CategoryOut_"]),
    ),
    http.patch("*/api/v1/categories/category-1", async ({ request }) => {
      expect(await request.json()).toEqual({ category: "cloud" });
      confirmed = true;
      return HttpResponse.json({
        ...item,
        category: "cloud",
        source: "user",
        confirmed: true,
      } satisfies components["schemas"]["CategoryOut"]);
    }),
  );
  wrapper(<Categories />);
  const select = await screen.findByLabelText(
    "Category for synthetic merchant",
  );
  const button = screen.getByRole("button", { name: "Confirm category" });
  expect(button).toBeDisabled();
  await userEvent.selectOptions(select, "cloud");
  await userEvent.click(button);
  expect(
    await screen.findByText("No merchants need category confirmation."),
  ).toBeVisible();
});
