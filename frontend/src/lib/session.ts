import { useSyncExternalStore } from "react";
import type { components } from "../api/schema";

const key = "subtrack.session";
type Session = { token: string; expires: number };
type SignOutNotice = { message: string; deleted?: Record<string, number> };
let signOutNotice: SignOutNotice | undefined;
export const getSignOutNotice = () => signOutNotice;
function read(): Session | null {
  try {
    const value = JSON.parse(
      sessionStorage.getItem(key) || "null",
    ) as Session | null;
    if (
      value &&
      typeof value.token === "string" &&
      Number.isFinite(value.expires) &&
      value.expires > Date.now()
    )
      return value;
    if (value) {
      sessionStorage.removeItem(key);
      signOutNotice = {
        message: "Your session expired. Please sign in again.",
      };
    }
    return null;
  } catch {
    return null;
  }
}
let current = read();
const listeners = new Set<() => void>();
export function clearSession(
  expired = false,
  deleted?: Record<string, number>,
) {
  current = null;
  signOutNotice = {
    message: deleted
      ? "Your account and data were deleted."
      : expired
        ? "Your session expired. Please sign in again."
        : "You have been signed out.",
    deleted,
  };
  sessionStorage.removeItem(key);
  window.dispatchEvent(
    new CustomEvent("subtrack:logout", { detail: { expired } }),
  );
  listeners.forEach((listener) => listener());
}
export function saveSession(value: components["schemas"]["Token"]) {
  signOutNotice = undefined;
  current = {
    token: value.access_token,
    expires: Date.now() + value.expires_in * 1000,
  };
  sessionStorage.setItem(key, JSON.stringify(current));
  listeners.forEach((listener) => listener());
}
export function getToken() {
  if (current && current.expires <= Date.now()) clearSession(true);
  return current?.token;
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
