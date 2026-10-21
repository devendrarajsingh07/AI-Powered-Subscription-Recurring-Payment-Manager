import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter } from "react-router";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import type { components } from "../api/schema";
import { authHandlers } from "../auth-test-handlers";
import { Auth } from "../pages/Auth";
import { Unsubscribe } from "../pages/Unsubscribe";
import { ReportProblem } from "./ReportProblem";

const server = setupServer(...authHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
function view(ui: React.ReactNode, path = "/") {
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

test("unsubscribe page posts the signed link only after an explicit click", async () => {
  let seen = "";
  server.use(
    http.post("*/api/v1/alerts/unsubscribe", ({ request }) => {
      seen = new URL(request.url).search;
      return HttpResponse.json({
        message:
          "If this link was valid, SubTrack alert emails are now turned off.",
      } satisfies components["schemas"]["MessageResult"]);
    }),
  );
  view(<Unsubscribe />, "/unsubscribe?u=user-1&t=signature");
  expect(seen).toBe("");
  await userEvent.click(
    screen.getByRole("button", { name: "Turn off alert emails" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "alert emails are now turned off",
  );
  expect(seen).toBe("?u=user-1&t=signature");
});

test("incomplete unsubscribe link offers no action", () => {
  view(<Unsubscribe />, "/unsubscribe");
  expect(screen.getByRole("alert")).toHaveTextContent("incomplete");
  expect(screen.queryByRole("button")).toBeNull();
});

test("problem report is sent and surfaces the server's content rejection", async () => {
  const bodies: unknown[] = [];
  server.use(
    http.post("*/api/v1/support/reports", async ({ request }) => {
      const body = (await request.json()) as { message: string };
      bodies.push(body);
      if (/\d{6,}/.test(body.message))
        return HttpResponse.json(
          {
            error: {
              code: "sensitive_content",
              message: "Please describe the problem without account numbers",
            },
          },
          { status: 422 },
        );
      return HttpResponse.json(
        {
          id: crypto.randomUUID(),
          received: true,
        } satisfies components["schemas"]["SupportReportOut"],
        { status: 201 },
      );
    }),
  );
  view(<ReportProblem />);
  const box = screen.getByLabelText("Description");
  await userEvent.type(box, "ref 12345678 looks odd");
  await userEvent.click(screen.getByRole("button", { name: "Send report" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("account numbers");
  await userEvent.clear(box);
  await userEvent.type(box, "The renewal date looks wrong");
  await userEvent.click(screen.getByRole("button", { name: "Send report" }));
  expect(await screen.findByRole("status")).toHaveTextContent("received");
  expect(bodies).toHaveLength(2);
});

test("registration requires and sends the current legal version when enabled", async () => {
  let sent: Record<string, unknown> | undefined;
  server.use(
    http.get("*/api/v1/auth/config", () =>
      HttpResponse.json({
        public_demo_only: false,
        session_mode: "strict",
        notice: "Educational use with synthetic data",
        legal_version: "draft-1",
        legal_acceptance_required: true,
      } satisfies components["schemas"]["AuthConfig"]),
    ),
    http.post("*/api/v1/auth/register", async ({ request }) => {
      sent = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(
        {
          id: crypto.randomUUID(),
          email: "a@example.org",
          verification_required: true,
        },
        { status: 201 },
      );
    }),
  );
  view(<Auth register />, "/register");
  await userEvent.type(
    await screen.findByLabelText(/Email address/),
    "a@example.org",
  );
  await userEvent.type(
    screen.getByLabelText(/^Password/),
    "Correct-Horse-9-Battery",
  );
  await userEvent.click(screen.getByRole("button", { name: /Create account/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "accept the terms",
  );
  expect(sent).toBeUndefined();
  await userEvent.click(screen.getByRole("checkbox", { name: /draft-1/ }));
  await userEvent.click(screen.getByRole("button", { name: /Create account/ }));
  await screen.findByRole("button", { name: /Create account/ });
  expect(sent?.accepted_terms_version).toBe("draft-1");
});
