/**
 * The 2026-10-02 memory round: §3.9 of the release-readiness review (UX-MEM-01
 * to UX-MEM-08) and UX-PERM-05, driven against a running host.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, with
 * Anthropic connected through Models from `RAIKER_LIVE_ANTHROPIC_KEY` — the key
 * typed into the Connect dialog, never written here.
 */
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-02-memory-round");
const HAIKU = /Haiku 4\.5/i;
const TEA = "My favourite tea is Assam with a splash of oat milk.";

test.describe.configure({ mode: "serial" });

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

/** Hosts this container cannot reach; their refusals are the network's, not Raiker's. */
const UNREACHABLE = /huggingface|openrouter|ollama|503/i;

function memoryFile(name: string, records: Array<{ text: string; scope?: string }>): string {
  const path = join(tmpdir(), name);
  writeFileSync(path, JSON.stringify({ memories: records }));
  return path;
}

async function openImport(page: Page) {
  await page.goto(`${BASE}/#/memory?tab=recall`);
  await settled(page);
  // Going to the address the page is already on navigates nowhere, so the
  // disclosure may still be open from the last step — and a click would close it.
  const advanced = page.locator("details.advanced");
  if (!(await advanced.evaluate((element) => (element as HTMLDetailsElement).open))) {
    await page.getByText("Advanced memory management").click();
  }
}

test("Anthropic connects through Models", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await useAnthropic(page, BASE);
  await capture(page, join(SHOTS, "01-anthropic-connected.png"));
});

test("an import is reviewed record by record and leaves a receipt", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);

  // A first file, so the second has something to be a duplicate of.
  await openImport(page);
  await page.locator('.file-button input[type="file"]').setInputFiles(
    memoryFile("first.json", [{ text: TEA, scope: "account" }, { text: "Deploys happen on Thursdays." }]),
  );
  await page.getByRole("button", { name: /^Import 2 records$/ }).click();
  await expect(page.getByText(/^Imported 2 records\./)).toBeVisible({ timeout: 30_000 });

  // The second file: one stored copy, one re-typed copy, one new, one left out.
  await openImport(page);
  await page.locator('.file-button input[type="file"]').setInputFiles(
    memoryFile("second.json", [
      { text: "Deploys happen on Thursdays." },
      { text: "deploys happen on thursdays" },
      { text: "The staging database is restored every Monday." },
      { text: "Office plants are watered on Fridays." },
    ]),
  );
  const list = page.getByRole("list", { name: "Records in this file" });
  await expect(list).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Not a Raiker export/)).toBeVisible();
  await expect(list.getByText("Already stored")).toBeVisible();
  await expect(list.getByText("Like one you have")).toBeVisible();
  await page.getByRole("checkbox", { name: /Import “deploys happen on thursdays”/ }).uncheck();
  await capture(page, join(SHOTS, "02-import-review.png"), list);
  await page.getByRole("button", { name: /^Import 2 records$/ }).click();
  await expect(
    page.getByText("Imported 2 records; skipped 1 already stored, 1 you left out. You can undo this import below."),
  ).toBeVisible({ timeout: 30_000 });
  const receipts = page.getByRole("region", { name: "Recent imports" });
  await expect(receipts.getByText("from second.json")).toBeVisible();
  await capture(page, join(SHOTS, "03-import-receipts.png"), receipts);
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("a real turn is given a memory, and the record links back to it", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, HAIKU);
  const answers = page.locator(".message-bubble-raiker");
  const before = await answers.count();
  // Asked plainly. Recall's lexical leg needs every content word of the prompt
  // in the record, so "Answer in one sentence." would recall nothing (BUG-313).
  await sendTurn(page, "What is my favourite tea?");
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await expect.poll(async () => answers.count(), { timeout: 60_000 }).toBeGreaterThan(before);
  await expect(page.getByRole("button", { name: /Remembered \d+/ }).last()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "04-chat-remembered.png"));

  await page.goto(`${BASE}/#/memory?tab=memories`);
  await settled(page);
  await page.getByRole("button", { name: /More for “My favourite tea/ }).click();
  const drawer = page.getByRole("region", { name: "Memory record" });
  await expect(drawer.getByText("1 turn")).toBeVisible();
  await expect(drawer.getByText("Imported by you")).toBeVisible();
  await drawer.getByText("Why?").click();
  await capture(page, join(SHOTS, "05-record-usage-and-evidence.png"), drawer);
  await drawer.getByRole("link", { name: "Open the latest" }).click();
  await expect(page).toHaveURL(/#\/new-chat\?session=.+&turn=.+/);
  await expect(page.getByText(/Assam/).last()).toBeVisible({ timeout: 30_000 });
  expect(seen.failures.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
});

