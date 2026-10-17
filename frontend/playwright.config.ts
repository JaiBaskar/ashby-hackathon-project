import { defineConfig, devices } from '@playwright/test'

// End-to-end runs against the real stack: FastAPI (uvicorn, the demo model from config.yaml) and a production
// Next.js build. Tests go through Next's port, so the /api rewrite is covered. Ports differ from `make dev`.
const API_PORT = 8100
const WEB_PORT = 3100
const API_URL = `http://127.0.0.1:${API_PORT}`
// The repo's venv by default; set PYTHON on machines where it lives elsewhere (e.g. .venv/Scripts/python on Windows).
const PYTHON = process.env.PYTHON ?? '../.venv/bin/python'

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  timeout: 60_000,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    ...devices['Desktop Chrome'],
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${PYTHON} -m uvicorn --factory --app-dir ../backend project.api:create_app --host 127.0.0.1 --port ${API_PORT}`,
      // Never write test runs into a real history database, even if the shell has DATABASE_URL set.
      env: { DATABASE_URL: '' },
      url: `${API_URL}/docs`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // API_URL must be set before the build: rewrites are fixed at build time (implementation-steps.md §3).
      command: `npx next build && npx next start --hostname 127.0.0.1 --port ${WEB_PORT}`,
      env: { API_URL },
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 300_000,
    },
  ],
})
