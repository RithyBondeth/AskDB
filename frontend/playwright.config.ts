import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Browser smoke tests: the real frontend and backend, with a mock model (e2e/mock-model.mjs)
// standing in for the provider. Run `npm run build` first, then `npm run e2e`.
// Ports differ from the dev servers so both can run at once.
const WEB = 3100;
const API = 8100;
const MODEL = 8765;
// Saved answers and uploads from a test run go to a throwaway folder.
const data = mkdtempSync(join(tmpdir(), "askdb-e2e-"));
// Use an already-installed Chromium (e.g. PW_CHROMIUM_PATH=/opt/pw-browsers/chromium)
// instead of `npx playwright install`.
const executablePath = process.env.PW_CHROMIUM_PATH;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB}`,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
    viewport: { width: 1400, height: 1000 },
    launchOptions: executablePath ? { executablePath } : {},
  },
  webServer: [
    {
      command: "node e2e/mock-model.mjs",
      url: `http://127.0.0.1:${MODEL}/models`,
      env: { MOCK_MODEL_PORT: String(MODEL) },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `uv run uvicorn api.main:app --port ${API}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API}/api/health`,
      env: {
        ASKDB_PROVIDER: "free",
        ASKDB_FREE_BASE_URL: `http://127.0.0.1:${MODEL}`,
        ASKDB_FREE_API_KEY: "mock",
        ASKDB_STORE_PATH: join(data, "askdb.sqlite"),
        ASKDB_UPLOAD_DIR: join(data, "uploads"),
        ASKDB_CORS_ORIGINS: `["http://127.0.0.1:${WEB}"]`,
      },
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `npx next start -p ${WEB}`,
      url: `http://127.0.0.1:${WEB}`,
      env: { ASKDB_API_URL: `http://127.0.0.1:${API}` },
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
