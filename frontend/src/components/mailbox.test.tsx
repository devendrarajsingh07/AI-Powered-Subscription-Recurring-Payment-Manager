import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import MailboxLab, { EvidenceEditor } from "../pages/MailboxLab";

type Config = components["schemas"]["MailboxConfig"];
type Evidence = components["schemas"]["ReceiptEvidenceOut"];
const config: Config = {
  enabled: true,
  connected: false,
  mode: "synthetic",
  live_available: false,
  disclosure: "Synthetic fixtures only. No Gmail access or AI disclosure.",
  consent_version: "synthetic-mailbox-v1",
  interest_disclosure:
    "Separate voluntary declaration. No offers or provider contact.",
  interest_version: "voluntary-interest-v1",
};
const evidence: Evidence = {
  id: "00000000-0000-4000-8000-000000000001",
  merchant: "netflix",
  charged_on: "2026-07-01",
  amount: "499.00",
  currency: "INR",
  flags: ["authenticity_unverified"],
  status: "pending",
  transaction_id: null,
  reviewed_at: null,
  candidates: [
    {
      id: "00000000-0000-4000-8000-000000000002",
      merchant_normalized: "netflix",
      date: "2026-07-01",
      amount: "499.00",
      currency: "INR",
    },
    {
      id: "00000000-0000-4000-8000-000000000003",
      merchant_normalized: "netflix",
      date: "2026-06-30",
      amount: "499.00",
      currency: "INR",
    },
  ],
};
const server = setupServer(
  http.get("*/api/v1/mailbox/config", () => HttpResponse.json(config)),
  http.get("*/api/v1/interests", () =>
    HttpResponse.json({
      categories: [],
      consent_version: config.interest_version,
      disclosure: config.interest_disclosure,
    } satisfies components["schemas"]["InterestOut"]),
  ),
  http.get("*/api/v1/mailbox/evidence", () =>
    HttpResponse.json({
      items: [evidence],
      total: 1,
      limit: 10,
      offset: 0,
    } satisfies components["schemas"]["Page_ReceiptEvidenceOut_"]),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function mount(ui = <MailboxLab />) {
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
      {ui}
    </QueryClientProvider>,
  );
}

test("synthetic consent is explicit and live Gmail is never offered as connected", async () => {
  let posted: unknown;
  server.use(
    http.post("*/api/v1/mailbox/synthetic/connect", async ({ request }) => {
      posted = await request.json();
      return HttpResponse.json({ ...config, connected: true } satisfies Config);
    }),
  );
  mount();
  const user = userEvent.setup();
  const start = await screen.findByRole("button", {
    name: "Start synthetic mailbox lab",
  });
  expect(start).toBeDisabled();
  await user.click(
    screen.getByLabelText(
      "I consent to the synthetic mailbox rehearsal described above",
    ),
  );
  await user.click(start);
  expect(await screen.findByText("Synthetic fixture connection")).toBeVisible();
  expect(posted).toEqual({ consent: true, version: config.consent_version });
  expect(screen.getByText(/Live Gmail is unavailable/)).toBeVisible();
});

test("disabled mode has no connect, sync or financial input controls", async () => {
  server.use(
    http.get("*/api/v1/mailbox/config", () =>
      HttpResponse.json({
        ...config,
        enabled: false,
        mode: "disabled",
      } satisfies Config),
    ),
  );
  mount();
  expect(await screen.findByText(/This lab is disabled/)).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Start synthetic mailbox lab" }),
  ).toBeNull();
  expect(screen.queryByRole("textbox")).toBeNull();
});

test("ambiguous bank matching requires a selected candidate and separate confirmation; edits revoke approval", async () => {
  const decide = vi.fn();
  mount(<EvidenceEditor row={evidence} busy={false} onDecision={decide} />);
  const user = userEvent.setup();
  expect(screen.getByText(/Several bank debits qualify/)).toBeVisible();
  const match = screen.getByRole("button", { name: "Confirm bank match" });
  expect(match).toBeDisabled();
  await user.click(screen.getAllByRole("radio")[0]);
  expect(match).toBeDisabled();
  await user.click(screen.getByLabelText("I confirm this is the same payment"));
  await user.click(match);
  expect(decide).toHaveBeenCalledWith({
    action: "match",
    verified: true,
    transaction_id: evidence.candidates[0].id,
  });
  await user.clear(screen.getByLabelText("Amount (INR)"));
  await user.type(screen.getByLabelText("Amount (INR)"), "1499.50");
  expect(match).toBeDisabled();
  const save = screen.getByRole("button", { name: "Save reviewed fields" });
  expect(save).toBeDisabled();
  await user.click(screen.getByLabelText("I reviewed these receipt fields"));
  await user.click(save);
  expect(decide).toHaveBeenLastCalledWith({
    action: "review",
    verified: true,
    merchant: "netflix",
    charged_on: "2026-07-01",
    amount: "1499.50",
  });
});

