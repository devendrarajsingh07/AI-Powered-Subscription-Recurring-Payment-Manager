const configured = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(
  /\/api\/v1\/?$/,
  "",
);
export const apiOrigin = configured.startsWith("http")
  ? configured
  : window.location.origin + configured;
