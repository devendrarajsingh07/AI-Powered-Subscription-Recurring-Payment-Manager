import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { clearSession, getToken } from "../lib/session";

export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
  }
}
const configuredBase = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(
  /\/api\/v1\/?$/,
  "",
);
export const api = createClient<paths>({
  baseUrl: configuredBase.startsWith("http")
    ? configuredBase
    : window.location.origin + configuredBase,
  fetch: (request) => globalThis.fetch(request),
});
api.use({
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  async onResponse({ response, schemaPath }) {
    if (!response.ok) {
      if (
        response.status === 401 &&
        schemaPath !== "/api/v1/auth/login" &&
        schemaPath !== "/auth/login"
      )
        clearSession(true);
      const body = await response
        .clone()
        .json()
        .catch(() => null);
      const message =
        response.status === 429
          ? "Too many attempts. Please try again shortly."
          : body?.error?.message ||
            "The request could not be completed. Please try again.";
      throw new ApiError(message, response.status);
    }
    return response;
  },
});
// The contract paths include /api/v1; base origin avoids duplicating that prefix.
export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