test.each(["light", "dark"])(
  "receipt evidence is accessible plain text in %s",
  async (theme) => {
    document.documentElement.dataset.theme = theme;
    const hostile = "<img src=x onerror=steal()>";
    const ui = mount(
      <EvidenceEditor
        row={{ ...evidence, merchant: hostile }}
        busy={false}
        onDecision={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: hostile })).toBeVisible();
    expect(ui.container.querySelector("img,script,iframe")).toBeNull();
    expect((await axe(ui.container)).violations).toEqual([]);
  },
);

test("voluntary interests need their own consent and never use receipt preferences", async () => {
  let body: unknown;
  server.use(
    http.put("*/api/v1/interests", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({
        categories: ["music"],
        consent_version: config.interest_version,
        disclosure: config.interest_disclosure,
      } satisfies components["schemas"]["InterestOut"]);
    }),
  );
  mount();
  const save = await screen.findByRole("button", {
    name: "Save voluntary interests",
  });
  expect(save).toBeDisabled();
  const user = userEvent.setup();
  await user.click(screen.getByLabelText("music"));
  expect(save).toBeDisabled();
  await user.click(
    screen.getByLabelText(
      "I separately consent to save these voluntary interests",
    ),
  );
  await user.click(save);
  await waitFor(() =>
    expect(body).toEqual({
      consent: true,
      version: config.interest_version,
      categories: ["music"],
    }),
  );
});

test("disconnect requires typed confirmation and reports purge; errors remain visible", async () => {
  server.use(
    http.get("*/api/v1/mailbox/config", () =>
      HttpResponse.json({ ...config, connected: true } satisfies Config),
    ),
    http.delete("*/api/v1/mailbox/connection", () =>
      HttpResponse.json({
        deleted: { receipt_evidence: 1, mailbox_syncs: 1, oauth_states: 0 },
      } satisfies components["schemas"]["DeleteResult"]),
    ),
  );
  mount();
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", {
      name: "Disconnect and remove evidence",
    }),
  );
  const dialog = within(screen.getByRole("dialog"));
  const purge = dialog.getByRole("button", { name: "Purge mailbox evidence" });
  expect(purge).toBeDisabled();
  await user.type(dialog.getByLabelText("Confirmation word"), "DISCONNECT");
  await user.click(purge);
  expect(await screen.findByText(/Mailbox consent withdrawn/)).toBeVisible();
});

test("configuration failure has a safe error and retry", async () => {
  server.use(
    http.get("*/api/v1/mailbox/config", () =>
      HttpResponse.json(
        { error: { code: "unavailable", message: "Please retry shortly" } },
        { status: 503 },
      ),
    ),
  );
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Please retry shortly",
  );
  expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
});

test.each(["queued", "running", "done", "failed"] as const)(
  "sync progress shows server state %s",
  async (status) => {
    const progress: components["schemas"]["MailboxSyncOut"] = {
      id: "00000000-0000-4000-8000-000000000004",
      status,
      processed: status === "done" ? 16 : 0,
      total: 16,
      accepted: status === "done" ? 12 : 0,
      rejected: status === "done" ? 4 : 0,
      duplicates: 0,
      attempts: 1,
      failure_code: status === "failed" ? "sync_unavailable" : null,
      expires_at: "2030-01-01T00:00:00Z",
      created_at: "2026-10-18T00:00:00Z",
    };
    server.use(
      http.get("*/api/v1/mailbox/config", () =>
        HttpResponse.json({ ...config, connected: true } satisfies Config),
      ),
      http.post("*/api/v1/mailbox/sync", () =>
        HttpResponse.json({
          ...progress,
          status: "queued",
          processed: 0,
          accepted: 0,
          rejected: 0,
        } satisfies components["schemas"]["MailboxSyncOut"]),
      ),
      http.get("*/api/v1/mailbox/sync/:id", () => HttpResponse.json(progress)),
    );
    mount();
    await userEvent.click(
      await screen.findByRole("button", { name: "Sync synthetic receipts" }),
    );
    const region = within(
      await screen.findByRole("region", { name: "Mailbox sync progress" }),
    );
    await waitFor(() =>
      expect(region.getByRole("status")).toHaveTextContent(`Status: ${status}`),
    );
    expect(region.getByRole("progressbar")).toHaveAttribute(
      "value",
      String(progress.processed),
    );
    if (status === "failed")
      expect(region.getByRole("status")).toHaveTextContent("sync_unavailable");
  },
);
