import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: `VITE_PROXY_TARGET=http://localhost:8004 npm run dev` proxies API calls to a
// running backend (local uvicorn or the live Render URL). Prod build is same-origin —
// FastAPI serves dist/ itself. 8004 matches the port used everywhere else in this repo
// (README Quick Start, Dockerfile, docker-compose.dev.yml) -- the plain `npm run dev`
// default has to match that or requests silently hit the Vite dev server's own origin
// instead of the backend.
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8004";
// "/analytics/" (trailing slash) so the proxy only takes the backend's /analytics/*
// sub-routes -- the bare "/analytics" path is the frontend's own SPA route
// (App.tsx's Analytics dashboard page) and must still be served by Vite itself.
const apiPaths = ["/health", "/ingest", "/webhook", "/pipeline", "/live", "/analytics/", "/docs", "/openapi.json"];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      apiPaths.map((p) => [p, { target, changeOrigin: true, secure: false, ws: true }]),
    ),
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
      },
    },
  },
  test: {
    // e2e/ holds Playwright specs (npm run test:e2e) — vitest's default glob would
    // otherwise also try to collect them and fail on the missing @playwright/test runtime.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
