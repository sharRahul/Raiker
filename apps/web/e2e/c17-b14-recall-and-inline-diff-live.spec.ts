/**
 * C17 and B14, live: a memory the owner approved is named in the answer it
 * shaped and correctable there, and a proposed file change is read as a diff in
 * Build rather than in another route.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture, captureElement } from "./capture";
import { dismissFirstRunModelSetup, OWNER_CREDENTIALS, refreshHostedReadiness } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = OWNER_CREDENTIALS.password;

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn() {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  await dismissFirstRunModelSetup(page);
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
  await page.goto(`${BASE}/#/memory`);
  await expect(page.getByText("Loading memories…")).toBeHidden({ timeout: 60_000 });
  await page.locator("details.advanced summary").first().click();
  await page.setInputFiles(
    "details.advanced input[type=file]",
    {
      name: "memories.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify([
          { text: "My nightly backups go to the encrypted NAS in the garage.", scope: "account" },
        ]),
      ),
    },
  );
  await page.getByRole("button", { name: "Import reviewed records" }).click();
  await expect(
    page.getByText("My nightly backups go to the encrypted NAS in the garage.").first(),
  ).toBeVisible({ timeout: 60_000 });
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
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  const picker = page.getByLabel("Project for this build");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ index: 1 });

  await send(
    "Write a file called diff-demo.txt in this project containing exactly the line " +
      "'hello from raiker'. Use your tools; do not print it to me.",
    480_000,
  );

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
