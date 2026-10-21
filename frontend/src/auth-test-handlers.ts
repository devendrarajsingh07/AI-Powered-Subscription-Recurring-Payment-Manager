import { http, HttpResponse } from "msw";
import type { components } from "./api/schema";

export const authHandlers = [
  http.post("*/api/v1/auth/logout-cookie", () =>
    HttpResponse.json({
      message: "Signed out",
    } satisfies components["schemas"]["MessageResult"]),
  ),
  http.get("*/api/v1/auth/config", () =>
    HttpResponse.json({
      public_demo_only: false,
      session_mode: "strict",
      notice: "Educational use with synthetic data",
    } satisfies components["schemas"]["AuthConfig"]),
  ),
  http.post("*/api/v1/auth/csrf", () =>
    HttpResponse.json({
      csrf_token: null,
    } satisfies components["schemas"]["CsrfResult"]),
  ),
  http.post("*/api/v1/auth/logout", () =>
    HttpResponse.json({
      message: "Signed out",
    } satisfies components["schemas"]["MessageResult"]),
  ),
];
