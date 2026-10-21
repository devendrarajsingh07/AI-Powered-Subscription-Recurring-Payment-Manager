import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const configuredApi = process.env.VITE_API_BASE_URL || "/api/v1";
const apiConnect = /^https?:\/\//.test(configuredApi)
  ? new URL(configuredApi).origin
  : "";

const headers = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
  "Content-Security-Policy": `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; frame-src 'self' blob:; connect-src 'self' ws: wss: ${apiConnect}; frame-ancestors 'none'; base-uri 'self'; object-src 'none'`,
};
// Publishes the built commit so a release pipeline can prove the new frontend is serving.
const commit = process.env.VERCEL_GIT_COMMIT_SHA || "";
function versionFile(): Plugin {
  return {
    name: "subtrack-version",
    apply: "build",
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "version.json",
        source: JSON.stringify({
          revision: /^[0-9a-f]{40}$/.test(commit) ? commit : null,
        }),
      });
    },
  };
}
export default defineConfig({
  preview: { headers },
  plugins: [react(), tailwindcss(), versionFile()],
  server: {
    headers,
    watch: {
      usePolling: process.env.VITE_USE_POLLING === "true",
      interval: 300,
    },
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
