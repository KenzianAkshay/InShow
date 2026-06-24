import { defineConfig } from "@playwright/test";

// E2E runs against the running compose stack (single ingress on port 3000).
// Start it first: `docker compose up --build`, then `npm test` in this folder.
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
});
