import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import Recommendations from "../pages/Recommendations";
import { SavingsPanel } from "./SavingsPanel";
import { RecentAlerts } from "./RecentAlerts";

type Recommendation = components["schemas"]["RecommendationOut"];
const record: Recommendation = {
  id: "rec-1",
  type: "duplicate",
  status: "open",
  message: "You may want to review overlapping music plans.",
  subscription_id: null,
  members: [
    {
      subscription_id: "sub-1",
      merchant: "synthetic music",
      category: "music",
      cadence: "monthly",
      avg_amount: "119.00",
      monthly_equivalent: "119.00",
    },
  ],
  est_monthly_saving: "119.00",
  extra_monthly_cost: null,
  percent_change: null,
  accepted_at: null,
  created_at: "2026-10-18T00:00:00Z",
  updated_at: "2026-10-18T00:00:00Z",
};
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function mount(ui: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
function page(items: Recommendation[]) {
  return HttpResponse.json({
    items,
    total: items.length,
    limit: 20,
    offset: 0,
  } satisfies components["schemas"]["Page_RecommendationOut_"]);
}
test("recommendation loading becomes a meaningful empty state", async () => {
  let release!: () => void;
  const barrier = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.use(
    http.get("*/api/v1/recommendations", async () => {
      await barrier;
      return page([]);
    }),
  );
  mount(<Recommendations />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading your data");
  release();
  expect(await screen.findByText(/No recommendations match/)).toBeVisible();
});
test("recommendation API errors have a retry action", async () => {
  server.use(
    http.get("*/api/v1/recommendations", () =>
      HttpResponse.json(
        {
          error: {
            code: "unavailable",
            message: "Could not load recommendations",
          },
        } satisfies components["schemas"]["ErrorEnvelope"],
        { status: 503 },
      ),
    ),
  );
  mount(<Recommendations />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not load recommendations",
  );
  expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
});
test("high cost and price increases show no saving estimate and label extra cost", async () => {
  server.use(
    http.get("*/api/v1/recommendations", () =>
      page([
        {
          ...record,
          id: "high-cost",
          type: "high_cost",
          est_monthly_saving: null,
        },
        {
          ...record,
          id: "price",
          type: "price_increase",
          est_monthly_saving: null,
          extra_monthly_cost: "20.00",
          percent_change: "10.05",
        },
      ]),
    ),
  );
  mount(<Recommendations />);
  expect(await screen.findAllByText("No estimate")).toHaveLength(2);
  expect(screen.getByText("Extra monthly-equivalent cost")).toBeVisible();
  expect(screen.getByText("₹20.00")).toBeVisible();
  expect(screen.getByText(/10.05% price increase/)).toBeVisible();
  expect(screen.queryByText("₹0.00")).not.toBeInTheDocument();
});
test("accept waits for server acknowledgement and records intent only", async () => {
  let accepted = false;
  server.use(
    http.get("*/api/v1/recommendations", () => page(accepted ? [] : [record])),
    http.patch("*/api/v1/recommendations/rec-1", async ({ request }) => {
      expect(await request.json()).toEqual({
        action: "accept",
      } satisfies components["schemas"]["RecommendationPatch"]);
      accepted = true;
      return HttpResponse.json({
        ...record,
        status: "accepted",
        accepted_at: "2026-10-18T01:00:00Z",
      } satisfies Recommendation);
    }),
  );
  mount(<Recommendations />);
  expect(await screen.findByText("₹119.00")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Record review intent" }),
  );
  expect(
    await screen.findByText(
      "Review or cancellation intent recorded. Subscription statuses are unchanged.",
    ),
  ).toBeVisible();
  expect(await screen.findByText(/No recommendations match/)).toBeVisible();
});
test("dismiss and filters use validated network arguments", async () => {
  let dismissed = false;
  server.use(
    http.get("*/api/v1/recommendations", ({ request }) => {
      const params = new URL(request.url).searchParams;
      return page(dismissed && params.get("status") === "open" ? [] : [record]);
    }),
    http.patch("*/api/v1/recommendations/rec-1", async ({ request }) => {
      expect(await request.json()).toEqual({ action: "dismiss" });
      dismissed = true;
      return HttpResponse.json({
        ...record,
        status: "dismissed",
      } satisfies Recommendation);
    }),
  );
  mount(<Recommendations />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Dismiss recommendation" }),
  );
  expect(await screen.findByText(/Recommendation dismissed/)).toBeVisible();
  await userEvent.selectOptions(
    screen.getByLabelText("Recommendation status"),
    "dismissed",
  );
  expect(
    await screen.findByRole("article", { name: "Music overlap" }),
  ).toBeVisible();
});
test("dashboard savings displays only the API figure and supports an actual zero", async () => {
  server.use(
    http.get("*/api/v1/summary/savings", () =>
      HttpResponse.json({
        potential_savings: "1234567.89",
        currency: "INR",
      } satisfies components["schemas"]["SavingsOut"]),
    ),
  );
  const first = mount(<SavingsPanel />);
  expect(await screen.findByTestId("potential-savings")).toHaveTextContent(
    "₹12,34,567.89",
  );
  first.unmount();
  server.use(
    http.get("*/api/v1/summary/savings", () =>
      HttpResponse.json({
        potential_savings: "0.00",
        currency: "INR",
      } satisfies components["schemas"]["SavingsOut"]),
    ),
  );
  mount(<SavingsPanel />);
  expect(
    await screen.findByText("No open duplicate estimates right now."),
  ).toBeVisible();
});
test("recommendations remain accessible and link to the actual product drawer", async () => {
  server.use(http.get("*/api/v1/recommendations", () => page([record])));
  const view = mount(<Recommendations />);
  expect(
    await screen.findByRole("link", { name: "Review synthetic music Music" }),
  ).toHaveAttribute("href", "/subscriptions?review=sub-1");
  expect(
    (
      await axe(view.container, {
        rules: { "color-contrast": { enabled: false } },
      })
    ).violations,
  ).toEqual([]);
});
test("recent alert panel renders sent and safe skipped states without recipients", async () => {
  const base: components["schemas"]["AlertOut"] = {
    id: "alert-1",
    subscription_id: null,
    kind: "budget",
    send_on: "2026-10-01",
    status: "sent",
    sent_at: "2026-10-18T00:00:00Z",
    channel: "email",
    attempt_count: 1,
    last_attempt_at: "2026-10-18T00:00:00Z",
    next_attempt_at: null,
    safe_failure_reason: null,
  };
  server.use(
    http.get("*/api/v1/alerts", () =>
      HttpResponse.json({
        items: [
          base,
          {
            ...base,
            id: "alert-2",
            status: "skipped",
            sent_at: null,
            attempt_count: 0,
            safe_failure_reason: "No notification email configured",
          },
        ],
        total: 2,
        limit: 10,
        offset: 0,
      } satisfies components["schemas"]["Page_AlertOut_"]),
    ),
  );
  mount(<RecentAlerts />);
  expect(
    await screen.findByText("No notification email configured"),
  ).toBeVisible();
  expect(screen.getByText("Sent", { exact: true })).toBeVisible();
  expect(screen.getByText("Skipped")).toBeVisible();
});
