export type Theme = "light" | "dark" | "system";
export function readTheme(): Theme {
  try {
    const value = localStorage.getItem("subtrack.theme");
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}
export function applyTheme(value: Theme) {
  document.documentElement.dataset.theme =
    value === "system"
      ? window.matchMedia?.("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : value;
  try {
    localStorage.setItem("subtrack.theme", value);
  } catch {
    /* Storage is optional. */
  }
}
