import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom lacks the native dialog lifecycle. Browser focus trapping is verified by Playwright.
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
  this.querySelector<HTMLElement>("button, input, select")?.focus();
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};

afterEach(cleanup);
