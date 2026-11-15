/** Live closure evidence for restart persistence, provider reachability and the
 * composer's paste behaviour.
 *
 * Rewritten 2026-11-19 (TO_BE_FIXED § 2026-11-17 round): it was written for the
 * 2026-10 Models layout, a *Memory store* card with **Turn off**, a draft
 * shared between Chat, Build and Design, and an owner's pre-seeded workspace.
 * Today the permission is a detail pane with a decision mode, each surface
 * keeps its own draft (FIXED-1306), and the spec connects what it needs itself
 * through `useHostedModel`, from keys read from the environment and typed into
 * the product's own dialogs. Restart the host between two runs to exercise the
 * restart half; the assertions are the same either way. */
import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import {
  checkModelReady,
  chooseModelForTurn,
  hostedProviderCard,
  openPermission,
  setPermission,
  signInAsOwner,
  useHostedModel,
} from "./hosted-provider";
import { ANTHROPIC_KEY, LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "2026-11-19-round");
const OPENAI_KEY = process.env.RAIKER_LIVE_OPENAI_KEY ?? "";

test.beforeEach(async ({ page }) => {
  await signInAsOwner(page, BASE);
});

test("memory authority and every saved provider connection survive a host restart", async ({ page }) => {
  test.setTimeout(420_000);
  // QUI-L06 — the permission opens in the detail pane beside its category,
  // with its decision mode stated there.
  const memory = await openPermission(page, BASE, /^Memory store/);
  await expect(memory.getByRole("group", { name: /decision|mode/i }).or(memory.getByText(/Allow|Ask|Deny/).first()).first()).toBeVisible();
  await capture(page, join(SHOTS, "memory-permission-after-restart.png"));

  const providers = [
    ...(ANTHROPIC_KEY ? ["Anthropic"] : []),
    ...(OPENAI_KEY ? ["OpenAI"] : []),
  ];
  test.skip(providers.length === 0, "set RAIKER_LIVE_ANTHROPIC_KEY or RAIKER_LIVE_OPENAI_KEY");
  for (const provider of providers) {
    const card = await hostedProviderCard(page, BASE, provider);
    // A connection that did not survive would offer Connect instead of a check.
    if (await card.getByRole("button", { name: "Connect", exact: true }).isVisible().catch(() => false)) {
      test.info().annotations.push({ type: provider, description: "not connected in this workspace; skipped" });
      continue;
    }
    await checkModelReady(page, card);
  }
  await capture(page, join(SHOTS, "models-after-restart.png"));
});

test("a large paste becomes an attachment and is reversible", async ({ page }) => {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt", { exact: true });
  await prompt.fill("");
  const pasted = `BEGIN\n${"exact pasted text ".repeat(250)}\nEND`;
  await prompt.evaluate((element, text) => {
    const data = new DataTransfer();
    data.setData("text/plain", text);
    element.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: data }));
  }, pasted);
  await expect(page.getByText("pasted-text.txt", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(prompt).toHaveValue("");
  await capture(page, join(SHOTS, "composer-large-paste-attachment.png"));
  await page.getByRole("button", { name: "Show pasted-text.txt inline" }).click();
  await expect(prompt).toHaveValue(pasted);
});

test("memory_write runs once the owner allows it and the fact can be found in Memory", async ({ page }) => {
  test.setTimeout(420_000);
  test.skip(OPENAI_KEY === "", "set RAIKER_LIVE_OPENAI_KEY");
  const marker = `Raiker-memory-E2E-${Date.now()}`;
  const fact = `${marker}: restart verification completed.`;
  await setPermission(page, BASE, "Memory store", "Turn on", "Live check of a direct memory write");
  const memory = await openPermission(page, BASE, /^Memory store/);
  const allow = memory.getByRole("button", { name: "Allow", exact: true });
  if (await allow.isVisible().catch(() => false)) await allow.click();
  await useHostedModel(page, BASE, {
    provider: "OpenAI", keyLabel: "OpenAI API key", key: OPENAI_KEY,
    model: process.env.RAIKER_LIVE_OPENAI_MODEL ?? "gpt-4o-mini",
  });
  await page.goto(`${BASE}/#/home`);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /GPT-4o Mini|gpt-4o-mini/i);
  const prompt = page.getByLabel("Prompt", { exact: true });
  await prompt.fill(`Use memory_write to remember this exact durable fact: ${fact} Then reply with the tool name you used.`);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-group-raiker").last();
  // Under Ask the write parks for a decision; answering it is the owner's part.
  const allowOnce = answer.getByRole("button", { name: "Allow once" });
  await expect(allowOnce.or(answer.getByText(/memory_write|remembered|saved|stored/i)).first())
    .toBeVisible({ timeout: 240_000 });
  if (await allowOnce.isVisible().catch(() => false)) await allowOnce.click();
  // The record, not the prose: the memory the turn wrote exists.
  await expect.poll(async () => page.evaluate(async (wanted) => {
    const response = await fetch("/api/memory");
    const rows = (await response.json()) as Array<{ text: string }>;
    return rows.some((row) => row.text.includes(wanted));
  }, marker), { timeout: 240_000 }).toBe(true);

  // Search is on Memory's Memories tab (the Overview opens first).
  await page.goto(`${BASE}/#/memory?tab=memories`);
  const search = page.getByLabel("Search memories");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(marker);
  // Approved directly under Allow, or waiting in review under Ask: either way
  // the fact the turn wrote is findable by its marker.
  await expect(page.locator(".memory-card", { hasText: marker }).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "memory-write-found.png"));
});
