import { expect, test } from "@playwright/test";

test("live Memory, Knowledge Map, and context usage review", async ({ page }) => {
  await page.goto("http://127.0.0.1:8765/#/memory");
  if (await page.getByLabel("Confirm password").isVisible()) {
    await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByLabel("Confirm password").fill("Live-review-password-C1!");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }

  await page.goto("http://127.0.0.1:8765/#/memory");
  await expect(page.getByRole("heading", { name: "Memory", level: 2 })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Incognito session" })).toBeVisible();
  await expect(page.getByText("No approved memories yet")).toBeVisible();
  await expect(page.getByText("Advanced memory management")).toBeVisible();
  await page.screenshot({ path: "../../docs/plans/screenshots/working/memory-redesign-live.png", fullPage: true });

  await page.goto("http://127.0.0.1:8765/#/brain");
  await expect(page.getByRole("heading", { name: "Knowledge Map", level: 2 })).toBeVisible();
  await expect(page.getByText(/does not display hidden model reasoning/i)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Map" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "List" })).toBeVisible();
  await page.screenshot({ path: "../../docs/plans/screenshots/working/knowledge-map-redesign-live.png", fullPage: true });

  await page.route("**/api/sessions/*/context-usage", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      session_id: "sess_live", profile_id: "hosted", provider: "Anthropic", model: "claude-opus-5",
      used_tokens: 86, context_window_tokens: 1_000_000, context_window_source: "provider",
      usage_source: "provider", billable: true, session_cost: null, provider_total_cost: null,
      currency: "USD", price_source: null, price_as_of: null, session_turns: 1,
      session_input_tokens: 72, session_output_tokens: 14,
    }) });
  });
  await page.route("**/api/sessions/sess_live", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      session: {
        session_id: "sess_live", principal_id: "principal_owner", status: "active", created_at: "2026-07-29T12:00:00Z",
        updated_at: "2026-07-29T12:00:00Z", turn_count: 0, pinned: false, tags: [], project_id: null,
        archived: false, archived_at: null, origin: "chat",
      },
      turns: [],
    }) });
  });
  await page.route("**/api/sessions/sess_live/attachments", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ files: [] }) });
  });
  // Continue a known session so opening the popover performs the governed
  // context-usage read. The session transcript itself may be absent in this
  // clean live workspace; context usage remains independently testable.
  await page.goto("http://127.0.0.1:8765/#/new-chat?session=sess_live");
  await page.getByRole("button", { name: "Context window" }).click();
  await expect(page.getByText("86 tokens used")).toBeVisible();
  await expect(page.getByText("<0.01%")).toBeVisible();
  await expect(page.getByText("999,914 tokens remaining")).toBeVisible();
  await page.screenshot({ path: "../../docs/plans/screenshots/working/context-window-redesign-live.png", fullPage: true });
});
