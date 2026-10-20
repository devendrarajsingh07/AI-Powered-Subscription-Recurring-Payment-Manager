import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { axe } from "vitest-axe";
import type { components } from "../api/schema";
import { ChatAssistant, ChatPanel } from "./ChatAssistant";

type Config = components["schemas"]["ChatConfig"];
const config: Config = {
  mode: "offline",
  provider: "fake",
  live_opt_in: false,
  disclosure:
    "Google Gemini receives subscription names, amounts and dates only after consent. " +
    "The unpaid tier allows product improvement and human review. " +
    "Paid-tier terms exclude improvement but allow safety/legal retention.",
};
const history: components["schemas"]["Page_ChatHistory_"] = {
  items: [],
  total: 0,
  limit: 20,
  offset: 0,
};
const final: components["schemas"]["ChatFinal"] = {
  answer: "Renewal: ₹119.00 on 2026-10-22",
  verified: true,
  tools: ["upcoming_renewals"],
  conversation_id: "00000000-0000-4000-8000-000000000001",
};
const server = setupServer(
  http.get("*/api/v1/chat/config", () => HttpResponse.json(config)),
  http.get("*/api/v1/chat/history", () => HttpResponse.json(history)),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function mount(drawer = false) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {drawer ? <ChatAssistant /> : <ChatPanel />}
    </QueryClientProvider>,
  );
}
function chunk(name: string, value: unknown) {
  return new TextEncoder().encode(
    `event: ${name}\ndata: ${JSON.stringify(value)}\n\n`,
  );
}
function response(value = final) {
  return new HttpResponse(
    new ReadableStream({
      start(controller) {
        controller.enqueue(
          chunk("status", {
            tool: "upcoming_renewals",
            message: "Checking…",
          } satisfies components["schemas"]["ChatStatus"]),
        );
        controller.enqueue(chunk("final", value));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream" } },
  );
}

test("offline label, verified answer, consulted tools and accessible drawer", async () => {
  server.use(http.post("*/api/v1/chat", () => response()));
  const ui = mount(true);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Ask SubTrack" }));
  expect(await screen.findByText(/Offline demo assistant/)).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "What renews this week?" }),
  );
  await user.click(screen.getByRole("button", { name: "Send question" }));
  expect(await screen.findByText(final.answer)).toBeVisible();
  expect(screen.getByText("Based on: upcoming renewals")).toBeVisible();
  expect((await axe(ui.container)).violations).toEqual([]);
  await user.click(screen.getByRole("button", { name: "Close dialog" }));
  expect(screen.getByRole("button", { name: "Ask SubTrack" })).toHaveFocus();
});

