/**
 * C17 and B14, live: a memory the owner approved is named in the answer it
 * shaped and correctable there, and a proposed file change is read as a diff in
 * Build rather than in another route.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture, captureElement } from "./capture";
import { chooseModelForTurn, refreshHostedReadiness, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

// BUG-248 — the shared sign-in, which handles a first-run workspace, a locked
// one and the first-run model prompt alike. This spec's own copy only unlocked.
async function signIn() {
  await signInAsOwner(page, BASE);
}

async function send(prompt: string, timeout = 300_000) {
  const composer = page
    .locator("#prompt-input:visible, textarea[placeholder^='Describe']:visible")
    .first();
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  await signIn();
});

test.afterAll(async () => { await context.close(); });

test("C17 — a remembered sentence is named in the answer it shaped, and correctable there", async () => {
  test.setTimeout(600_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");

  // A memory, added through the product's own governed import rather than by
  // waiting on a proposal a fresh account's gates would refuse to produce.
  // The import drawer moved to Recall & indexing, with the other things that
  // act on the store rather than on one record; a record then shows on Memories.
  const remembered = "My nightly backups go to the encrypted NAS in the garage.";
  await page.goto(`${BASE}/#/memory?tab=recall`);
  const advanced = page.locator("details.advanced");
  await expect(advanced).toBeVisible({ timeout: 60_000 });
  if (!(await advanced.evaluate((node) => (node as HTMLDetailsElement).open))) {
    await advanced.locator("summary").click();
  }
  await advanced.locator('input[type="file"]').setInputFiles({
    name: "memories.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ memories: [{ text: remembered, scope: "account" }] })),
  });
  await advanced.getByRole("button", { name: /^Import / }).first().click();
  await page.goto(`${BASE}/#/memory?tab=memories`);
  await expect(page.getByText(remembered).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "fixed-311-memory-page.png"));

  await page.getByRole("link", { name: "Chat", exact: true }).first().click();
  await send("Where do my nightly backups go?");

  const strip = page.getByRole("button", { name: /Remembered \d+/ }).first();
  await expect(strip).toBeVisible({ timeout: 60_000 });
  await strip.click();
  await expect(page.getByRole("button", { name: "Forget" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Correct" }).first()).toBeVisible();
  await capture(page, join(SHOTS, "fixed-311-chat-recall-strip.png"), strip);
});

test("B14 — a proposed file change is read as a diff where it was proposed", async () => {
  test.setTimeout(600_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");
  // Build works inside a project, and a workspace reset for a round has none:
  // make one through Projects, as `bug-242-build-restore-mem-09-live` does.
  await page.goto(`${BASE}/#/projects`);
  const projectName = page.getByLabel("New project name");
  await expect(projectName).toBeVisible({ timeout: 30_000 });
  await projectName.fill(`Inline diff ${Date.now()}`);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /^Open project Inline diff/ }).first(),
  ).toBeVisible({ timeout: 60_000 });

  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  // COMPOSER-03 put the project behind `+`, a turn needs its own model
  // (BUG-292), and Build's action is `Run` (COMPOSER-15) — the same drift
  // `bug-242-build-restore-mem-09-live` records, met here after its sign-in.
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  const picker = page.getByLabel("Project for this build");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ index: 1 });
  await chooseModelForTurn(page, /Haiku 4\.5/, "Build composer");
  await page
    .getByLabel("Describe the change")
    .fill(
      "Write a file called diff-demo.txt in this project containing exactly the line " +
        "'hello from raiker'. Use your tools; do not print it to me.",
    );
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 480_000 });

  // The decision and the change it proposes are on one screen.
  const decisions = page.locator("section.decisions");
  await expect(decisions).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Accept" }).first()).toBeVisible();
  // The diff itself: added and removed lines, the file it touches, and the
  // decision, all in one place.
  await expect(decisions.getByText("diff-demo.txt").first()).toBeVisible({ timeout: 60_000 });
  await expect(decisions.getByText("Added:").first()).toBeAttached({ timeout: 60_000 });
  await captureElement(decisions, join(SHOTS, "fixed-312-build-inline-diff.png"));
});
