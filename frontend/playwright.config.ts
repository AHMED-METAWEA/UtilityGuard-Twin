import { defineConfig } from "@playwright/test";

// The browser test serves the built shell (`frontend/dist`) with `vite preview` on a loopback
// port and opens it in a real Chromium. `make test-browser` builds first. UG_E2E_DIST and
// UG_E2E_PORT exist so a modified copy of the build can be tested (the mutation checks of
// card T-A1-014) without touching `dist`.
declare const process: { env: Record<string, string | undefined> };

const port = Number(process.env.UG_E2E_PORT ?? "4179");
const dist = process.env.UG_E2E_DIST ?? "dist";
const origin = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.spec.ts",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [["list"]],
  // Under node_modules, so nothing new appears in the working tree.
  outputDir: "node_modules/.cache/playwright-results",
  use: {
    baseURL: origin,
    browserName: "chromium",
    headless: true,
    serviceWorkers: "block",
  },
  webServer: {
    command: `npx vite preview --host 127.0.0.1 --port ${port} --strictPort --outDir ${dist}`,
    url: `${origin}/`,
    reuseExistingServer: false,
    timeout: 30_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
