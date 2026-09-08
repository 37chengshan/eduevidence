import { defineConfig } from "@playwright/test";
import path from "node:path";
import os from "node:os";
const home =
  process.env.STUDIO_TEST_HOME ||
  path.join(os.tmpdir(), "eduevidence-studio-browser-tests");
const port = Number(process.env.STUDIO_TEST_PORT || 8765);
const staticPort = Number(process.env.STUDIO_STATIC_TEST_PORT || 8766);
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
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
        `python tests/seed.py && python ../scripts/dashboard_server.py --port ${port}`,
      url: `http://127.0.0.1:${port}/api/studio/catalog`,
      reuseExistingServer: false,
      env: { EDUEVIDENCE_HOME: home },
    },
    {
      command: `python -m http.server ${staticPort} --bind 127.0.0.1 --directory ..`,
      url: `http://127.0.0.1:${staticPort}/dist_gh_pages/studio/`,
      reuseExistingServer: false,
    },
  ],
});
