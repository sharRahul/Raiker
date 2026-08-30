/**
 * BUG-244 and BUG-246, against a real instance.
 *
 * Both are defects a unit test can describe and only a running product can
 * prove, because both are about what the owner is *told* at the moment they
 * decide.
 *
 * * **BUG-244 — an import was the one way to make a duplicate.** Every other
 *   correction path in memory has an answer for the same sentence arriving
 *   twice; import simply wrote again, and reported the number of records in the
 *   file rather than the number it changed. Recall is budgeted, so four copies
 *   of one sentence occupy four of the slots a turn has for remembering
 *   anything — which is how it was noticed at all.
 * * **BUG-246 — the authority matrix hid its own verdicts on a phone.** Three
 *   columns at 390 px meant the *Raiker agent* column scrolled off screen and
 *   every row read "Unavail". Nothing was lost and nothing lied; the answer was
 *   simply the part you had to scroll for.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

/** One export file, chosen in Memory → Advanced management → Review import. */
async function chooseImportFile(records: Array<{ text: string; scope?: string }>) {
  // Advanced management is a `<details>`, and clicking its summary *toggles*
  // it — so a second call would close what the first opened.
  const advanced = page.locator("details.advanced");
  if (!(await advanced.evaluate((node) => (node as HTMLDetailsElement).open))) {
    await page.getByText("Advanced memory management").click();
  }
  await page.locator(".file-button input[type=file]").setInputFiles({
    name: "round-import.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ memories: records })),
  });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  test.setTimeout(300_000);
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signInAsOwner(page, BASE);
});

test.afterAll(async () => {
  await context?.close();
});

test("a re-import says what is already stored, and writes only what is new", async () => {
  test.setTimeout(300_000);
  const marker = `Import round ${Date.now()}`;
  const records = [{ text: `${marker} — first sentence.` }, { text: `${marker} — second sentence.` }];

  await page.goto(`${BASE}/#/memory`);
  await expect(page.locator("main#main")).toBeVisible();
  await chooseImportFile(records);

  // Nothing is stored yet, so both records are new and the ordinary import is
  // what is offered.
  const review = page.locator(".import-review");
  await expect(review).toBeVisible({ timeout: 30_000 });
  // The count is stated before the button that acts on it, so it is read from
  // the sentence rather than from the button's own label.
  await expect(review.locator("strong", { hasText: /^2 new$/ })).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "bug-244-01-first-import-two-new.png"), review);
  await page.getByRole("button", { name: /^Import 2 new records$/ }).click();
  await expect(page.getByText("Imported 2 records.")).toBeVisible({ timeout: 60_000 });

  // The same file again. This is the defect: before, it wrote two more copies
  // and said "2 valid records" both times.
  await chooseImportFile(records);
  await expect(review).toBeVisible({ timeout: 30_000 });
  await expect(review.getByText(/All 2 records are already stored/)).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "bug-244-02-re-import-already-stored.png"), review);
  // The deliberate second copy is still offered — an owner who means to hold the
  // same sentence at a second scope is doing something legitimate.
  await expect(page.getByRole("button", { name: "Import anyway" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Import \d+ new record/ })).toHaveCount(0);
});

test("the delegated-authority verdicts are readable at a phone width", async () => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/#/capabilities`);
  await expect(page.locator("main#main")).toBeVisible();

  const cards = page.locator(".matrix-cards");
  await expect(cards).toBeVisible({ timeout: 30_000 });
  // The verdict column is the one that used to be off screen. Every entry now
  // carries its own label, and the whole card fits the viewport.
  const first = cards.locator("li").first();
  await expect(first.getByText("Raiker agent")).toBeVisible();
  const fits = await first.evaluate(
    (node) => node.getBoundingClientRect().right <= window.innerWidth + 1,
  );
  expect(fits).toBe(true);
  // No row is cut mid-word any more, and nothing scrolls sideways.
  await expect(page.getByText("Unavail", { exact: true })).toHaveCount(0);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await capture(page, join(SHOTS, "bug-246-01-authority-at-phone-width.png"));
  await page.setViewportSize({ width: 1440, height: 1000 });
});
