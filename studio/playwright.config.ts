import { defineConfig } from "@playwright/test";
import path from "node:path";
import os from "node:os";
const home =
  process.env.STUDIO_TEST_HOME ||
  path.join(os.tmpdir(), "eduevidence-studio-browser-tests");
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:8765",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: {
      ...(process.env.PLAYWRIGHT_CHROMIUM_PATH
        ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
        : {}),
    },
  },
  webServer: [
    {
      command:
        "python tests/seed.py && python ../scripts/dashboard_server.py --port 8765",
      url: "http://127.0.0.1:8765/api/studio/catalog",
      reuseExistingServer: false,
      env: { EDUEVIDENCE_HOME: home },
    },
    {
      command: "python -m http.server 8766 --bind 127.0.0.1 --directory ..",
      url: "http://127.0.0.1:8766/dist_gh_pages/studio/",
      reuseExistingServer: false,
    },
  ],
});
