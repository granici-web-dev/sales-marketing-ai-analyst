/**
 * Playwright E2E stub — Wave 0.
 *
 * Pre-declares the end-to-end happy-path test for the chat surface that plan
 * 08-06 will turn on after the orchestrator (08-04) + chat router (08-05) +
 * frontend chat UI (08-06) all ship.
 *
 * The test is `test.skip(...)` for Wave 0 — the spec file exists, the suite
 * COMPILES (when @playwright/test is installed), but every assertion is
 * inert. Plan 08-06 removes the `.skip` and the assertions become live.
 *
 * Why this Wave 0 stub matters:
 *   - The orchestrator's per-task <automated> gate in plan 08-06 references
 *     this file path; without it the gate would silently no-op.
 *   - Forces the e2e harness wiring to be settled before 08-06 starts (login
 *     helper, base URL config, viewport defaults).
 *   - Documents the assertion contract a reviewer can use to evaluate 08-06's
 *     implementation against the user-visible behavior expected by CHAT-09.
 *
 * Acceptance contract (08-RESEARCH.md § Validation Architecture +
 * 08-CONTEXT.md D-32/D-33):
 *
 *   - User logs in with seeded test credentials.
 *   - Navigates to /chat (lazy hash route is fine — no UI-route change required).
 *   - Sees the chat input (aria-label="Întrebare nouă") within 5s.
 *   - Types "Cum stăm cu vânzările luna asta?" and presses Enter.
 *   - Within 5s an assistant bubble appears (D-33 optimistic UI: empty bubble
 *     with thinking dot before SSE arrives).
 *   - Within 8s the first text content streams into the bubble (first
 *     `assistant_chunk` SSE event applied).
 *
 * Note: @playwright/test is NOT yet a project dependency. Plan 08-06 adds it
 * via `pnpm add -D @playwright/test playwright`. Wave 0 (this plan) only
 * delivers the SPEC FILE — no install. If a CI step prematurely tries to
 * run this without the install, the import below fails fast with a clear
 * "Cannot find module '@playwright/test'" error.
 */

// @ts-expect-error -- Playwright is wired in plan 08-06; Wave 0 keeps file as stub.
import { test, expect } from "@playwright/test";

test.skip(
  "chat: send Romanian question and receive streamed response",
  async ({ page }) => {
    // ── Setup: log in with seeded test credentials ──────────────────────────
    // Reuse Phase 1 login helper once 08-06 lands; for now this is a no-op
    // because the entire test is skipped.
    await page.goto("/login");
    await page.fill('input[name="email"]', "owner@sofabelle.test");
    await page.fill('input[name="password"]', "test-password");
    await page.click('button[type="submit"]');

    // ── Navigate to the chat surface ────────────────────────────────────────
    await page.goto("/chat");

    // ── Wait for the chat input (UI-SPEC aria-label) ───────────────────────
    const input = page.locator('textarea[aria-label="Întrebare nouă"]');
    await expect(input).toBeVisible({ timeout: 5_000 });

    // ── Send a Romanian question and confirm the response streams ──────────
    await input.fill("Cum stăm cu vânzările luna asta?");
    await input.press("Enter");

    // Assistant bubble shows up (D-33 optimistic UI).
    const assistantBubble = page.locator('[data-role="assistant-message"]').last();
    await expect(assistantBubble).toBeVisible({ timeout: 5_000 });

    // First streamed text content arrives.
    await expect(assistantBubble).not.toHaveText("", { timeout: 8_000 });
  },
);
