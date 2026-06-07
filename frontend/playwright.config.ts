import { defineConfig } from "@playwright/test";

/**
 * Playwright config for v2 a11y audits.
 *
 * The default test directory is `e2e/`. The default browser is chromium
 * only; we don't run cross-browser a11y because the production runtime
 * is browser-agnostic and axe-core results are deterministic across
 * browsers for the rules we run.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        // No specific browserName — Playwright defaults to chromium.
      },
    },
  ],
});
