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
import { dismissFirstRunModelSetup, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const PASSWORD = "Round-2026-08-17-review-password-1!";

const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test.describe.configure({ mode: "serial" });

async function signIn(page: import("@playwright/test").Page): Promise<void> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  const username = page.getByLabel("Username");
  await expect(username).toBeVisible({ timeout: 20_000 });
  await username.fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /Sign in|Unlock/ }).click();
  }
  await expect(
    page
      .getByRole("button", { name: "Decide later" })
      .or(page.getByRole("heading", { name: "Welcome to your Work Dashboard" }))
      .first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
}

test("Memory names the embedding space recall actually searches (MEM-03)", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  await signIn(page);
  await page.goto(`${BASE}/#/memory`);
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

  // A default install holds no semantic vectors, so "Automatic" is the only
  // honest option — the picker offers what the workspace really has, not a
  // catalogue of what Raiker could in principle call.
  const picker = card.getByLabel("Recall backend");
  await expect(picker).toHaveValue("auto");

  // MEM-11 — the setting used to govern only the memories Raiker attaches on
  // its own; the search the assistant ran itself ignored it. The card may only
  // make this claim now that both paths go through one retrieval.
  // A plain string, not a regex: Playwright normalizes whitespace for string
  // matchers and does not for regex ones, and this sentence wraps in the
  // source — so the regex form fails against the raw text node for a reason
  // that has nothing to do with the product.
  await expect(card.locator("p.control-note")).toContainText(
    "recalls on its own and to the ones the assistant looks up",
  );

  await page.screenshot({
    path: `${SHOTS}/r0817-01-memory-recall-backend.png`,
    fullPage: true,
  });
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

  await signIn(page);

  // The credential goes in through Raiker's own dialog, not an environment
  // variable — this is the path a person takes.
  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: /API key/i,
    key: ANTHROPIC_KEY,
    model: "claude-haiku-4-5-20251001",
  });
  await expect(card.getByText(/can reach/i)).toBeVisible({ timeout: 120_000 });
  await page.screenshot({
    path: `${SHOTS}/r0817-02-anthropic-connected-via-ui.png`,
    fullPage: true,
  });

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
  await page.waitForTimeout(2_500);

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
  await expect(page.getByText(/matching conversation/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/“[^”]*rotation[^”]*”/i).first()).toBeVisible({ timeout: 15_000 });

  await page.screenshot({
    path: `${SHOTS}/r0817-03-chat-search-bm25-ranked.png`,
    fullPage: true,
  });
  expect(consoleErrors).toEqual([]);
});
