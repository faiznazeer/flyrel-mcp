import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://localhost:8787", browserName: "chromium" },
  webServer: {
    command: "npm run db:local && npm run dev -- --port 8787",
    url: "http://localhost:8787",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
