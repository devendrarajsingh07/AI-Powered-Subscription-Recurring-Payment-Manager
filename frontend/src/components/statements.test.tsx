import { authHandlers } from "../auth-test-handlers";
import { StrictMode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  expect,
  test,
  vi,
} from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import { reviewComplete, StatementReview } from "./StatementReview";
import { saveSession, clearSession } from "../lib/session";

type Job = components["schemas"]["StatementPreviewOut"];
const row: components["schemas"]["ExtractedRow"] = {
  index: 0,
  date: "2026-10-18",
  description: "Synthetic merchant",
  amount: "119.00",
  type: "debit",
  page: 1,
  confidence: "98.00",
  field_confidence: { amount: "98.00" },
  flags: ["Review extracted row"],
  balance: "100.00",
};
const job: Job = {
  id: "00000000-0000-4000-8000-000000000001",
  filename: "synthetic.pdf",
  status: "ready",
  stage: "review",
  source_type: "pdf_text",
  processed_pages: 1,
  total_pages: 1,
  expires_at: "2030-01-01T00:00:00Z",
  error_code: null,
  error_message: null,
  upload_id: null,
  result: {
    rows: [row],
    source_type: "pdf_text",
    page_count: 1,
    flagged_count: 1,
    reconciliation: {
      status: "unavailable",
      balance_checks: 0,
      total_checks: 0,
      opening: null,
      closing: null,
    },
    warnings: ["Review all extracted values."],
  },
};
const server = setupServer(
  ...authHandlers,
  http.get("*/api/v1/uploads/previews/:id", () => HttpResponse.json(job)),
  http.delete("*/api/v1/uploads/previews/:id", () =>
    HttpResponse.json({
      ...job,
      status: "cancelled",
      result: null,
    } satisfies Job),
  ),
);
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  URL.createObjectURL = vi.fn(() => "blob:synthetic-local");
  URL.revokeObjectURL = vi.fn();
});
beforeEach(() =>
  saveSession({
    access_token: "synthetic-test-token",
    expires_in: 3600,
    token_type: "bearer",
  }),
);
afterEach(() => {
  clearSession();
  server.resetHandlers();
  vi.clearAllMocks();
});
afterAll(() => server.close());
function mount() {
  const imported = vi.fn();
  const cancelled = vi.fn();
  const retry = vi.fn();
  const ui = render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <StrictMode>
        <StatementReview
          jobId={job.id}
          file={
            new File(["synthetic"], "synthetic.pdf", {
              type: "application/pdf",
            })
          }
          onImported={imported}
          onCancel={cancelled}
          onRetry={retry}
        />
      </StrictMode>
    </QueryClientProvider>,
  );
  return { ...ui, imported, cancelled, retry };
}

test("flagged rows cannot import without explicit review; corrected values go as strings", async () => {
  let submitted: Partial<components["schemas"]["RowEdit"]>[] = [];
  server.use(
    http.post("*/api/v1/uploads", async ({ request }) => {
      const form = await request.formData();
      submitted = JSON.parse(String(form.get("edits")));
      expect(form.get("file")).toBeNull();
      return HttpResponse.json({
        id: "00000000-0000-4000-8000-000000000002",
        source: "upload",
        source_type: "pdf_text",
        excluded_count: 0,
        filename: "synthetic.pdf",
        row_count: 1,
        status: "pending",
        stage: "queued",
        processed_rows: 0,
        total_rows: 1,
        inserted_count: 0,
        duplicate_count: 0,
        malformed_count: 0,
        detected_count: 0,
        warnings: [],
        error_message: null,
        uploaded_at: "2026-10-18T00:00:00Z",
        remainder_notice:
          "Unreadable remainder counts as one malformed record.",
      } satisfies components["schemas"]["UploadOut"]);
    }),
  );
  const ui = mount();
  const user = userEvent.setup();
  expect(
    await screen.findByRole("button", { name: "Import reviewed rows" }),
  ).toBeDisabled();
  const input = screen.getByLabelText("Row 1 amount");
  await user.clear(input);
  await user.type(input, "149.00");
  expect(
    screen.getByRole("button", { name: "Import reviewed rows" }),
  ).toBeDisabled();
  await user.click(screen.getByLabelText("Verify row 1"));
  await user.click(
    screen.getByRole("button", { name: "Import reviewed rows" }),
  );
  await waitFor(() =>
    expect(ui.imported).toHaveBeenCalledWith(
      "00000000-0000-4000-8000-000000000002",
    ),
  );
  expect(submitted).toEqual([{ index: 0, verified: true, amount: "149.00" }]);
});

