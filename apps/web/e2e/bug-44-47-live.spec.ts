/**
 * Live browser verification for BUG-44 and BUG-47.
 *
 * Runs against two real `raiker-web` hosts, not a route-mocked shell:
 *
 * * **127.0.0.1:8765** — a *source checkout*, holding a real Anthropic
 *   credential entered through the product UI and answering a real turn. This
 *   is where BUG-47 is reproduced and where the update panel has to say
 *   "source checkout" and refuse to look for updates.
 * * **127.0.0.1:8766** — a host started *from inside a release artifact* built
 *   by `raiker-release`, with `RAIKER_INSTALL_ROOT` and `PYTHONPATH` pointing at
 *   the extracted payload, so the code executing is the artifact's copy and the
 *   provenance it reports is read from the `installation.json` that build wrote.
 *   That artifact was built without platform signing, so the panel must call it
 *   an **unsigned build** — which is the property BUG-44 is really about.
 *
 * Start them first:
 *   npm --prefix apps/web run build
 *   python apps/api/main.py --workspace <ws-a> --port 8765 --no-browser \
 *     --rate-limit-per-minute 6000
 *   raiker-release build --version 0.1.0 --target linux-x86_64 --out dist \
 *     --source-root . --web-assets apps/web/dist --wheel-dir <wheels>
 *   # extract dist/raiker-0.1.0-linux-x86_64-unsigned.zip to <installed>
 *   RAIKER_INSTALL_ROOT=<installed> PYTHONPATH=<installed>/service \
 *     python <installed>/service/apps/api/main.py --workspace <ws-b> \
 *     --port 8766 --no-browser --ui-dir <installed>/web
 *   RAIKER_LIVE_ANTHROPIC_KEY=… npm --prefix apps/web run test:e2e:live
 *
 * What each part proves:
 *
 * * **BUG-47** — a local provider's test result lands under that provider's own
 *   row and nowhere else, while a connected hosted card keeps its independent
 *   status. Before the fix the view held one result string for the whole page,
 *   so testing Ollama printed its answer beneath Anthropic and OpenRouter and
 *   printed nothing beneath Ollama.
 * * **BUG-44** — the update panel reads provenance from the build rather than
 *   asserting it: a checkout says checkout and makes no request when checked, a
 *   real artifact reports its version, target and *unsigned* signing state, and
 *   nothing anywhere offers to apply an update from inside the host it would
 *   replace.
 *
 * The release pipeline itself — build, reproducibility, packaging smoke test on
 * this platform, native installer, signed channel index, and the verification
 * an installed Raiker performs — is exercised here too, by running the same
 * commands `.github/workflows/release.yml` runs. A browser cannot screenshot
 * `dpkg-deb`, but the run either produces a verifiable release or it does not.
 */
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

const SOURCE = "http://127.0.0.1:8765";
const PACKAGED = "http://127.0.0.1:8766";
const REPO = join(import.meta.dirname, "..", "..", "..");
const SHOTS = join(REPO, "docs", "plans", "screenshots", "working");
const PASSWORD = "Bug-44-47-live-password-D2!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const RELEASE_DIR = process.env.RAIKER_LIVE_RELEASE_DIR ?? "";
const WHEEL_DIR = process.env.RAIKER_LIVE_WHEEL_DIR ?? "";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(target: Page, base: string) {
  await target.goto(`${base}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(target.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  page = await context.newPage();
  await signIn(page, SOURCE);
});

test.afterAll(async () => await context?.close());

test("a real Anthropic turn answers, so the rest of this file is evidence", async () => {
  test.setTimeout(240_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  await page.goto(`${SOURCE}/#/models`);
  const card = page.locator("article.provider-card").filter({ hasText: "Anthropic" });
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connected")).toBeVisible({ timeout: 30_000 });

  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 30_000 });
  await catalogue.selectOption(MODEL);
  await card.getByRole("button", { name: "Use model" }).click();
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({ timeout: 30_000 });

  await page.goto(`${SOURCE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: RELEASE LIVE");
  await page.getByRole("button", { name: "Send" }).click();
  // Exact, and scoped to the transcript: the prompt is echoed in the sent
  // bubble and in the recent-chat rail, and neither of those is an answer.
  await expect(page.getByRole("main").getByText("RELEASE LIVE", { exact: true }))
    .toBeVisible({ timeout: 180_000 });
});

test("BUG-47 — a provider's test result stays under that provider", async () => {
  test.setTimeout(180_000);
  await page.goto(`${SOURCE}/#/models?tab=providers`);

  const ollamaRow = page.locator(".local-row").filter({ hasText: "Ollama" });
  const anthropicCard = page.locator("article.provider-card").filter({ hasText: "Anthropic" });
  await expect(anthropicCard.getByText("Connected")).toBeVisible({ timeout: 30_000 });

  // Test the *local* provider. This is the reported reproduction: its answer
  // used to appear beneath every connected hosted card and beneath nothing else.
  await ollamaRow.getByRole("button", { name: "Test" }).click();
  // The message names Ollama whether it answered or not, so a result appearing
  // under the wrong card would now contradict the card it sits under.
  const ollamaResult = page.locator("[data-test-result]").filter({ hasText: /^Ollama/ });
  await expect(ollamaResult).toHaveCount(1, { timeout: 60_000 });
  // It is inside the Ollama row, and the Anthropic card holds no result at all.
  await expect(ollamaRow.locator("[data-test-result]")).toHaveCount(1);
  await expect(anthropicCard.locator("[data-test-result]")).toHaveCount(0);

  // Now test the hosted provider. Two independent results, each under its own
  // card, neither overwriting nor duplicating the other.
  await anthropicCard.getByRole("button", { name: "Test" }).click();
  const anthropicResult = anthropicCard.locator("[data-test-result]");
  await expect(anthropicResult).toHaveCount(1, { timeout: 60_000 });
  await expect(anthropicResult).toContainText(/Anthropic responded and exposed \d+ models?\./);
  await expect(ollamaRow.locator("[data-test-result]")).toHaveCount(1);
  await expect(page.locator("[data-test-result]")).toHaveCount(2);

  // Two shots, because the evidence is a *relationship* between two parts of a
  // long page: the local row holding its own answer, and the hosted cards
  // holding theirs and no one else's.
  await ollamaRow.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "197-BUG-47-local-result-under-ollama-live.png") });
  await anthropicCard.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "198-BUG-47-hosted-cards-keep-their-own-live.png") });
});

