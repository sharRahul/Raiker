/**
 * The 2026-09-16 round, driven against a running host with a real Anthropic key.
 *
 * Four things landed in this round that a document can assert and a product can
 * fail to deliver, so each is driven here rather than reasoned about:
 *
 * 1. **BUG-300** — a turn that declared a table is *the same answer* wherever it
 *    is read back. Exported, reopened from the record, and read aloud, it stops
 *    being the raw ` ```raiker:table ` fence with its JSON. Driven from a real
 *    turn, because the declaration has to come from a model for the export to
 *    have anything to export.
 * 2. **REM-MAP-02** — a Knowledge Map with nothing in it says so, instead of
 *    handing a new owner three placeholder nodes that behave like records.
 * 3. **REM-MAP-04** — the same records, the same rejection and the same
 *    evidence, as a list, with the simulation stopped.
 * 4. **REM-GUIDE** — Build and the Knowledge Map can reach the guide. Build
 *    shipped `working-in-build.md` and had no way to open it.
 *
 * The key is entered through the product's own Connect dialog, because the
 * screen an owner sees is the only screen worth testing.
 */
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const SHOTS = "../../docs/screenshots";

test.describe.configure({ mode: "serial" });

/** Console errors are a budget, and a round that spends it silently is not evidence. */
function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

/**
 * Ask for an answer with a declared table in it, and wait until it is on screen.
 *
 * The prompt names the data and the destination rather than the encoding: the
 * point is that the model reaches for the declared channel because it was told
 * the channel exists (FIXED-545), not that it can copy a payload back.
 */
async function askForATable(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku 4\.5/i);
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 60_000 });
  await composer.fill(
    "Three cities and their approximate populations in millions: Tokyo 37, Delhi 33, " +
      "Shanghai 29. Show me that here in this conversation as a table with the columns " +
      "City and Millions. Do not create a file.",
  );
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();
  await expect(page.getByRole("table").first()).toBeVisible({ timeout: 300_000 });
}

