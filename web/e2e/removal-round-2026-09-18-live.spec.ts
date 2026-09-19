import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import {
  chooseModelForTurn,
  enableCapability,
  signInAsOwner,
  useHostedModel,
} from "./hosted-provider";

/**
 * The 2026-09-18 pass of the removal and simplification review, driven live.
 *
 * Five rows of §18.3, each of which is a claim about what an owner sees on a
 * page rather than about a function's return value — which is why each is
 * checked here and not only in a unit test:
 *
 * * **REM-THREAD-03** — a thread resumes on the surface it was done on, and the
 *   technical record behind it is a link beside the row rather than the row's
 *   destination.
 * * **REM-SESSIONS** — the inspector is the inspector: one routed way back, and
 *   no second "Open" into Chat on every row.
 * * **REM-MEM-01** — a memory card offers Edit, Pin and More, not seven equally
 *   prominent controls.
 * * **REM-OBSERVE** — Observability opens with what is wrong, and the resting
 *   state of a healthy install is below it.
 * * **REM-LIVE** — Work in action has a non-animated equivalent carrying the
 *   same records.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-18-round");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

/** One real Chat turn, so there is a thread to read back. */
async function oneChatTurn(page: Page, text: string): Promise<void> {
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(text);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toBeVisible({ timeout: 240_000 });
  await expect
    .poll(async () => ((await answer.textContent()) ?? "").trim().length, {
      timeout: 240_000,
      intervals: [1_000],
    })
    .toBeGreaterThan(20);
}

