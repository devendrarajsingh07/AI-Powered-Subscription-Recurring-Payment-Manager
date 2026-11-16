import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ImportWalkthrough } from "./ImportWalkthrough";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

test("replay advances six illustrative stages without making a request", () => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
  const requests = vi.spyOn(globalThis, "fetch");
  render(<ImportWalkthrough />);
  expect(
    screen.getByText("Simulation · No statement is imported."),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Replay walkthrough" }));
  for (const label of [
    "Choose file",
    "Review",
    "Validate",
    "Detect",
    "Record",
    "Ready",
  ]) {
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(
      label,
    );
    act(() => {
      vi.advanceTimersByTime(680);
    });
  }
  expect(
    screen.getByRole("button", { name: "Replay walkthrough" }),
  ).toBeVisible();
  expect(requests).not.toHaveBeenCalled();
});

test("stop keeps the current stage and reduced motion jumps to the result", () => {
  vi.useFakeTimers();
  const media = vi.fn(() => ({ matches: false }));
  vi.stubGlobal("matchMedia", media);
  render(<ImportWalkthrough />);
  fireEvent.click(screen.getByRole("button", { name: "Replay walkthrough" }));
  fireEvent.click(screen.getByRole("button", { name: "Stop walkthrough" }));
  act(() => {
    vi.advanceTimersByTime(680);
  });
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(
    "Choose file",
  );
  media.mockReturnValue({ matches: true });
  fireEvent.click(screen.getByRole("button", { name: "Replay walkthrough" }));
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(
    "Ready",
  );
  expect(
    screen.queryByRole("button", { name: "Stop walkthrough" }),
  ).not.toBeInTheDocument();
});