test("a Knowledge Map with nothing in it says so, and offers the way to record something", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/brain`);
  await expect(page.getByRole("heading", { name: "Knowledge Map" })).toBeVisible({
    timeout: 60_000,
  });

  // REM-MAP-02 is about a workspace that has recorded nothing, so it runs
  // before the turn below fills the map — and says so rather than failing when
  // a re-run finds a workspace that has been worked in. Same convention as
  // `requireFirstRunWorkspace`: a round that reuses an instance should be told
  // which scenarios need their own, not left to read it out of an assertion.
  // Read from the count pill rather than sampled with `isVisible()`, which does
  // not wait: the pill renders a frame after the graph resolves, so an
  // immediate check answered "no records here" about a page that had not
  // finished drawing and skipped the scenario it was meant to run.
  const pill = page.locator("button.summary-pill");
  await expect(pill).toBeVisible({ timeout: 60_000 });
  test.skip(
    !((await pill.textContent()) ?? "").includes("Nothing recorded yet"),
    "This workspace already holds records, so its map is not empty. " +
      "Reset it with scripts/reset_live_workspace.py to run this scenario.",
  );

  // REM-MAP-02. The three placeholder nodes and two placeholder edges are gone:
  // they were flagged `is_real: false` and labelled "Starter view", and they
  // were still selectable, centreable objects in the one surface whose job is
  // to show what the workspace actually knows.
  await expect(page.getByText("Nothing in the map yet")).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("button", { name: /Workspace, workspace record/i }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Add first source, source record/i })).toHaveCount(
    0,
  );
  // The way out is in the empty state instead of inside a node.
  await expect(page.getByRole("button", { name: /Add source$/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open Memory/ })).toHaveAttribute(
    "href",
    "#/memory",
  );

  // REM-GUIDE — one contextual link, on a page that had none.
  await expect(page.getByRole("link", { name: /How the Knowledge Map works/ })).toBeVisible();

  await capture(page, `${SHOTS}/knowledge-map-empty-state.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("a declared table is still a table when the conversation is exported", async ({ page }) => {
  test.setTimeout(600_000);
  test.skip(KEY === "", "needs RAIKER_LIVE_ANTHROPIC_KEY");
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: KEY,
    model: MODEL,
  });

  await askForATable(page);

  // The review comes before the format, which is what the dialog is for — and
  // it now says the export will carry a table, rather than leaving the owner to
  // discover that from the file.
  await page.getByRole("button", { name: "Conversation actions" }).click();
  await page.getByRole("menuitem", { name: /Export/i }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Export conversation" })).toBeVisible({
    timeout: 60_000,
  });
  await expect(
    dialog.getByRole("listitem").filter({ hasText: /tables? (and|or) charts?/i }),
  ).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/export-review-declared-parts.png`);

  // Markdown, because a GFM table is the one an assertion can read without a
  // parser, and because it is the format somebody commits or pastes.
  await dialog.getByRole("radio", { name: "Markdown" }).check();
  const download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Export", exact: true }).click();
  const exported = readFileSync(await (await download).path(), "utf-8");

  // BUG-300's interface outcome, on the medium it names: a GFM table where the
  // conversation showed a table, and not the fence the model wrote.
  expect(exported).not.toContain("raiker:table");
  expect(exported).toMatch(/\|[^\n|]*City[^\n|]*\|/i);
  expect(exported).toMatch(/\|\s*-+\s*\|/);
  expect(exported).toMatch(/Tokyo/);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("a reopened conversation and the Sessions inspector show the same table", async ({
  page,
}) => {
  test.setTimeout(300_000);
  test.skip(KEY === "", "needs RAIKER_LIVE_ANTHROPIC_KEY");
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);

  // The conversation the previous test produced, reopened from the record
  // rather than watched live. Its parts are derived server-side by the same
  // splitter, so there is one reading of one answer.
  await page.goto(`${BASE}/#/observe?tab=sessions`);
  // The newest conversation, which is the one the turn above produced. Reached
  // from its own row rather than by text, because the prompt appears in five
  // cells of it and a text match would land on whichever came first.
  const rows = page.getByRole("table").first().getByRole("row");
  await expect(rows.nth(1)).toBeVisible({ timeout: 60_000 });
  await rows.nth(1).getByRole("cell").nth(1).click();

  // The turn, inside the detail the click opened. `turn-btn` is the row; the
  // inspector below it is what this test is about.
  const turn = page.locator("button.turn-btn").first();
  await expect(turn).toBeVisible({ timeout: 30_000 });
  await turn.click();

  // Before this, the inspector printed the fence and its JSON here.
  const inspector = page.locator(".answer");
  await expect(inspector.getByRole("table").first()).toBeVisible({ timeout: 60_000 });
  await expect(inspector.getByText("Tokyo")).toBeVisible();
  // Scoped to the answer. The governed events listed underneath quote the raw
  // record on purpose — an audit summary is what the runtime saw, verbatim, and
  // a fence rendered as a table there would be the evidence log editing itself.
  expect(await inspector.textContent()).not.toContain("raiker:table");
  await capture(page, `${SHOTS}/sessions-reopened-typed-answer.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("the Knowledge Map offers the same records as a list", async ({ page }) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/brain`);
  await expect(page.getByRole("group", { name: "How to show records" })).toBeVisible({
    timeout: 60_000,
  });

  // REM-MAP-04 — finding provenance should not require reading graph geometry
  // or waiting for a layout to settle.
  // The preference write is debounced, so the save is waited for rather than
  // assumed: a reload that outruns it would report a preference that was never
  // stored, and blame the feature for the race.
  const saved = page.waitForResponse(
    (response) =>
      response.url().includes("/api/brain/settings") && response.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "List" }).click();
  const list = page.getByRole("table", { name: /Workspace records/i });
  const empty = page.getByText("Nothing in the map yet");
  await expect(list.or(empty).first()).toBeVisible({ timeout: 30_000 });
  // The canvas is not drawing behind it: a simulation ticking under a table is
  // exactly the visualisation-only motion this row is about.
  await expect(page.locator(".graph-workspace.hidden")).toHaveCount(1);
  await capture(page, `${SHOTS}/knowledge-map-list-view.png`);

  // And the choice is a way of working rather than a temporary escape, so it
  // survives a reload with the rest of the display preferences.
  await saved;
  await page.reload();
  await expect(page.getByRole("button", { name: "List" })).toHaveAttribute(
    "aria-pressed",
    "true",
    { timeout: 60_000 },
  );
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Build can open the chapter the product ships about it", async ({ page }) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/build`);

  // REM-GUIDE. `working-in-build.md` shipped and nothing in the product could
  // open it, so the surface with the most to explain was the one that could
  // only explain itself inline.
  const link = page.getByRole("link", { name: /How Build works on a repository/ });
  await expect(link).toBeVisible({ timeout: 60_000 });
  await link.click();

  // It lands on a chapter, not on an empty page.
  await expect(page.getByRole("heading", { name: "Working in Build" })).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, `${SHOTS}/guide-working-in-build.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});