test("live consent gates the first message and can be withdrawn", async () => {
  let opted = false;
  server.use(
    http.get("*/api/v1/chat/config", () =>
      HttpResponse.json({
        ...config,
        mode: "live",
        provider: "gemini",
        live_opt_in: opted,
      } satisfies Config),
    ),
    http.put("*/api/v1/chat/config", async ({ request }) => {
      opted = ((await request.json()) as components["schemas"]["ChatConsent"])
        .live_opt_in;
      return HttpResponse.json({
        ...config,
        mode: "live",
        provider: "gemini",
        live_opt_in: opted,
      } satisfies Config);
    }),
  );
  mount();
  const user = userEvent.setup();
  expect(await screen.findByText(/Live Gemini assistant/)).toBeVisible();
  expect(screen.getByText(/Google Gemini receives/)).toHaveTextContent(
    /human review/,
  );
  expect(screen.getByText(/Google Gemini receives/)).toHaveTextContent(
    /Paid-tier/,
  );
  expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Enable live AI" })).toBeDisabled();
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Enable live AI" }));
  expect(
    await screen.findByRole("button", { name: "Withdraw live AI consent" }),
  ).toBeEnabled();
  await user.click(
    screen.getByRole("button", { name: "Withdraw live AI consent" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled(),
  );
});

test("unverified fallback and hostile text render plainly", async () => {
  const hostile = "<img src=x onerror=alert('unsafe')>";
  server.use(
    http.post("*/api/v1/chat", () =>
      response({ ...final, answer: hostile, verified: false }),
    ),
  );
  const ui = mount();
  const user = userEvent.setup();
  await user.type(await screen.findByRole("textbox"), "my renewals");
  await user.click(screen.getByRole("button", { name: "Send question" }));
  expect(await screen.findByText(hostile)).toBeVisible();
  expect(screen.getByText(/Could not verify/)).toBeVisible();
  expect(ui.container.querySelector("img")).toBeNull();
});

test("tool status is live, answer stays buffered, Stop aborts fetch", async () => {
  let aborted = false;
  server.use(
    http.post("*/api/v1/chat", ({ request }) => {
      request.signal.addEventListener("abort", () => {
        aborted = true;
      });
      return new HttpResponse(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              chunk("status", {
                tool: "upcoming_renewals",
                message: "Checking…",
              }),
            );
          },
        }),
        { headers: { "Content-Type": "text/event-stream" } },
      );
    }),
  );
  mount();
  const user = userEvent.setup();
  await user.type(await screen.findByRole("textbox"), "renewals");
  await user.click(screen.getByRole("button", { name: "Send question" }));
  expect(await screen.findByText("Checked upcoming renewals…")).toBeVisible();
  expect(screen.queryByText(final.answer)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Stop answer" }));
  expect(await screen.findByText(/Stopped/)).toBeVisible();
  expect(aborted).toBe(true);
});

test("rate limiting and stream errors show safe retry feedback", async () => {
  server.use(
    http.post("*/api/v1/chat", () =>
      HttpResponse.json(
        {
          error: { code: "rate_limited", message: "Try later" },
        } satisfies components["schemas"]["ErrorEnvelope"],
        { status: 429 },
      ),
    ),
  );
  mount();
  const user = userEvent.setup();
  await user.type(await screen.findByRole("textbox"), "budget");
  await user.click(screen.getByRole("button", { name: "Send question" }));
  expect(await screen.findByText(/Too many attempts/)).toBeVisible();
  server.use(
    http.post(
      "*/api/v1/chat",
      () =>
        new HttpResponse(
          'event: error\ndata: {"message":"Assistant timed out"}\n\n',
          { headers: { "Content-Type": "text/event-stream" } },
        ),
    ),
  );
  await user.type(screen.getByRole("textbox"), "budget");
  await user.click(screen.getByRole("button", { name: "Send question" }));
  expect(await screen.findByText("Assistant timed out")).toBeVisible();
});

test("history is shown and clearing removes it after server acknowledgement", async () => {
  let cleared = false;
  server.use(
    http.get("*/api/v1/chat/history", () =>
      HttpResponse.json(
        cleared
          ? history
          : ({
              ...history,
              total: 1,
              items: [
                {
                  id: "message-1",
                  conversation_id: final.conversation_id,
                  role: "assistant",
                  content: "Saved answer",
                  verified: true,
                  tools: ["spend_summary"],
                  created_at: "2026-10-18T00:00:00Z",
                },
              ],
            } satisfies components["schemas"]["Page_ChatHistory_"]),
      ),
    ),
    http.delete("*/api/v1/chat/history", () => {
      cleared = true;
      return HttpResponse.json({
        deleted: 1,
      } satisfies components["schemas"]["ClearedHistory"]);
    }),
  );
  mount();
  const user = userEvent.setup();
  expect(await screen.findByText("Saved answer")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Clear history" }));
  expect(await screen.findByText("Chat history cleared.")).toBeVisible();
  expect(screen.queryByText("Saved answer")).not.toBeInTheDocument();
});

test("config failure renders loading and recoverable error", async () => {
  server.use(
    http.get("*/api/v1/chat/config", () =>
      HttpResponse.json(
        { error: { code: "unavailable", message: "Assistant unavailable" } },
        { status: 503 },
      ),
    ),
  );
  mount();
  expect(screen.getByText("Opening your assistant…")).toBeVisible();
  expect(await screen.findByText("Assistant unavailable")).toBeVisible();
});
