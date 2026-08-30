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
 * * **BUG-47** — a provider's test result lands under the card or row that ran
 *   it and nowhere else. Before the fix the view held one result string for the
 *   whole page, so testing Ollama printed its answer beneath Anthropic and
 *   OpenRouter and printed nothing beneath Ollama. Since FIXED-141 split Models
 *   by model origin, the pairs that can still contaminate one another are the
 *   ones sharing a tab, so the scenario now tests two hosted cards on Hosted
 *   and two runtime rows on Local (BUG-85).
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
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const SOURCE = "http://127.0.0.1:8765";
const PACKAGED = "http://127.0.0.1:8766";
const REPO = join(import.meta.dirname, "..", "..", "..");
const SHOTS = join(REPO, "docs", "plans", "screenshots", "working");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const RELEASE_DIR = process.env.RAIKER_LIVE_RELEASE_DIR ?? "";
const WHEEL_DIR = process.env.RAIKER_LIVE_WHEEL_DIR ?? "";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

/** BUG-229 — the one shared sign-in; this spec drives two instances. */
async function signIn(target: Page, base: string) {
  await signInAsOwner(target, base);
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

  const card = await useHostedModel(page, SOURCE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({ timeout: 30_000 });

  await page.goto(`${SOURCE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: RELEASE LIVE");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // Exact, and scoped to the transcript: the prompt is echoed in the sent
  // bubble and in the recent-chat rail, and neither of those is an answer.
  await expect(page.getByRole("main").getByText("RELEASE LIVE", { exact: true }))
    .toBeVisible({ timeout: 180_000 });
});

/**
 * BUG-85 re-aimed this scenario. It used to open `#/models?tab=local` and wait
 * for a *hosted* card's "Connected" badge on the same screen — impossible since
 * FIXED-141 split the page by model origin, so the scenario could not run at
 * all. The split also makes the original local-versus-hosted cross-contamination
 * structurally impossible, so the property worth testing is the one that can
 * still break: two cards **on the same tab** must keep their own results.
 */
test("BUG-47 — a provider's test result stays under that provider, on its own tab", async () => {
  test.setTimeout(180_000);

  // ── Hosted: several cards, one grid, one tab ────────────────────────────
  await page.goto(`${SOURCE}/#/models?tab=hosted`);
  const hostedCards = page.locator("article.provider-card");
  const anthropicCard = hostedCards.filter({ hasText: "Anthropic" });
  await expect(anthropicCard.getByText("Connection saved")).toBeVisible({ timeout: 30_000 });
  // The scenario is only meaningful with a neighbour to contaminate.
  expect(await hostedCards.count()).toBeGreaterThan(1);
  await expect(page.locator("[data-test-result]")).toHaveCount(0);

  await anthropicCard.getByRole("button", { name: "Test" }).click();
  await expect(anthropicCard.locator("[data-test-result]")).toHaveCount(1, { timeout: 60_000 });
  // One result on the whole tab: under the card that ran it, under no other.
  await expect(page.locator("[data-test-result]")).toHaveCount(1);

  // A second hosted card, so the two answers have to stay apart rather than
  // one page-wide string being reprinted under everything connected.
  const neighbour = hostedCards.filter({ hasNotText: "Anthropic" }).first();
  const neighbourName = (await neighbour.getByRole("heading").first().innerText()).trim();
  await neighbour.getByRole("button", { name: "Test" }).click();
  await expect(neighbour.locator("[data-test-result]")).toHaveCount(1, { timeout: 60_000 });
  await expect(page.locator("[data-test-result]")).toHaveCount(2);
  await expect(anthropicCard.locator("[data-test-result]")).toHaveCount(1);
  // Every message names its own provider, so a result under the wrong card
  // would contradict the card it sits under.
  await expect(neighbour.locator("[data-test-result]")).toContainText(neighbourName);
  await anthropicCard.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "198-BUG-47-hosted-cards-keep-their-own-live.png") });

  // ── Local: the same property among the Local rows ───────────────────────
  await page.goto(`${SOURCE}/#/models?tab=local`);
  const localRows = page.locator(".local-row");
  await expect(localRows.first()).toBeVisible({ timeout: 30_000 });
  expect(await localRows.count()).toBeGreaterThan(1);
  await expect(page.locator("[data-test-result]")).toHaveCount(0);

  const firstRow = localRows.nth(0);
  const secondRow = localRows.nth(1);
  const firstName = (await firstRow.getByRole("heading").first().innerText()).trim();
  const secondName = (await secondRow.getByRole("heading").first().innerText()).trim();

  await firstRow.getByRole("button", { name: "Test" }).click();
  await expect(firstRow.locator("[data-test-result]")).toHaveCount(1, { timeout: 60_000 });
  await expect(page.locator("[data-test-result]")).toHaveCount(1);
  await expect(secondRow.locator("[data-test-result]")).toHaveCount(0);

  await secondRow.getByRole("button", { name: "Test" }).click();
  await expect(secondRow.locator("[data-test-result]")).toHaveCount(1, { timeout: 60_000 });
  await expect(page.locator("[data-test-result]")).toHaveCount(2);
  await expect(firstRow.locator("[data-test-result]")).toContainText(firstName);
  await expect(secondRow.locator("[data-test-result]")).toContainText(secondName);

  await firstRow.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "197-BUG-47-local-rows-keep-their-own-live.png") });
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
