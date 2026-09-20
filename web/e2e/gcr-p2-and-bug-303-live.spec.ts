import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

/**
 * The 2026-09-20 round, live: BUG-303's conversation library, and the two
 * static-review fixes that only a real turn can show.
 *
 * Three things here cannot be proved anywhere else.
 *
 * **BUG-303.** The library controls — pin, rename, archive, move, tags — moved
 * off Sessions, the evidence inspector, and onto Threads, the board work is
 * resumed from. Unit tests hold each control against a stubbed index; only a
 * real workspace shows the *order* changing when a thread is pinned, the thread
 * leaving the board when it is archived, and the same page being where it comes
 * back from.
 *
 * **GCR-35** (FIXED-567). A follow-up whose previous exchange is larger than the
 * history budget used to reach the model with no conversation at all. The
 * *boundary* is asserted in `tests/test_owner_consent_and_history.py`, where a
 * budget can be set — live, the budget is derived from whatever capacity the
 * connected model advertises, and a 200 000-token context is not something a
 * prompt can overflow. What this proves instead is the outcome the entry is
 * about and the one only a real provider can show: a long exchange followed by
 * a question that *only the earlier turn can answer*, answered from it.
 *
 * **GCR-47** (FIXED-573). The attached-root watcher records its cycles as a
 * background pass, so Diagnostics can say whether it is running. The row only
 * exists once a host has actually run one.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-20-round");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");

/**
 * Send one prompt and wait for the whole answer.
 *
 * *Whole*, not merely present: the reply streams, so a poll that stops at the
 * first non-empty read returns the first sentence of it. Waiting for the length
 * to stop changing is what makes "the answer was long" a fact about the answer
 * rather than about how fast the assertion ran.
 */
async function ask(page: import("@playwright/test").Page, text: string): Promise<string> {
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(text);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toBeVisible({ timeout: 240_000 });

  let settled = -1;
  await expect
    .poll(
      async () => {
        const length = ((await answer.textContent()) ?? "").trim().length;
        const unchanged = length > 20 && length === settled;
        settled = length;
        return unchanged;
      },
      { timeout: 300_000, intervals: [2_000] },
    )
    .toBe(true);
  return ((await answer.textContent()) ?? "").trim();
}

test("a follow-up after a very long answer still reaches the model with the conversation", async ({
  page,
}) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);

  // A first exchange large enough that the budget has to do real work on it:
  // a long prompt and a long answer. The reference number is stated plainly
  // rather than smuggled in — an instruction to "ignore the rest of this
  // message" is prompt-injection shaped, and this model correctly refuses that
  // pattern, which would make the spec measure the refusal instead.
  const background = Array.from(
    { length: 40 },
    (_, index) =>
      `Context note ${index + 1}: the deployment on day ${index + 1} touched the ` +
      "scheduler, the event index and the approval queue, and was reviewed by the " +
      "owner before it shipped.",
  ).join(" ");
  const first = await ask(
    page,
    `Our reference number for this piece of work is MARIGOLD-42. Here is the ` +
      `background: ${background} Now write eight detailed paragraphs explaining ` +
      "what a governed audit log is for and what belongs in one.",
  );
  expect(first.length).toBeGreaterThan(1_000);

  await chooseModelForTurn(page, MODEL_LABEL);
  const followUp = await ask(page, "What reference number did I give you at the start?");
  await capture(page, join(SHOTS, "chat-follow-up-after-an-oversized-exchange.png"));

  expect(followUp).toContain("MARIGOLD-42");
});

