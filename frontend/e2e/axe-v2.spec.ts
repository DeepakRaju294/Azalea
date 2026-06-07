/**
 * Playwright + axe-core a11y audit for the v2 learn page.
 *
 * Run locally with:
 *   npx playwright install --with-deps chromium
 *   npx playwright test e2e/axe-v2.spec.ts
 *
 * The CI workflow runs the same thing. The test exercises one v2 lesson
 * end-to-end and walks axe-core across the rendered DOM. Failures
 * fail the gate; the report is uploaded as a workflow artifact.
 *
 * Requires the v2 backend + frontend to be running locally on the
 * standard ports. In CI we boot them as services. We auth via a test
 * supabase token loaded from V2_TEST_AUTH_TOKEN.
 */

import { expect, test } from "@playwright/test";
// @ts-expect-error — axe-core does not ship its own d.ts via this path.
import { injectAxe, checkA11y } from "axe-playwright";

const BASE_URL = process.env.V2_TEST_BASE_URL || "http://localhost:3000";
const TEST_TOPIC_ID = process.env.V2_TEST_TOPIC_ID || "";

test.describe("v2 learn page accessibility", () => {
  test.beforeEach(async ({ page }) => {
    // If the test env provides an auth token, set it before navigation
    // so the v2 page can fetch lessons. Without this the page renders
    // an auth-required state and axe finds no v2 components.
    const authToken = process.env.V2_TEST_AUTH_TOKEN || "";
    if (authToken) {
      await page.addInitScript((t) => {
        const session = {
          access_token: t,
          refresh_token: "test",
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          token_type: "bearer",
        };
        window.localStorage.setItem(
          "sb-azalea-auth-token",
          JSON.stringify({ currentSession: session }),
        );
      }, authToken);
    }
  });

  test("learn-v2 renders without serious axe violations", async ({ page }) => {
    test.skip(
      !TEST_TOPIC_ID,
      "V2_TEST_TOPIC_ID not set; skipping live axe audit",
    );
    await page.goto(
      `${BASE_URL}/study-paths/test/learn-v2?topic=${TEST_TOPIC_ID}`,
    );

    // Wait for the lesson to render. The H2 with the step title appears
    // once a render_step is mounted; that's our "ready" signal.
    await page.waitForSelector("h2", { timeout: 30_000 });

    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      axeOptions: {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
        },
      },
    });
  });

  test("clicking a node opens chat sidebar without violations", async ({ page }) => {
    test.skip(
      !TEST_TOPIC_ID,
      "V2_TEST_TOPIC_ID not set; skipping live axe audit",
    );
    await page.goto(
      `${BASE_URL}/study-paths/test/learn-v2?topic=${TEST_TOPIC_ID}`,
    );
    await page.waitForSelector("h2", { timeout: 30_000 });

    // Try to click the first selectable element (any element with a
    // data-element-id attribute or a role=button inside the visual area).
    const firstClickable = page.locator(
      '[role="button"], [data-element-id]',
    ).first();
    if (await firstClickable.count()) {
      await firstClickable.click({ force: true });
    }

    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      axeOptions: {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
        },
      },
    });
  });
});
