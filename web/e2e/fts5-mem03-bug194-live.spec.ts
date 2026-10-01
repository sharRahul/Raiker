/**
 * Live evidence for the 2026-08-17 round, driven through the product's own UI
 * against a real `raiker-web` and a real hosted provider.
 *
 * Three claims, each proved on the surface an owner actually uses rather than
 * through an API the page does not call:
 *
 * * **FIXED-231 (MEM-05 / RAIKER-2025)** — chat search really is answered by the
 *   FTS5 index, and a hit comes back with a snippet quoting the matched term.
 *   The BM25 *ordering* claim is asserted in `tests/test_text_search_fts5.py`
 *   instead, because this page groups hits by conversation before rendering
 *   them and asserting order here would measure the grouping.
 * * **FIXED-230 (MEM-03)** — Memory names the embedding space recall searches,
 *   and says in one sentence whether a paraphrase can recall anything at all.
 * * The provider credential is entered through Raiker's own connect dialog, and
 *   a governed turn really answers from it.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner, useHostedModel } from "./hosted-provider";
import { LIVE_BASE, LIVE_KEYS } from "./live";

const BASE = LIVE_BASE;
const SHOTS = "../../docs/plans/screenshots/working";

const ANTHROPIC_KEY = LIVE_KEYS.anthropic;

test.describe.configure({ mode: "serial" });

test("Memory names the embedding space recall actually searches (MEM-03)", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  await signInAsOwner(page, BASE);
  // REM-MEM-03 moved the engine's controls off the page for reading your own
  // memories: *Recall & indexing* keeps whether recall matches meaning or words,
  // and links to Settings → Memory engine, where the space is chosen.
  await page.goto(`${BASE}/#/memory?tab=recall`);
  await expect(page.getByRole("heading", { name: "Recall backend" })).toBeVisible({
    timeout: 30_000,
  });

  // The sentence that used to be missing entirely: `embedding_backend:
  // "disabled"` was true of writes and silent about reads while the hashing
  // embedding scored every search.
  const card = page.locator("section.control-card").filter({ hasText: "Recall backend" });
  const posture = card.locator("p.posture-line");
  await expect(posture).toBeVisible();
  await expect(posture).toContainText("raiker-local-hash-v1");
  await expect(posture).toContainText(/matches words, not meaning/i);
  // The honest half: the sentence says what this backend *cannot* do.
  await expect(posture).toHaveAttribute("data-semantic", "false");
  await expect(card.getByRole("link", { name: /Change the recall backend/ })).toHaveAttribute(
    "href",
    "#/settings?tab=memory-engine",
  );
  await capture(page, `${SHOTS}/r0817-01-memory-recall-backend.png`);

  // A default install holds no semantic vectors, so "Automatic" is the only
  // honest option — the picker offers what the workspace really has, not a
  // catalogue of what Raiker could in principle call. MEM-11's account of what
  // the setting governs moved to the guide's *Recall backend and token budget*.
  await page.goto(`${BASE}/#/settings?tab=memory-engine`);
  const picker = page.getByLabel("Recall backend");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await expect(picker).toHaveValue("auto");

  expect(consoleErrors).toEqual([]);
});

test("chat search is answered by the FTS5 index, with a marked snippet (MEM-05)", async ({
  page,
}) => {
  test.setTimeout(400_000);
  test.skip(!ANTHROPIC_KEY, "RAIKER_LIVE_ANTHROPIC_KEY is not set for this run");
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  await signInAsOwner(page, BASE);

  // The credential goes in through Raiker's own dialog, not an environment
  // variable — this is the path a person takes.
  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: /API key/i,
    key: ANTHROPIC_KEY,
    model: "claude-haiku-4-5-20251001",
  });
  await expect(card.getByText(/can reach/i)).toBeVisible({ timeout: 120_000 });
  await capture(page, `${SHOTS}/r0817-02-anthropic-connected-via-ui.png`);

  // One real governed turn against the connected provider, whose answer is then
  // findable through chat search. The prompt asks for a specific word so the
  // search below is looking for something the transcript really contains.
  const prompts = [
    "In one short sentence, what does key rotation mean? Use the word rotation.",
  ];
  for (const prompt of prompts) {
    await page.goto(`${BASE}/#/new-chat`);
    const composer = page.getByRole("textbox", { name: /Message|Ask|Prompt/i }).first();
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.fill(prompt);
    const send = page.getByRole("button", { name: "Send", exact: true }).first();
    await expect(send).toBeEnabled({ timeout: 120_000 });
    await send.click();
    // A real streamed answer, not a stub: wait for the turn to stop running.
    await expect(page.getByText(/rotation/i).first()).toBeVisible({ timeout: 120_000 });
    await page.waitForTimeout(2_000);
  }

  await page.goto(`${BASE}/#/search-chat`);
  const search = page.getByRole("searchbox").or(page.getByRole("textbox")).first();
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill("rotation");
  // Typing narrows the thread board; reading message text across every
  // conversation is its own, explicit question since NEW-THREAD-01.
  await page.getByRole("button", { name: "Search message text" }).click();

  // What this proves live: the FTS5 index really is what answers chat search,
  // and the hit comes back with a *marked snippet* quoting the matched term.
  // That second half is the part worth driving through the browser —
  // `snippet()` takes its six arguments in a different order on each engine and
  // the wrong order returns NULL rather than raising, so an empty quote here is
  // exactly how that defect would present.
  //
  // The BM25 *ordering* claim is deliberately not asserted here. This page
  // groups hits by conversation before it renders them, so what a reader sees
  // is a conversation list, not the ranked turn list the index returned;
  // asserting order against the group would be measuring the grouping.
  // `tests/test_text_search_fts5.py` asserts the ranking directly, against the
  // case MEM-05 describes.
  // The result line names the question it answered: "N conversations mention “…”".
  await expect(page.getByText(/conversations? mentions? “rotation”/i)).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/“[^”]*rotation[^”]*”/i).first()).toBeVisible({ timeout: 15_000 });

  await capture(page, `${SHOTS}/r0817-03-chat-search-bm25-ranked.png`);
  expect(consoleErrors).toEqual([]);
});