test("the conversation library organises a thread from the board it is resumed from", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/search-chat`);

  const firstRow = page.locator("ul.threads > li").first();
  await expect(firstRow).toBeVisible({ timeout: 60_000 });

  // The subject is read from the control's own accessible name rather than from
  // the row's text: a pinned row carries a marker in front of its title, so
  // `.title` and `aria-label` are deliberately not the same string.
  // The row is keyed by the conversation it is about, not by where it currently
  // sits or what it is called: every action below re-reads the index, and the
  // index reorders — a pin moves the row to the top, an archive moves it out of
  // the scope. A spec holding on to "the first row" would organise whichever
  // thread happened to land there.
  const evidenceHref = (await firstRow.getByRole("link", { name: "Evidence" }).getAttribute("href")) ?? "";
  const sessionId = /session=([^&]+)/.exec(evidenceHref)?.[1] ?? "";
  expect(sessionId.length, `no session id in ${evidenceHref}`).toBeGreaterThan(0);

  const row = () =>
    page.locator("ul.threads > li").filter({ has: page.locator(`a[href*="${sessionId}"]`) });

  /**
   * Re-find this thread and open its controls.
   *
   * Retried, because each action re-reads the index and the row is replaced
   * when the answer arrives: a click that lands in the gap toggles a menu on an
   * element that is about to be discarded. That is a property of the harness
   * racing a live re-read, not of the control — an owner clicking a row that is
   * not mid-refresh sees it open first time.
   */
  const organise = async () => {
    const library = row().getByRole("group", { name: /^Organise / });
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const control = row().getByRole("button", { name: /^Organise / });
      await expect(control).toBeVisible({ timeout: 30_000 });
      await control.click();
      if (await library.isVisible().catch(() => false)) return library;
      await page.waitForTimeout(500);
      if (await library.isVisible().catch(() => false)) return library;
    }
    await expect(library).toBeVisible({ timeout: 30_000 });
    return library;
  };

  // BUG-303 — Organise is on the row, on Threads, and a routine thread is
  // offered none of it.
  await capture(page, join(SHOTS, "threads-organise-a-thread.png"), await organise());

  // A pin says so on the row, which is what makes the ordering readable. The
  // control names the state it would move to, so a used workspace may arrive
  // already pinned and has to be put back first.
  let library = row().getByRole("group", { name: /^Organise / });
  if (await library.getByRole("button", { name: "Unpin", exact: true }).count()) {
    await library.getByRole("button", { name: "Unpin", exact: true }).click();
    library = await organise();
  }
  await library.getByRole("button", { name: "Pin", exact: true }).click();
  await expect(row().getByLabel("Pinned")).toBeVisible({ timeout: 30_000 });
  // Pinned first is the ordering the sort promises.
  await expect(
    page.locator("ul.threads > li").first().locator(`a[href*="${sessionId}"]`).first(),
  ).toBeVisible({ timeout: 30_000 });

  // A tag is added from the row, and shows on it.
  library = await organise();
  // By placeholder rather than by label: the label carries the thread's title,
  // and a pinned row's title is prefixed with its marker.
  const tagField = library.getByPlaceholder("Add a tag…");
  await tagField.fill("round-2026-09-20");
  await tagField.press("Enter");
  await expect(row().getByText("round-2026-09-20")).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "threads-pinned-and-tagged.png"));

  // Archiving takes the thread off the board, and the same page is where it
  // comes back from. That reversibility is why Archive could move at all.
  library = await organise();
  await library.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(row()).toHaveCount(0, { timeout: 30_000 });
  const archivedChip = page.getByRole("button", { name: /^Archived \(\d+\)$/ });
  await expect(archivedChip).toBeVisible({ timeout: 30_000 });
  await archivedChip.click();
  await expect(row()).toHaveCount(1, { timeout: 30_000 });
  await capture(page, join(SHOTS, "threads-archived-scope.png"));

  library = await organise();
  await library.getByRole("button", { name: "Restore", exact: true }).click();
  const backChip = page.getByRole("button", { name: /^Back to active \(\d+\)$/ });
  await expect(backChip).toBeVisible({ timeout: 30_000 });
  await backChip.click();
  await expect(row()).toHaveCount(1, { timeout: 30_000 });
});

test("the evidence inspector keeps Delete and says where the library went", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=sessions`);

  const row = page.locator("tr.row-btn").first();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.getByRole("button", { name: /session actions/i }).click();

  const menu = page.getByRole("menu").first();
  await expect(menu).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "sessions-inspector-menu.png"));

  // Found while capturing this evidence: the menu was absolutely positioned
  // inside a card that scrolls, so it opened 131px below the bottom of it and
  // Delete — the only destructive control on the page — was cut off. The
  // question is whether an owner can reach it, so that is what is measured: is
  // the element at Delete's own centre point Delete? A clipped element is still
  // "visible" to a locator and still has a bounding box, so neither of those
  // would have caught it.
  const reachable = await page.evaluate(() => {
    const item = [...document.querySelectorAll('[role="menuitem"]')].find(
      (element) => (element.textContent ?? "").trim() === "Delete",
    ) as HTMLElement | undefined;
    if (item === undefined) return "no Delete item";
    const box = item.getBoundingClientRect();
    const x = box.left + box.width / 2;
    const y = box.top + box.height / 2;
    if (y > window.innerHeight || y < 0) return `off-screen at y=${Math.round(y)}`;
    const hit = document.elementFromPoint(x, y);
    return hit === item || item.contains(hit) ? "reachable" : `covered by ${hit?.tagName}`;
  });
  expect(reachable, "Delete must be reachable in the row menu").toBe("reachable");

  // BUG-303 — none of the four library controls, and one line saying where they
  // are. Delete stays: it removes the audit record this page is about.
  for (const gone of [/^Rename$/, /^Move to project$/, /^Pin$/, /^Archive$/, /^Unarchive$/]) {
    await expect(menu.getByRole("menuitem", { name: gone })).toHaveCount(0);
  }
  await expect(menu.getByRole("menuitem", { name: /Organise in Threads/ })).toHaveAttribute(
    "href",
    "#/search-chat",
  );
  await expect(menu.getByRole("menuitem", { name: /^Delete$/ })).toBeVisible();

  // The tag applied on Threads is readable here, and not editable here.
  await page.keyboard.press("Escape");
  await expect(page.getByText("round-2026-09-20").first()).toBeVisible({ timeout: 30_000 });
  expect(await page.locator('input[aria-label^="Add a tag to"]').count()).toBe(0);
});

test("Diagnostics names the attached-root watcher among its background passes", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  // Diagnostics lives inside Observe → Overview, behind "Runtime health, in
  // detail" — a healthy install does not have to scroll past it.
  await page.goto(`${BASE}/#/observe?tab=overview`);
  const details = page.locator("details.specialist", { hasText: "Runtime health, in detail" });
  await expect(details).toBeVisible({ timeout: 60_000 });
  await details.locator("summary").click();

  // GCR-47 — the watcher records every cycle, success included, under the same
  // background-pass health the host tick uses. It is not a surface of its own.
  const passes = page.getByRole("heading", { name: "Background passes" });
  await expect(passes).toBeVisible({ timeout: 60_000 });
  const watcher = page.getByText("Attached root watch", { exact: false }).first();
  await expect(watcher).toBeVisible({ timeout: 120_000 });
  await capture(page, join(SHOTS, "diagnostics-watcher-health.png"), watcher);
});
