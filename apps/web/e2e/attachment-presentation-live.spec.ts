/**
 * How an attached file looks, verified with real files.
 *
 * An attachment used to render as a small grey pill with a generic paper icon —
 * the same shape whether you had attached a photograph, a spreadsheet or a
 * folder path. This checks the replacement against a real 2.2 MB JPEG and a
 * real PDF: a picture shows the picture, a document shows its type and size,
 * and what the transcript shows back is the same card the composer showed.
 *
 * The fixtures are supplied through RAIKER_E2E_IMAGE / RAIKER_E2E_PDF so the
 * spec carries no personal files of its own; it skips when they are unset.
 *
 * Start the server first:
 *   python apps/api/main.py --workspace <ws> --port 8765 --no-browser
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { join } from "node:path";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Single-runtime-review-password-1!";

const IMAGE = process.env.RAIKER_E2E_IMAGE ?? "";
const PDF = process.env.RAIKER_E2E_PDF ?? "";

async function signIn(page: Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /unlock|sign in/i }).click();
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });
}

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  await signIn(page);
});

test.afterAll(async () => {
  await page?.close();
});

test("a picture attaches as a picture and a document as a typed card", async () => {
  test.skip(IMAGE === "" || PDF === "", "set RAIKER_E2E_IMAGE and RAIKER_E2E_PDF");
  test.setTimeout(180_000);

  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload image").setInputFiles(IMAGE);
  // The thumbnail is the local file shown back — no request, no placeholder.
  const row = page.getByLabel("Attached to this prompt");
  await expect(row.locator("img")).toBeVisible({ timeout: 30_000 });
  await expect(row.locator("img")).toHaveAttribute("src", /^blob:/);

  // The panel stays open between picks, so a second file is a second choice
  // rather than a second trip through the control.
  await page.getByLabel("Upload document").setInputFiles(PDF);
  // A document states what it is and how big, because those are the two facts
  // you check before sending something.
  await expect(row.getByText("PDF", { exact: false }).first()).toBeVisible({ timeout: 30_000 });

  await expect(row.getByRole("button", { name: /^Remove attachment/ })).toHaveCount(2);
  await page.screenshot({ path: join(SHOTS, "169-composer-attachments-live.png"), fullPage: true });
});

test("what the transcript shows back is what the composer showed", async () => {
  test.skip(IMAGE === "" || PDF === "", "set RAIKER_E2E_IMAGE and RAIKER_E2E_PDF");
  test.setTimeout(180_000);

  await page
    .getByPlaceholder("How can I help you today?")
    .fill("In one short line: what is happening in this photo?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy response" })).toBeVisible({
    timeout: 150_000,
  });

  // The sent turn carries the same cards, and the picture is still a picture.
  const sent = page.locator(".turn-attachments").first();
  await expect(sent.locator("img")).toBeVisible();
  await expect(sent.getByRole("button", { name: /^Open / })).toHaveCount(2);
  await page.screenshot({ path: join(SHOTS, "170-transcript-attachments-live.png"), fullPage: true });

  // And the composer is empty again, with nothing left behind.
  await expect(page.getByLabel("Attached to this prompt")).toHaveCount(0);

  // BUG-26 again, on a real 2.2 MB photograph rather than a test pixel: the
  // picture opens in the inspector and the controls move it.
  await sent.getByRole("button", { name: /^Open IMG/ }).click();
  await expect(page.getByRole("complementary", { name: "File preview" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: /zoom in/i }).click();
  await page.getByRole("button", { name: /zoom in/i }).click();
  await expect(page.getByText("156%")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "171-photo-inspection-live.png"), fullPage: true });
});
