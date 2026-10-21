import { authHandlers } from "../auth-test-handlers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import { DemoPanel } from "./DemoPanel";
import { applyTheme, readTheme } from "../lib/theme";

const upload: components["schemas"]["UploadOut"] = {
  source_type: "csv",
  excluded_count: 0,
  source: "demo",
  demo_as_of: "2026-10-18",
  id: "demo-id",
  filename: "demo.csv",
  row_count: 3,
  status: "done",
  stage: "done",
  processed_rows: 3,
  total_rows: 3,
  inserted_count: 3,
  duplicate_count: 0,
  malformed_count: 0,
  detected_count: 1,
  warnings: [],
  error_message: null,
  uploaded_at: "2026-10-18T00:00:00Z",
  remainder_notice: "Unreadable remainder is reported.",
};
const empty: components["schemas"]["Page_UploadOut_"] = {
  items: [],
  total: 0,
  limit: 100,
  offset: 0,
};
const server = setupServer(
  ...authHandlers,
  http.get("*/api/v1/uploads", () => HttpResponse.json(empty)),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
  localStorage.clear();
});
afterAll(() => server.close());
function show() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <DemoPanel settings />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("load demo is accessible and shows real upload result", async () => {
  server.use(
    http.post("*/api/v1/demo/load", () => HttpResponse.json(upload)),
    http.get("*/api/v1/uploads/demo-id", () => HttpResponse.json(upload)),
  );
  const view = show();
  await userEvent.click(
    await screen.findByRole("button", { name: "Load demo data" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Statement processed" }),
  ).toBeVisible();
  expect((await axe(view.container)).violations).toEqual([]);
});
test("demo load failure is safe and retry stays available", async () => {
  server.use(
    http.post("*/api/v1/demo/load", () =>
      HttpResponse.json(
        { error: { code: "disabled", message: "Demo loading is disabled" } },
        { status: 404 },
      ),
    ),
  );
  show();
  await userEvent.click(
    await screen.findByRole("button", { name: "Load demo data" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Demo loading is disabled",
  );
  expect(screen.getByRole("button", { name: "Load demo data" })).toBeEnabled();
});
test("demo badge and removal require explicit confirmation", async () => {
  server.use(
    http.get("*/api/v1/uploads", () =>
      HttpResponse.json({
        ...empty,
        items: [upload],
        total: 1,
      } satisfies components["schemas"]["Page_UploadOut_"]),
    ),
  );
  let removed = false;
  server.use(
    http.delete("*/api/v1/demo/data", () => {
      removed = true;
      return HttpResponse.json({
        deleted: { uploads: 1 },
      } satisfies components["schemas"]["DeleteResult"]);
    }),
  );
  show();
  expect(await screen.findByText("Demo data")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Remove demo data" }),
  );
  expect(removed).toBe(false);
  await userEvent.click(
    screen.getByRole("button", { name: "Confirm remove demo" }),
  );
  await waitFor(() => expect(removed).toBe(true));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Demo data removed",
  );
});
test("theme stores only valid preferences and survives storage denial", () => {
  localStorage.setItem("subtrack.theme", "invalid");
  expect(readTheme()).toBe("system");
  applyTheme("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(readTheme()).toBe("dark");
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  expect(readTheme()).toBe("system");
  expect(() => applyTheme("light")).not.toThrow();
});
