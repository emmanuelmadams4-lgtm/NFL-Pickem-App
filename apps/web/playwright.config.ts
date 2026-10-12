import { defineConfig } from "@playwright/test";

/** Browser tests run against the production export served by FastAPI, on a seeded throwaway database. */
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8123",
    browserName: "chromium",
    timezoneId: "America/New_York",
    locale: "en-US",
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "bash ../../scripts/e2e-server.sh",
    url: "http://127.0.0.1:8123/api/health",
    timeout: 180_000,
    reuseExistingServer: false,
    stdout: "pipe",
  },
});
