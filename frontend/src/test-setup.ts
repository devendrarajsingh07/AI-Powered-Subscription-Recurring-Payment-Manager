import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no canvas implementation. Keep the capability unavailable without its
// noisy "not implemented" console error; full browser axe checks cover real layout.
HTMLCanvasElement.prototype.getContext = function () {
  return null;
};

// jsdom lacks the native dialog lifecycle. Browser focus trapping is verified by Playwright.
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
  this.querySelector<HTMLElement>("button, input, select")?.focus();
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};

afterEach(cleanup);