test("bulk acknowledgement, remove/undo, filtering and object URL cleanup", async () => {
  const ui = mount();
  const user = userEvent.setup();
  await screen.findByLabelText("Verify row 1");
  await user.click(screen.getByRole("button", { name: "Remove row 1" }));
  expect(
    screen.getByRole("button", { name: "Import reviewed rows" }),
  ).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Undo remove row 1" }));
  expect(
    screen.getByRole("button", { name: "Import reviewed rows" }),
  ).toBeDisabled();
  await user.click(
    screen.getByRole("button", { name: "I reviewed every extracted row" }),
  );
  await user.click(screen.getByLabelText("Show only unverified flagged rows"));
  expect(screen.getByText(/No rows in this view/)).toBeVisible();
  ui.unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic-local");
});

test.each(["pending", "processing"] as const)(
  "real-progress shape renders %s and cancel",
  async (status) => {
    server.use(
      http.get("*/api/v1/uploads/previews/:id", () =>
        HttpResponse.json({ ...job, status, result: null } satisfies Job),
      ),
    );
    const ui = mount();
    const user = userEvent.setup();
    expect(
      await screen.findByRole("progressbar", { name: "Pages extracted" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancel preview" }));
    await waitFor(() => expect(ui.cancelled).toHaveBeenCalled());
  },
);

test("encrypted failure and server errors have safe guidance and retry", async () => {
  server.use(
    http.get("*/api/v1/uploads/previews/:id", () =>
      HttpResponse.json({
        ...job,
        status: "failed",
        result: null,
        error_code: "password_required",
        error_message: "Enter the PDF password.",
      } satisfies Job),
    ),
  );
  const ui = mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Enter the PDF password.",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Retry local file preview" }),
  );
  expect(ui.retry).toHaveBeenCalled();
});

test.each(["light", "dark"])(
  "plain-text hostile descriptions and accessible review in %s",
  async (theme) => {
    document.documentElement.dataset.theme = theme;
    const hostile = "<script>steal()</script>";
    server.use(
      http.get("*/api/v1/uploads/previews/:id", () =>
        HttpResponse.json({
          ...job,
          result: { ...job.result!, rows: [{ ...row, description: hostile }] },
        } satisfies Job),
      ),
    );
    const ui = mount();
    expect(await screen.findByDisplayValue(hostile)).toBeVisible();
    expect(ui.container.querySelector("script")).toBeNull();
    expect((await axe(ui.container)).violations).toEqual([]);
  },
);

test("empty/invalid row decisions cannot unlock review", () => {
  expect(reviewComplete([row], {})).toBe(false);
  expect(
    reviewComplete([row], { 0: { index: 0, verified: true, amount: null } }),
  ).toBe(false);
  expect(reviewComplete([row], { 0: { index: 0, delete: true } })).toBe(true);
});

test("Strict Mode replay never cancels a new job, but actual unmount does", async () => {
  let cancelled = 0;
  server.use(
    http.delete("*/api/v1/uploads/previews/:id", () => {
      cancelled += 1;
      return HttpResponse.json({
        ...job,
        status: "cancelled",
        result: null,
      } satisfies Job);
    }),
  );
  const ui = mount();
  await screen.findByRole("heading", { name: "Review every extracted row" });
  expect(cancelled).toBe(0);
  ui.unmount();
  await waitFor(() => expect(cancelled).toBe(1));
});
