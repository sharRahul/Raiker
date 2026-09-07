import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

test("live Memory, Knowledge Map, and context usage review", async ({ page }) => {
  await signInAsOwner(page, "http://127.0.0.1:8765");

  await page.goto("http://127.0.0.1:8765/#/memory");
  await expect(page.getByRole("heading", { name: "Memory", level: 1 })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Incognito session" })).toBeVisible();
  await expect(page.getByText("No approved memories yet")).toBeVisible();
  await expect(page.getByText("Advanced memory management")).toBeVisible();
  await capture(page, "../../docs/plans/screenshots/working/memory-redesign-live.png");

  await page.goto("http://127.0.0.1:8765/#/brain");
  await expect(page.getByRole("heading", { name: "Knowledge Map", level: 1 })).toBeVisible();
  await expect(page.getByRole("application", { name: /Interactive force-directed knowledge graph/i })).toBeVisible();
  await expect(page.getByRole("button", { name: "Global" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Local" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add workspace source" })).toBeVisible();
  await page.getByRole("button", { name: "Graph settings" }).click();
  await expect(page.getByRole("complementary", { name: "Graph settings" })).toBeVisible();
  await expect(page.getByText("Centre force")).toBeVisible();
  await expect(page.getByText("Always alive")).toBeVisible();
  await capture(page, "../../docs/plans/screenshots/working/knowledge-map-redesign-live.png");

  await page.route("**/api/sessions/*/context-usage", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      session_id: "sess_live", profile_id: "ollama-local-openai-compatible", provider: "Ollama", model: "qwen2.5:7b",
      used_tokens: 8_240, context_window_tokens: 32_768, context_window_source: "provider",
      usage_source: "provider", billable: false, session_cost: null, provider_total_cost: null,
      currency: null, price_source: null, price_as_of: null, session_turns: 1,
      session_input_tokens: 8_100, session_output_tokens: 140,
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
  await expect(page.getByText("8,240 tokens used")).toBeVisible();
  await expect(page.getByText("25.15%")).toBeVisible();
  await expect(page.getByText("24,528 tokens remaining")).toBeVisible();
  await expect(page.getByText(/Reported by Ollama/)).toBeVisible();
  await expect(page.getByText(/Capacity reported by runtime/)).toBeVisible();
  await expect(page.getByText(/no API cost/i)).toBeVisible();
  await capture(page, "../../docs/plans/screenshots/working/local-context-window-live.png");
});