test.describe("removal round, 2026-09-18", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");
    test.setTimeout(300_000);
    await signInAsOwner(page, BASE);
  });

  test("REM-THREAD-03 — a thread resumes where it was done, with the record beside it", async ({
    page,
  }) => {
    await useHostedModel(page, BASE, {
      provider: "Anthropic",
      keyLabel: "API key",
      key: ANTHROPIC_KEY,
      model: MODEL,
    });
    await oneChatTurn(page, "Name one thing a governed runtime records about a turn.");

    await page.goto(`${BASE}/#/search-chat`);
    const row = page.locator("ul.threads li").first();
    await expect(row).toBeVisible({ timeout: 30_000 });

    // The row opens the surface that owns the work — Chat here, because the
    // turn above was sent from Chat — and says so on the row itself.
    await expect(row.locator("a").first()).toHaveAttribute("href", /^#\/new-chat\?session=/);
    await expect(row).toContainText("Chat");
    // Found while proving this row: every chat thread reported "0 turns",
    // because `list_sessions` returns the session row and a session row has no
    // turn count in it. A thread that has just answered has at least one.
    await expect(row).toContainText(/\d+ turns?/);
    await expect(row).not.toContainText("0 turns");

    // And the technical record is a link beside the row rather than its
    // destination: Threads resumes work, the inspector verifies it.
    const evidence = row.getByRole("link", { name: "Evidence" });
    await expect(evidence).toBeVisible();
    await expect(evidence).toHaveAttribute("href", /^#\/sessions\?session=/);
    await capture(page, join(SHOTS, "threads-work-mode-and-evidence.png"));

    await evidence.click();
    // The inspector opens on that session, with its turns listed — which is the
    // record behind the thread, not another copy of the conversation.
    await expect(page.locator("ol.turns li").first()).toBeVisible({ timeout: 30_000 });
    expect(page.url()).toContain("/sessions?session=");
  });

  test("REM-SESSIONS — the inspector offers one routed way back, not a second library", async ({
    page,
  }) => {
    await page.goto(`${BASE}/#/observe?tab=sessions`);
    const row = page.locator("tr.row-btn").first();
    await expect(row).toBeVisible({ timeout: 30_000 });

    // The row used to carry an "Open" link straight into Chat. Resuming lives
    // in Threads now, and this page says so.
    await expect(row.getByRole("link", { name: "Open" })).toHaveCount(0);
    // Scoped to the page's own lead: the navigation rail carries a Threads link
    // on every screen, and matching that would assert nothing about this one.
    await expect(page.locator("p.page-lead").getByRole("link", { name: "Threads" })).toBeVisible();

    await row.locator(".session-title").click();
    // One way back, named for the surface that owns the conversation — not the
    // two side-by-side guesses ("Open in chat" / "Open in Build") every session
    // used to be offered.
    await expect(page.getByRole("link", { name: "Resume in Chat" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByRole("link", { name: "Open in chat" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Open in Build" })).toHaveCount(0);
    await capture(page, join(SHOTS, "sessions-evidence-inspector.png"));
  });

  test("REM-OBSERVE — the overview opens with what is wrong", async ({ page }) => {
    await page.goto(`${BASE}/#/observe?tab=overview`);
    const attention = page.getByRole("heading", { name: "Needs your attention" });
    await expect(attention).toBeVisible({ timeout: 30_000 });

    // It is the first section, above the resting-state tiles it used to sit
    // seven of below.
    const headings = await page.locator("h2.section-h").allInnerTexts();
    expect(headings[0]).toBe("Needs your attention");

    // Diagnostics is a specialist view behind a disclosure rather than a full
    // page rendered inline on every visit.
    const specialist = page.locator("details.specialist");
    await expect(specialist).toHaveCount(1);
    await expect(specialist).not.toHaveAttribute("open", "");
    await capture(page, join(SHOTS, "observe-attention-first.png"));
  });

  test("REM-MEM-01 — a memory card offers Edit, Pin and More", async ({ page }) => {
    // Seeded through the owner's own governed path rather than skipped: a card
    // is what this row is about, and a round with no approved memory would
    // report "nothing to check" as though it were a pass. The gate first,
    // because the page is a viewer until the owner opens it — which is the
    // product being right, not an obstacle.
    await enableCapability(page, BASE, "Memory store", "Seeding a record for the REM-MEM-01 round.");

    await page.goto(`${BASE}/#/memory?tab=memories`);
    const grid = page.locator(".memory-grid article.memory-card");
    if (!(await grid.first().isVisible().catch(() => false))) {
      // The import drawer lives on Recall & indexing, with the other things
      // that act on the store rather than on one record.
      await page.goto(`${BASE}/#/memory?tab=recall`);
      const advanced = page.locator("details.advanced");
      await expect(advanced).toBeVisible({ timeout: 30_000 });
      await advanced.locator("summary").click();
      await advanced.locator('input[type="file"]').setInputFiles({
        name: "seed-memories.json",
        mimeType: "application/json",
        buffer: Buffer.from(
          JSON.stringify({
            memories: [{ text: "The owner prefers short, direct answers.", scope: "account" }],
          }),
        ),
      });
      await advanced
        .getByRole("button", { name: /^Import / })
        .first()
        .click();
      await page.goto(`${BASE}/#/memory?tab=memories`);
      await expect(grid.first()).toBeVisible({ timeout: 60_000 });
    }

    const card = grid.first();
    const actions = card.locator(".card-actions button");
    await expect(actions).toHaveCount(3);
    await expect(card.getByRole("button", { name: /^More for/ })).toBeVisible();

    await card.getByRole("button", { name: /^More for/ }).click();
    const drawer = card.getByRole("region", { name: "Memory record" });
    await expect(drawer).toBeVisible();
    // The controls that changed what Raiker remembers are here, each with its
    // own consequence stated rather than sharing one sentence with the others.
    for (const name of ["View source", "View history", "Edit scope", "Review expiry", "Forget", "Delete permanently"]) {
      await expect(drawer.getByRole("button", { name })).toBeVisible();
    }
    await capture(page, join(SHOTS, "memory-record-drawer.png"));
  });

  test("REM-LIVE — Work in action has a list that does not move", async ({ page }) => {
    await page.goto(`${BASE}/#/observe?tab=work`);
    const list = page.getByRole("button", { name: "List" });
    await expect(list).toBeVisible({ timeout: 30_000 });
    await list.click();
    // The list is what renders, whether or not this workspace has anything in
    // it: a table of the recorded work, or the one line that says there is
    // none. What must not be there is a floor full of characters.
    await expect(page.getByRole("heading", { name: "Live work" })).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("article.desk")).toHaveCount(0);
    await expect(
      page.getByRole("table", { name: "Live work" }).or(page.locator("p.empty")).first(),
    ).toBeVisible({ timeout: 30_000 });
    await capture(page, join(SHOTS, "work-in-action-list.png"));

    // And the floor is still there, one press away, for the reader who wants it.
    await page.getByRole("button", { name: "Workstations" }).click();
    await expect(page.getByRole("region", { name: "Agent workstations" })).toBeVisible({
      timeout: 30_000,
    });
  });

  test("REM-EXT-01 — Extensions says what is installed before it explains anything", async ({
    page,
  }) => {
    // Something has to be installed before "what is installed" can be checked,
    // and on a workspace with nothing the lead above already says so — which is
    // the page being right, not the row being unmet. So the round installs one,
    // through the builder, which is an owner path rather than a fixture.
    await page.goto(`${BASE}/#/extensions?tab=skills`);
    if (!(await page.getByText("release-notes").first().isVisible().catch(() => false))) {
      await page.getByRole("button", { name: "Add a skill" }).click();
      await page
        .getByRole("group", { name: "Where the skill comes from" })
        .getByRole("button", { name: /Write one here/ })
        .click();
      await page.getByLabel("Name").fill("release-notes");
      await page
        .getByLabel(/^Description/)
        .fill("Draft release notes. Use when cutting a release or summarising a diff.");
      await page
        .getByLabel("Instructions")
        .fill("# Release notes\n\n1. Read the diff since the last tag.");
      await page.getByRole("button", { name: "Build and install" }).click();
      await expect(page.getByText("release-notes").first()).toBeVisible({ timeout: 60_000 });
    }

    await page.goto(`${BASE}/#/extensions?tab=overview`);
    await expect(page.getByRole("heading", { name: "What Raiker can reach" })).toBeVisible({
      timeout: 30_000,
    });
    // The inventory: what have I got, without opening five tabs in turn.
    await expect(page.getByRole("heading", { name: "What is installed" })).toBeVisible();
    await expect(page.locator("ul.inventory")).toContainText("Skills");
    // Found while proving this row: the lead counted only the two kinds
    // `/api/extensions` carries, so a workspace with installed skills was told
    // "Nothing is installed yet." above a list of what is.
    await expect(page.getByText("Nothing is installed yet")).toHaveCount(0);
    await capture(page, join(SHOTS, "extensions-inventory.png"));

    // And the operator reference is a disclosure rather than a card of equal
    // weight beside the state.
    await page.goto(`${BASE}/#/extensions?tab=hooks`);
    const reference = page.getByRole("heading", { name: "What a handler may be" });
    await expect(reference).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("a bounded program in your workspace")).toBeHidden();
  });

  test("REM-SKILL-01 — one Add skill entry, and the mode chosen before a form", async ({
    page,
  }) => {
    await page.goto(`${BASE}/#/extensions?tab=skills`);
    const add = page.getByRole("button", { name: "Add a skill" });
    await expect(add).toBeVisible({ timeout: 30_000 });
    // None of the three forms is on screen until the owner has said which.
    await expect(page.getByLabel("Skill URL")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Choose a file" })).toHaveCount(0);

    await add.click();
    const modes = page.getByRole("group", { name: "Where the skill comes from" });
    await expect(modes).toBeVisible();
    await modes.getByRole("button", { name: /From a link/ }).click();
    await expect(page.getByLabel("Skill URL")).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose a file" })).toHaveCount(0);
    await capture(page, join(SHOTS, "skills-one-add-entry.png"));
  });

  test("REM-SET-SECURITY — four sections, one per lifecycle", async ({ page }) => {
    await page.goto(`${BASE}/#/settings?tab=security`);
    for (const name of [
      "Signing in and devices",
      "Encryption and the vault",
      "Findings and monitoring",
      "Standing access",
    ]) {
      await expect(page.getByRole("heading", { name })).toBeVisible({ timeout: 30_000 });
    }
    // Nothing was removed on the way: the controls that were in the one stack
    // are each still here, under the lifecycle they belong to.
    for (const name of [
      "Password",
      "Multi-factor authentication (TOTP)",
      "Active device sessions",
      "Database encryption",
      "Connector Vault Key",
      "Credential security",
      "Monitored capabilities",
      "Standing approval grants",
    ]) {
      await expect(page.getByRole("heading", { name })).toBeVisible();
    }
    await capture(page, join(SHOTS, "settings-security-lifecycles.png"));
  });
});
