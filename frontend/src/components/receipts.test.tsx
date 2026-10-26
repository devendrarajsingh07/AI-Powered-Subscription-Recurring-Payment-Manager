import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import { authHandlers } from "../auth-test-handlers";
import { ReceiptImport } from "./ReceiptImport";
import UploadPage from "../pages/Upload";

type Job = components["schemas"]["StatementPreviewOut"];
const job: Job = {
  id: "00000000-0000-4000-8000-000000000001",
  filename: "receipt.eml",
  source_type: "email_receipt",
  status: "ready",
  stage: "review_required",
  processed_pages: 1,
  total_pages: 1,
  expires_at: "2030-01-01T00:00:00Z",
  error_code: null,
  error_message: null,
  upload_id: null,
  result: {
    source_type: "email_receipt",
    page_count: 1,
    flagged_count: 1,
    warnings: [],
    reconciliation: {
      status: "unavailable",
      balance_checks: 0,
      total_checks: 0,
      opening: null,
      closing: null,
    },
    rows: [
      {
        index: 0,
        page: 1,
        date: "2026-07-01",
        description: "netflix",
        amount: "499.00",
        type: "debit",
        balance: null,
        confidence: "0.00",
        field_confidence: {},
        flags: [
          "email_review_required",
          "email_authenticity_unverified",
          "not_bank_reconciled",
        ],
      },
    ],
  },
};
const server = setupServer(
  ...authHandlers,
  http.get("*/api/v1/uploads", () =>
    HttpResponse.json({
      items: [],
      total: 0,
      offset: 0,
      limit: 10,
    } satisfies components["schemas"]["Page_UploadOut_"]),
  ),
  http.post("*/api/v1/receipts/preview", () => HttpResponse.json(job)),
  http.get("*/api/v1/uploads/previews/:id", () => HttpResponse.json(job)),
  http.delete("*/api/v1/uploads/previews/:id", () =>
    HttpResponse.json({
      ...job,
      status: "cancelled",
      result: null,
    } satisfies Job),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());
function mount(ui?: React.ReactNode) {
  const imported = vi.fn();
  const result = render(
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
      <MemoryRouter>
        {ui || <ReceiptImport onImported={imported} />}
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, imported };
}
async function choose() {
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Choose synthetic receipt"),
    new File(["synthetic"], "receipt.eml", { type: "message/rfc822" }),
  );
  await screen.findByRole("heading", { name: "Review receipt payment" });
  return user;
}
test("receipt review requires approval, edits clear approval, and only reviewed fields are posted", async () => {
  let submitted: FormData | undefined;
  server.use(
    http.post("*/api/v1/uploads", async ({ request }) => {
      submitted = await request.formData();
      return HttpResponse.json({
        id: "imported-receipt",
        source: "upload",
        source_type: "email_receipt",
        filename: "receipt.eml",
        row_count: 1,
        status: "pending",
        stage: "queued",
        processed_rows: 0,
        total_rows: 1,
        inserted_count: 0,
        duplicate_count: 0,
        malformed_count: 0,
        detected_count: 0,
        excluded_count: 0,
        warnings: [],
        error_message: null,
        uploaded_at: "2026-10-18T00:00:00Z",
        remainder_notice:
          "Unreadable remainder counts as one malformed record.",
      } satisfies components["schemas"]["UploadOut"]);
    }),
  );
  const ui = mount();
  const user = await choose();
  const button = screen.getByRole("button", { name: "Import reviewed rows" });
  expect(button).toBeDisabled();
  await user.click(screen.getByLabelText("Verify row 1"));
  expect(button).toBeEnabled();
  await user.clear(screen.getByLabelText("Row 1 amount"));
  await user.type(screen.getByLabelText("Row 1 amount"), "1499.50");
  expect(screen.getByLabelText("Verify row 1")).not.toBeChecked();
  expect(button).toBeDisabled();
  await user.click(screen.getByLabelText("Verify row 1"));
  await user.click(button);
  await waitFor(() =>
    expect(ui.imported).toHaveBeenCalledWith("imported-receipt"),
  );
  expect([...submitted!.keys()].sort()).toEqual(["edits", "preview_id"]);
  expect(JSON.parse(String(submitted!.get("edits")))).toEqual([
    { index: 0, verified: true, amount: "1499.50" },
  ]);
});
test("removing every receipt row does not permit an empty import; cancel returns to picker", async () => {
  mount();
  const user = await choose();
  await user.click(screen.getByRole("button", { name: "Remove row 1" }));
  expect(
    screen.getByRole("button", { name: "Import reviewed rows" }),
  ).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Cancel preview" }));
  expect(
    await screen.findByLabelText("Choose synthetic receipt"),
  ).toBeVisible();
});
test.each(["light", "dark"])(
  "receipt review is accessible plain text in %s, without embedding email content",
  async (theme) => {
    document.documentElement.dataset.theme = theme;
    const hostile = "<img src=x onerror=steal()>";
    server.use(
      http.get("*/api/v1/uploads/previews/:id", () =>
        HttpResponse.json({
          ...job,
          result: {
            ...job.result!,
            rows: [{ ...job.result!.rows[0], description: hostile }],
          },
        } satisfies Job),
      ),
    );
    const ui = mount();
    await choose();
    expect(screen.getByDisplayValue(hostile)).toBeVisible();
    expect(ui.container.querySelector("iframe, img, script")).toBeNull();
    expect(screen.queryByText(/Confidence 0/)).toBeNull();
    expect(screen.getByText(/Needs approval/)).toBeVisible();
    expect((await axe(ui.container)).violations).toEqual([]);
  },
);
test.each([
  ["receipt.txt", "synthetic", "Choose a synthetic .eml"],
  ["receipt.eml", "x".repeat(1024 * 1024 + 1), "1 MB limit"],
])(
  "invalid local selection %s never calls preview",
  async (name, body, message) => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/receipts/preview", () => {
        calls++;
        return HttpResponse.json(job);
      }),
    );
    mount();
    await userEvent
      .setup({ applyAccept: false })
      .upload(
        screen.getByLabelText("Choose synthetic receipt"),
        new File([body], name),
      );
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(calls).toBe(0);
  },
);
test.each([409, 422, 429])(
  "server %s failure is visible and picker remains retryable",
  async (status) => {
    server.use(
      http.post("*/api/v1/receipts/preview", () =>
        HttpResponse.json(
          {
            error: {
              code: "receipt_error",
              message: "Use a separate empty local account.",
            },
          },
          { status },
        ),
      ),
    );
    mount();
    await userEvent.upload(
      screen.getByLabelText("Choose synthetic receipt"),
      new File(["synthetic"], "receipt.eml"),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      status === 429 ? "try again shortly" : "separate empty local account",
    );
    expect(screen.getByLabelText("Choose synthetic receipt")).toBeEnabled();
  },
);
test.each([false, true])(
  "receipt option respects the server capability %s",
  async (enabled) => {
    server.use(
      http.get("*/api/v1/auth/config", () =>
        HttpResponse.json({
          public_demo_only: false,
          receipt_import_enabled: enabled,
          session_mode: "strict",
          notice: "Synthetic data",
          legal_version: "draft",
          legal_acceptance_required: false,
        } satisfies components["schemas"]["AuthConfig"]),
      ),
    );
    mount(<UploadPage />);
    await screen.findByRole("heading", { name: "Upload a statement" });
    expect(!!screen.queryByLabelText("Import source")).toBe(enabled);
    if (enabled) {
      await userEvent.selectOptions(
        screen.getByLabelText("Import source"),
        "receipt",
      );
      expect(screen.getByLabelText("Choose synthetic receipt")).toBeVisible();
      expect(screen.queryByLabelText("Choose statement file")).toBeNull();
    }
  },
);

test("public demo never exposes receipt file selection even if capability is erroneously true", async () => {
  server.use(
    http.get("*/api/v1/auth/config", () =>
      HttpResponse.json({
        public_demo_only: true,
        receipt_import_enabled: true,
        session_mode: "demo",
        notice: "Synthetic only",
        legal_version: "draft",
        legal_acceptance_required: false,
      } satisfies components["schemas"]["AuthConfig"]),
    ),
  );
  mount(<UploadPage />);
  await screen.findByRole("heading", { name: "Synthetic demo data" });
  expect(screen.queryByLabelText("Import source")).toBeNull();
  expect(screen.queryByLabelText("Choose synthetic receipt")).toBeNull();
});