test("archive, retention and restore read as one lifecycle", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=memories`);
  await settled(page);

  // Archive one record from the first import: reversible, so it asks nothing.
  // (Archiving one from the second would make undo keep it — an owner's later
  // decision about a record stands, even one they reversed.)
  await page.getByRole("button", { name: /More for “Deploys/ }).click();
  let drawer = page.getByRole("region", { name: "Memory record" });
  await drawer.getByRole("button", { name: "Archive" }).click();
  await expect(page.getByRole("heading", { name: "Deploys happen on Thursdays." })).toBeHidden({ timeout: 30_000 });

  // Put a review date three days out on another.
  const soon = new Date(Date.now() + 3 * 86_400_000).toISOString();
  page.once("dialog", (dialog) => void dialog.accept(soon));
  await page.getByRole("button", { name: /More for “The staging database/ }).click();
  drawer = page.getByRole("region", { name: "Memory record" });
  await drawer.getByRole("button", { name: "Review expiry" }).click();
  // The card's state chip, not the filter's option of the same name.
  await expect(page.locator(".memory-card .state-chip", { hasText: "Expires soon" })).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/memory?tab=overview`);
  await settled(page);
  const pipeline = page.getByRole("region", { name: "How a memory moves through Raiker" });
  await expect(pipeline.getByRole("link", { name: /Recalled/ })).toBeVisible();
  const retention = page.getByRole("region", { name: "Retention" });
  await expect(retention.getByText("Archived")).toBeVisible();
  await capture(page, join(SHOTS, "06-overview-pipeline-retention.png"));

  // The Archived row opens exactly the records it counted, and Restore returns one.
  await retention.locator("li").filter({ hasText: "Archived" }).getByRole("button", { name: "Show" }).click();
  await expect(page).toHaveURL(/filter=archived/);
  await expect(page.getByRole("heading", { name: "Deploys happen on Thursdays." })).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "07-archived-filter.png"));
  await page.getByRole("button", { name: /More for “Deploys/ }).click();
  await page.getByRole("region", { name: "Memory record" }).getByRole("button", { name: "Restore" }).click();
  await expect(page.getByRole("heading", { name: "Deploys happen on Thursdays." })).toBeHidden({ timeout: 30_000 });
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("undoing an import forgets what it wrote, and keeps what was changed since", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await openImport(page);
  page.once("dialog", (dialog) => void dialog.accept());
  const receipts = page.getByRole("region", { name: "Recent imports" });
  await receipts.locator("li").filter({ hasText: "second.json" }).getByRole("button", { name: "Undo import" }).click();
  // The staging record had its expiry changed, so it is the owner's decision now.
  await expect(page.getByText("Undid the import: forgot 1 record. Kept 1 you changed since.")).toBeVisible({
    timeout: 30_000,
  });
  await expect(receipts.getByText(/Undone/)).toBeVisible();
  await capture(page, join(SHOTS, "08-import-undone.png"), receipts);
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("Permissions says what Raiker can do by goal", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/capabilities`);
  await settled(page);
  const goals = page.getByRole("region", { name: "What Raiker can do for you" });
  await expect(goals).toBeVisible({ timeout: 60_000 });
  await expect(goals.getByText(/remember things about you/)).toBeVisible();
  await capture(page, join(SHOTS, "09-permissions-goals.png"), goals);
  await goals.getByRole("button", { name: /Change: .*read web pages/ }).click();
  await expect(page.locator(".cap.card").filter({ hasText: "Web fetch" }).first()).toBeInViewport({ timeout: 30_000 });
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("the Memory overview and Permissions hold at phone width", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=overview`);
  await settled(page);
  await expect(page.getByRole("region", { name: "How a memory moves through Raiker" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await capture(page, join(SHOTS, "10-memory-overview-390.png"));
  await page.goto(`${BASE}/#/capabilities`);
  await settled(page);
  await expect(page.getByRole("region", { name: "What Raiker can do for you" })).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "11-permissions-390.png"));
});
