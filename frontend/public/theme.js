// Before first paint; storage is a non-sensitive optional preference.
try {
  var preference = localStorage.getItem("subtrack.theme");
  document.documentElement.dataset.theme = preference === "dark" || preference === "light" ? preference : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
} catch {
  document.documentElement.dataset.theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
