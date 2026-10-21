import { useSyncExternalStore } from "react";
import type { components } from "../api/schema";
import { apiOrigin } from "../api/base";

type Session = { token: string; expires: number };
type Notice = { message: string; deleted?: Record<string, number> };
let current: Session | null = null;
let signOutNotice: Notice | undefined;
let csrf: string | undefined;
let revision = 0;
let pendingRefresh: Promise<boolean> | undefined;
const listeners = new Set<() => void>();
// Remove credentials left by older app versions; access tokens live only in this module.
try {
  sessionStorage.removeItem("subtrack.session");
} catch {
  /* Storage may be disabled. */
}
export const getSignOutNotice = () => signOutNotice;
export function clearSession(
  expired = false,
  deleted?: Record<string, number>,
) {
  revision += 1;
  current = null;
  csrf = undefined;
  signOutNotice = {
    message: deleted
      ? "Your account and data were deleted."
      : expired
        ? "Your session expired. Please sign in again."
        : "You have been signed out.",
    deleted,
  };
  try {
    sessionStorage.removeItem("subtrack.session");
  } catch {
    /* Memory remains cleared. */
  }
  window.dispatchEvent(
    new CustomEvent("subtrack:logout", { detail: { expired } }),
  );
  listeners.forEach((listener) => listener());
}
export function saveSession(value: components["schemas"]["Token"]) {
  revision += 1;
  signOutNotice = undefined;
  csrf = value.csrf_token || undefined;
  current = {
    token: value.access_token,
    expires: Date.now() + value.expires_in * 1000,
  };
  listeners.forEach((listener) => listener());
}
export function getToken() {
  if (current && current.expires <= Date.now()) clearSession(true);
  return current?.token;
}
export function refreshSession(): Promise<boolean> {
  if (pendingRefresh) return pendingRefresh;
  const started = revision;
  // Tabs share one cookie jar. Serialise rotation across tabs so two tabs presenting the same
  // refresh token cannot look like token theft, and always re-read the CSRF proof for the
  // cookie that is current *inside* the lock (another tab may have just rotated it).
  const exclusive = <T>(work: () => Promise<T>): Promise<T> =>
    typeof navigator !== "undefined" && navigator.locks
      ? navigator.locks.request("subtrack-refresh", work)
      : work();
  pendingRefresh = exclusive(async () => {
    try {
      const config = await fetch(apiOrigin + "/api/v1/auth/config", {
        credentials: "include",
      });
      if (
        !config.ok ||
        ((await config.json()) as components["schemas"]["AuthConfig"])
          .session_mode === "demo"
      )
        return false;
      const bootstrap = await fetch(apiOrigin + "/api/v1/auth/csrf", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!bootstrap.ok) return false;
      const candidate = (
        (await bootstrap.json()) as components["schemas"]["CsrfResult"]
      ).csrf_token;
      if (!candidate) return false;
      csrf = candidate;
      const response = await fetch(apiOrigin + "/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf!, "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) return false;
      const token = (await response.json()) as components["schemas"]["Token"];
      if (revision !== started) return false;
      saveSession(token);
      return true;
    } catch {
      return false;
    } finally {
      pendingRefresh = undefined;
    }
  });
  return pendingRefresh;
}
export async function logout(everywhere = false) {
  try {
    if (everywhere && current && current.expires <= Date.now()) {
      if (!(await refreshSession()))
        throw new Error("Reauthentication required");
    }
    const token = current?.token;
    const cookieLogout = !everywhere && Boolean(csrf);
    if (token || cookieLogout) {
      const response = await fetch(
        apiOrigin +
          "/api/v1/auth/" +
          (everywhere
            ? "logout-all"
            : cookieLogout
              ? "logout-cookie"
              : "logout"),
        {
          method: "POST",
          credentials: "include",
          headers: cookieLogout
            ? { "X-CSRF-Token": csrf!, "Content-Type": "application/json" }
            : { Authorization: `Bearer ${token}` },
          body: cookieLogout ? "{}" : undefined,
        },
      );
      if (!response.ok) throw new Error("Revocation failed");
    }
    clearSession();
  } catch {
    // Keep the UI signed in so failed server revocation can be retried explicitly.
    throw new Error("Could not sign out securely. Please retry.");
  }
}
export function useSession() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => current,
  );
}
