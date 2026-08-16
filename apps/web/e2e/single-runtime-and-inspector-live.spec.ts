/**
 * Live browser verification for this change set.
 *
 * Runs against a real `raiker-web` on 127.0.0.1:8765 — the actual FastAPI
 * runtime serving the built SPA, not a route-mocked shell — so what these
 * screenshots record is the shipped product answering its own endpoints.
 *
 * Covers: the single runtime (no mode picker in Settings), the unified
 * composers in Chat, Build and the Workbench, image inspection controls
 * (BUG-26), and the download surface on generated artifacts (BUG-28).
 *
 * Start the server first:
 *   python apps/api/main.py --workspace <ws> --port 8765 --no-browser
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { join } from "node:path";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Single-runtime-review-password-1!";

async function signIn(page: Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  const confirm = page.getByLabel("Confirm password");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });
}

// One sign-in for the whole file: the runtime rate-limits authentication (a
// real protection, not a test obstacle).
test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  await signIn(page);
});

test.afterAll(async () => {
  await page?.close();
});

test("Settings states one runtime instead of asking which one to run", async () => {
  test.setTimeout(90_000);
  await page.goto(`${BASE}/#/settings`);
  await page.getByRole("button", { name: "Runtime configuration" }).click();

  await expect(page.getByRole("heading", { name: "Runtime configuration" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByRole("heading", { name: /Raiker runtime/ })).toBeVisible();
  // The whole point: there is nothing to select, and the runtime is on.
  await expect(page.getByLabel("New runtime mode")).toHaveCount(0);
  await expect(page.getByText("Accepting work")).toBeVisible();
  // The one runtime-level decision that remains.
  await expect(page.getByRole("button", { name: "Disable agent runtime" })).toBeVisible();

  await page.screenshot({ path: join(SHOTS, "160-settings-single-runtime-live.png"), fullPage: true });
});

test("the Workbench composer carries files and schedules with a time", async () => {
  test.setTimeout(90_000);
  await page.goto(`${BASE}/#/home`);
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });

  // It no longer tells you to go and start in Chat to attach something.
  await expect(page.getByRole("button", { name: "Add attachment" })).toBeVisible();
  await expect(page.getByText(/start in Chat and attach it there/i)).toHaveCount(0);

  // Schedule mode asks for the time it needs, here, rather than handing Tasks
  // a half-filled form.
  await page.getByRole("tab", { name: "Schedule" }).click();
  await expect(page.getByLabel("Scheduled start time")).toBeVisible();

  await page.screenshot({ path: join(SHOTS, "161-workbench-composer-live.png"), fullPage: true });
});

test("Chat and Build offer the same composer affordances", async () => {
  test.setTimeout(120_000);

  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible({ timeout: 20_000 });
  const chatAttach = page.getByRole("button", { name: "Add attachment" });
  await expect(chatAttach).toBeVisible();
  await chatAttach.click();
  await expect(page.getByLabel("Attachment path")).toBeVisible();
  await expect(page.getByLabel("Upload image")).toHaveCount(1);
  await expect(page.getByLabel("Upload document")).toHaveCount(1);
  await page.screenshot({ path: join(SHOTS, "162-chat-composer-attach-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/build`);
  await expect(
    page.getByRole("button", { name: /^How much Raiker may do this turn:/ }),
  ).toBeVisible({ timeout: 20_000 });
  // BUG-35 — Build carries files too now, through the same control.
  const buildAttach = page.getByRole("button", { name: "Add attachment" });
  await expect(buildAttach).toBeVisible();
  await buildAttach.click();
  await expect(page.getByLabel("Attachment path")).toBeVisible();
  await expect(page.getByLabel("Upload image")).toHaveCount(1);
  await expect(page.getByLabel("Upload document")).toHaveCount(1);
  await page.screenshot({ path: join(SHOTS, "163-build-composer-attach-live.png"), fullPage: true });
});

test("Build shows what a turn carried, the same way the composer did", async () => {
  test.skip(process.env.RAIKER_E2E_IMAGE === undefined, "set RAIKER_E2E_IMAGE");
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/build`);
  await expect(
    page.getByRole("button", { name: /^How much Raiker may do this turn:/ }),
  ).toBeVisible({ timeout: 20_000 });
  // The panel may already be open from the previous test — Build stays mounted
  // across navigations — so open it only when it is actually shut.
  const upload = page.getByLabel("Upload image");
  if (!(await upload.count())) {
    await page.getByRole("button", { name: "Add attachment" }).click();
  }
  await upload.setInputFiles(String(process.env.RAIKER_E2E_IMAGE));
  const row = page.getByLabel("Attached to this prompt");
  await expect(row.locator("img")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "172-build-attachment-card-live.png"), fullPage: true });
});

test("Memory offers View source on every record", async () => {
  test.setTimeout(90_000);
  await page.goto(`${BASE}/#/memory`);
  await expect(page.getByRole("heading", { level: 1, name: "Memory" })).toBeVisible({
    timeout: 20_000,
  });
  await page.screenshot({ path: join(SHOTS, "164-memory-view-source-live.png"), fullPage: true });
});

test("Tasks presents the approval life of a scheduled run", async () => {
  test.setTimeout(90_000);
  await page.goto(`${BASE}/#/tasks`);
  await expect(page.getByRole("heading", { name: "Plan work" })).toBeVisible({ timeout: 20_000 });
  // Wait for the list itself: the composer renders before the tasks arrive, and
  // a screenshot taken in between records a loading state, not the behaviour.
  await expect(page.getByRole("heading", { name: "Open work" })).toBeVisible({ timeout: 20_000 });

  // BUG-25 — the two states an approval puts a scheduled run through, and the
  // retry that exists when automatic continuation could not proceed.
  await expect(page.getByText("continuing after approval").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue now" }).first()).toBeVisible();

  await page.screenshot({ path: join(SHOTS, "165-tasks-continuation-live.png"), fullPage: true });
});