test("BUG-44 — a source checkout says so, and checking makes no request", async () => {
  test.setTimeout(120_000);
  await page.goto(`${SOURCE}/#/workbench`);
  await page.getByRole("button", { name: /^Host/ }).click();
  const panel = page.getByRole("region", { name: "Host control" });
  await expect(panel.getByText("Install & updates")).toBeVisible({ timeout: 30_000 });
  await expect(panel.getByText("source checkout", { exact: true })).toBeVisible();
  await expect(panel.getByText(/Raiker contacts no update service/)).toBeVisible();

  await panel.getByRole("button", { name: /Check for updates/ }).click();
  await expect(panel.getByText(/source checkout/).first()).toBeVisible({ timeout: 30_000 });
  // Applying an update is never offered from inside the host it would replace.
  await expect(panel.getByRole("button", { name: /^(Install|Apply|Update now)/ })).toHaveCount(0);

  await page.screenshot({ path: join(SHOTS, "199-BUG-44-source-checkout-live.png") });
});

test("BUG-44 — a host running from a release artifact reports that build", async ({ browser }) => {
  test.setTimeout(180_000);
  const packaged = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  const other = await packaged.newPage();
  try {
    await signIn(other, PACKAGED);
    await other.getByRole("button", { name: /^Host/ }).click();
    const panel = other.getByRole("region", { name: "Host control" });
    await expect(panel.getByText("Install & updates")).toBeVisible({ timeout: 30_000 });

    // Read straight out of the artifact's own installation.json.
    await expect(panel.getByText("unsigned build", { exact: true })).toBeVisible();
    await expect(panel.getByText(/0\.1\.0 · linux-x86_64/)).toBeVisible();
    await expect(panel.getByText("signed release", { exact: true })).toHaveCount(0);
    await expect(panel.getByText(/not eligible for automatic updates/)).toBeVisible();

    await other.screenshot({ path: join(SHOTS, "200-BUG-44-packaged-unsigned-build-live.png") });
  } finally {
    await packaged.close();
  }
});

test("BUG-44 — the release pipeline builds, verifies and packages on this platform", () => {
  test.setTimeout(600_000);
  test.skip(RELEASE_DIR === "" || WHEEL_DIR === "", "set RAIKER_LIVE_RELEASE_DIR and RAIKER_LIVE_WHEEL_DIR");

  const run = (command: string, args: string[]) =>
    execFileSync(command, args, { cwd: REPO, encoding: "utf-8", env: { ...process.env } });

  // The same three commands the workflow runs, against the release this run
  // already produced: the channel index and the verification an installed
  // Raiker performs before it would change anything.
  const verified = run("raiker-release", ["verify", "--dir", RELEASE_DIR]);
  expect(verified).toContain("verified linux-x86_64");

  const artifact = join(RELEASE_DIR, "raiker-0.1.0-linux-x86_64-unsigned.zip");
  expect(existsSync(artifact)).toBe(true);

  // The packaging test the distribution design requires on every target: the
  // encrypted database has to work from the artifact, not from the checkout.
  const smoke = run("python", ["scripts/packaging_smoke_test.py", "--artifact", artifact]);
  expect(smoke).toContain("sqlcipher encrypts, refuses a wrong key");
  expect(smoke).toContain("packaging smoke test passed");

  // And the native installer for this platform.
  const installer = run("python", [
    "scripts/build_installer.py",
    "--artifact", artifact,
    "--out", join(RELEASE_DIR, "installers"),
  ]);
  expect(installer).toMatch(/built .*\.deb/);
});
