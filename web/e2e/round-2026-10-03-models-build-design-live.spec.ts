/**
 * The third 2026-10-03 round: the release-readiness review's remaining Models,
 * Build and Design rows — UX-MODEL-02, -04, -05, UX-BUILD-02, -03, -04 and
 * UX-DESIGN-01 to -04 — driven against a running host.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, with
 * Anthropic connected through Models from `RAIKER_LIVE_ANTHROPIC_KEY` — the key
 * typed into the Connect dialog, never written here. The host's egress reaches
 * Anthropic and no image provider, so Design's pictures are seeded into the
 * workspace's own store by `scripts/seed_design_assets.py` and read back
 * through the product.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, dismissFirstRunModelSetup, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-03-models-build-design-round");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "/tmp/claude-0/raiker-live";
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? join(import.meta.dirname, "..", "..", ".venv", "bin", "python");
const REPO = join(import.meta.dirname, "..", "..");

test.describe.configure({ mode: "serial" });

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

async function api<T>(page: Page, method: string, path: string, body?: unknown): Promise<T> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|; )raiker_csrf=([^;]+)/)?.[1];
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return (await response.json()) as T;
    },
    { method, path, body },
  );
}

async function openModels(page: Page, tab: string) {
  await page.goto(`${BASE}/#/models?tab=${tab}`);
  await settled(page);
}

test("a fresh workspace says which step each work mode stops at, and the one action that moves it", async ({ page }) => {
  test.setTimeout(240_000);
  const { failures } = watchFailures(page);
  await signInAsOwner(page, BASE);
  await dismissFirstRunModelSetup(page).catch(() => false);
  await openModels(page, "overview");

  const chat = page.getByRole("list", { name: "Chat readiness" });
  await expect(chat).toBeVisible({ timeout: 30_000 });
  const states = await chat.getByRole("listitem").evaluateAll((items) =>
    items.map((item) => `${item.getAttribute("data-step")}:${item.getAttribute("data-state")}`),
  );
  // Nothing connected: the first step is the one that stops it.
  expect(states).toEqual(["connect:blocked", "discover:waiting", "choose:waiting", "run:waiting"]);
  await expect(page.getByRole("button", { name: "Connect a provider" }).first()).toBeVisible();
  await capture(page, join(SHOTS, "01-readiness-nothing-connected.png"));

  await page.getByRole("button", { name: "Connect a provider" }).first().click();
  await expect(page).toHaveURL(/tab=add/);
  expect(failures).toEqual([]);
});

test("Anthropic connects through Models and the readiness line steps aside", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await useAnthropic(page, BASE);
  await openModels(page, "overview");
  // Connected and catalogued, and nothing chosen yet: the line moves on to the
  // third step and its action is the choice itself.
  const chat = page.getByRole("list", { name: "Chat readiness" });
  await expect(chat).toBeVisible({ timeout: 30_000 });
  const states = await chat.getByRole("listitem").evaluateAll((items) =>
    items.map((item) => `${item.getAttribute("data-step")}:${item.getAttribute("data-state")}`),
  );
  expect(states).toEqual(["connect:done", "discover:done", "choose:blocked", "run:waiting"]);
  await capture(page, join(SHOTS, "02-readiness-connected-choose-next.png"));

  const choose = page.locator(".work-rows li").filter({ hasText: "Chat" }).first().getByRole("button", { name: "Choose a model" });
  await choose.click();
  await expect(page).toHaveURL(/tab=models/);
  const haiku = page.locator("li, article").filter({ hasText: /Haiku 4\.5/ }).filter({ has: page.getByRole("button", { name: "Use", exact: true }) }).first();
  await haiku.getByRole("button", { name: "Use", exact: true }).click();
  await settled(page);
  await openModels(page, "overview");
  const chatRow = page.locator(".work-rows li").filter({ hasText: "Chat" }).first();
  // Chosen, and never run: the last step is "not checked yet", not broken, and
  // its action runs the exact-pair check here rather than sending the owner off.
  const chosen = await page.getByRole("list", { name: "Chat readiness" }).getByRole("listitem").evaluateAll((items) =>
    items.map((item) => `${item.getAttribute("data-step")}:${item.getAttribute("data-state")}`),
  );
  expect(chosen).toEqual(["connect:done", "discover:done", "choose:done", "run:unchecked"]);
  await capture(page, join(SHOTS, "03-readiness-chosen-not-checked.png"));
  await chatRow.getByRole("button", { name: "Check it now" }).click();
  await expect(chatRow.getByText("Ready", { exact: true })).toBeVisible({ timeout: 120_000 });
  // UX-MODEL-02 — a ready row says Ready and nothing more.
  await expect(chatRow.getByTestId("model-readiness-steps")).toHaveCount(0);
  await capture(page, join(SHOTS, "03b-readiness-ready.png"));
});

test("My models compares like for like, and an unknown fact says Unknown", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openModels(page, "models");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const table = page.getByRole("table");
  await expect(table).toBeVisible({ timeout: 30_000 });
  await expect(table.getByRole("columnheader")).toHaveText([
    "Model", "Runs", "Context", "Tools", "Vision", "Estimated cost", "Availability",
  ]);
  const haiku = table.getByRole("row").filter({ hasText: /Haiku 4\.5/ }).first();
  await expect(haiku).toContainText("Hosted service");
  await expect(haiku).toContainText("Prompts leave this device");
  await expect(haiku).toContainText("$1.00 in · $5.00 out per 1M tokens");
  await expect(haiku).toContainText("Ready");
  await capture(page, join(SHOTS, "04-models-compare.png"));

  // At phone width the table scrolls inside its own region, never the page.
  await page.setViewportSize({ width: 390, height: 844 });
  await settled(page);
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "05-models-compare-390.png"));
});

// ── Build ──────────────────────────────────────────────────────────────────

const PROJECT_NAME = `Closed loop ${Date.now().toString(36)}`;
let projectRoot = "";
const CODE_DIR = `pricing-${Date.now().toString(36)}`;
const CODE_DIR_MISSING = () => !existsSync(join(WORKSPACE, CODE_DIR, "test_pricing.py"));
let projectId = "";

async function setCapability(page: Page, label: string, reason: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByLabel("Search capabilities", { exact: true });
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible();
  const toggle = card.getByRole("button", { name: label });
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  const turnOn = card.getByRole("button", { name: "Turn on" });
  if (!(await turnOn.isVisible().catch(() => false))) return;
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const acknowledgement = dialog.getByRole("checkbox");
  if (await acknowledgement.isVisible().catch(() => false)) await acknowledgement.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

/**
 * The project this round works in. Created by the closed-loop scenario; a
 * later scenario run on its own creates it, so none depends on running after
 * another.
 */
async function ensureProject(page: Page) {
  if (projectId !== "") return;
  const created = await api<{ project_id?: string; project?: { project_id: string } }>(
    page, "POST", "/api/projects", { name: PROJECT_NAME },
  );
  projectId = created.project?.project_id ?? created.project_id ?? "";
  await page.reload();
  await settled(page);
}

/** COMPOSER-03 — the project is chosen behind `+`, the way an owner does it. */
async function chooseBuildProject(page: Page) {
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  const picker = page.getByLabel("Project for this build");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ label: PROJECT_NAME });
  await expect(page.getByText(`Working in ${PROJECT_NAME}`)).toBeVisible({ timeout: 30_000 });
  // BUG-292 — a Build turn names its own model.
  await chooseModelForTurn(page, /Haiku 4\.5/, "Build composer");
}

test("Build closes the loop: run the tests, read the failure, fix, re-run, green, summarise", async ({ page }) => {
  test.setTimeout(900_000);
  const { failures } = watchFailures(page);
  await signInAsOwner(page, BASE);
  await setCapability(page, "File writes", "UX-BUILD-04 closed-loop acceptance");
  await setCapability(page, "Shell commands", "UX-BUILD-04 closed-loop acceptance");
  await setCapability(page, "Approval execution relay", "UX-BUILD-04 closed-loop acceptance");

  await page.goto(`${BASE}/#/projects`);
  await settled(page);
  const created = await api<{ project_id?: string; root_subpath?: string; project?: { project_id: string; root_subpath: string } }>(
    page, "POST", "/api/projects", { name: PROJECT_NAME },
  );
  const project = created.project ?? (created as { project_id: string; root_subpath: string });
  projectId = project.project_id;
  // A managed project's own folder is Raiker's (under `.raiker/`, protected);
  // Build reads, writes and runs commands relative to the workspace. So the
  // repository under test is a folder in the workspace, named in the prompt.
  projectRoot = join(WORKSPACE, CODE_DIR);
  mkdirSync(projectRoot, { recursive: true });
  // A real, small repository with a real bug: the test fails until it is fixed.
  writeFileSync(
    join(projectRoot, "pricing.py"),
    "def total(prices, discount):\n" +
      '    """Sum the prices, then take `discount` percent off the sum."""\n' +
      "    return sum(prices) - discount\n",
  );
  writeFileSync(
    join(projectRoot, "test_pricing.py"),
    "from pricing import total\n\n" +
      "assert total([10, 20, 30], 10) == 54, total([10, 20, 30], 10)\n" +
      "assert total([100], 0) == 100\n" +
      'print("all tests passed")\n',
  );

  // Created through the API, so the page's project list is read again.
  await page.reload();
  await settled(page);
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await settled(page);
  await chooseBuildProject(page);

  // UX-BUILD-02 — the boundary in order, model last.
  await page.getByRole("button", { name: /^Context for this turn/ }).click();
  const inspector = page.getByRole("dialog", { name: "Context for this turn" });
  await expect(inspector).toBeVisible();
  await expect(inspector.getByRole("term").filter({ hasText: "Runs on" })).toBeVisible({ timeout: 30_000 });
  const terms = await inspector.getByRole("term").allTextContents();
  const order = ["Project", "Runs on", "Model"].map((label) => terms.indexOf(label));
  expect(order.every((index) => index >= 0), terms.join(", ")).toBe(true);
  expect(order).toEqual([...order].sort((left, right) => left - right));
  await capture(page, join(SHOTS, "06-build-boundary.png"));
  await page.keyboard.press("Escape");

  const prompt = page.getByLabel("Describe the change");
  await prompt.fill(
    `The folder ${CODE_DIR} holds a small Python module and its test. Run ` +
      `\`python ${CODE_DIR}/test_pricing.py\` with the shell tool. It fails. Read the failure, ` +
      `fix the bug in ${CODE_DIR}/pricing.py (not the test), then run the same command again and ` +
      "keep going until it prints 'all tests passed'. Finish with a short summary of what was " +
      "wrong, what you changed and the final test result.",
  );
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeEnabled({ timeout: 60_000 });
  await run.click();
  await expect(page.getByTestId("turn-control")).toBeVisible({ timeout: 60_000 });

  // Every command and write is a real approval: the loop is interrupted and
  // resumed by the owner, which is the "approval interruption" UX-BUILD-04 names.
  let approvals = 0;
  const deadline = Date.now() + 780_000;
  while (Date.now() < deadline) {
    const accept = page.getByRole("button", { name: "Accept", exact: true }).first();
    const done = page.getByTestId("turn-control");
    if (await accept.isVisible().catch(() => false)) {
      if (approvals === 0) await capture(page, join(SHOTS, "07-build-approval-interrupts.png"));
      await accept.click();
      approvals += 1;
      await page.waitForTimeout(1_500);
      continue;
    }
    const finished =
      !(await done.isVisible().catch(() => false)) &&
      !(await page.getByText("Waiting for approval", { exact: true }).isVisible().catch(() => false));
    if (finished && approvals > 0) {
      const passed = (() => {
        try {
          return execFileSync(PYTHON, ["test_pricing.py"], { cwd: projectRoot, encoding: "utf-8" });
        } catch {
          return "";
        }
      })();
      if (passed.includes("all tests passed")) break;
    }
    await page.waitForTimeout(3_000);
  }
  const output = execFileSync(PYTHON, ["test_pricing.py"], { cwd: projectRoot, encoding: "utf-8" });
  expect(output).toContain("all tests passed");
  expect(readFileSync(join(projectRoot, "test_pricing.py"), "utf-8")).toContain("== 54");
  expect(approvals).toBeGreaterThan(1);
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await capture(page, join(SHOTS, "08-build-green-summary.png"));
  expect(failures).toEqual([]);
});

test("a narrow window steps the workbench aside for an approval", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);
  await ensureProject(page);
  if (CODE_DIR_MISSING()) {
    mkdirSync(join(WORKSPACE, CODE_DIR), { recursive: true });
    writeFileSync(join(WORKSPACE, CODE_DIR, "test_pricing.py"), 'print("all tests passed")\n');
  }
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await settled(page);
  await chooseBuildProject(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await settled(page);
  await page.getByLabel("Describe the change").fill(
    `Use the shell tool exactly once to run \`python ${CODE_DIR}/test_pricing.py\`, then tell me what it printed.`,
  );
  const send = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(send).toBeEnabled({ timeout: 60_000 });
  // The owner presses Run and, while the turn works, opens the workbench to
  // read something — the drawer is modal, so the composer behind it is inert.
  await send.click();
  await page.getByRole("button", { name: /background work/i }).first().click();
  await expect(page.getByRole("dialog", { name: "Background work" })).toBeVisible();
  // UX-BUILD-03 — the drawer was over the transcript; the approval takes priority.
  await expect(page.getByRole("button", { name: "Accept", exact: true }).first()).toBeVisible({ timeout: 300_000 });
  await expect(page.getByRole("dialog", { name: "Background work" })).toBeHidden();
  await capture(page, join(SHOTS, "09-build-approval-over-drawer-390.png"));
  await page.getByRole("button", { name: "Accept", exact: true }).first().click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
});

test("Usage keeps the profile id in Details, not under the provider's name", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await openModels(page, "usage");
  const card = page.locator(".usage-row").filter({ hasText: "Anthropic" }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.locator("header")).not.toContainText("anthropic-hosted");
  const details = card.locator("details.ids");
  await expect(details).not.toHaveAttribute("open", "");
  await details.locator("summary").click();
  await expect(details).toContainText("anthropic-hosted");
  await capture(page, join(SHOTS, "10-usage-id-in-details.png"), card);
});

// ── Design ─────────────────────────────────────────────────────────────────

test("Design: filed or Unfiled before Generate, then export, delete, restore and remove", async ({ page }) => {
  test.setTimeout(240_000);
  const { failures, consoleErrors } = watchFailures(page);
  await signInAsOwner(page, BASE);
  await ensureProject(page);
  const seeded = JSON.parse(
    execFileSync(PYTHON, [join(REPO, "scripts", "seed_design_assets.py"), WORKSPACE, "--project", projectId], {
      cwd: REPO,
      encoding: "utf-8",
    }),
  ) as string[];
  expect(seeded).toHaveLength(3);

  await page.goto(`${BASE}/#/design`);
  await settled(page);
  // UX-DESIGN-02 — with no project chosen the destination is still stated.
  const line = page.getByRole("button", { name: /^Context for this turn/ });
  if (!(await line.textContent())?.includes("Unfiled")) {
    // A project left current by the Build scenario: clear it the owner's way.
    await page.getByRole("button", { name: /^Add/ }).first().click();
    await page.getByRole("menuitem", { name: /project/i }).first().click();
    await page.getByLabel("Project for this work").selectOption({ value: "" });
  }
  await expect(line).toContainText("Unfiled");
  await capture(page, join(SHOTS, "11-design-unfiled-destination.png"));

  await page.getByRole("button", { name: "Open The same lighthouse with a red lantern room on the canvas" }).first().click();
  const inspector = page.getByRole("complementary", { name: "Inspector" });
  await expect(inspector).toContainText(PROJECT_NAME);
  const download = inspector.getByRole("link", { name: "Download" });
  const href = await download.getAttribute("href");
  const disposition = await page.evaluate(async (url) => {
    const response = await fetch(url!, { credentials: "same-origin" });
    return response.headers.get("content-disposition");
  }, href);
  expect(disposition).toMatch(/^attachment; filename="raiker-the-same-lighthouse-with-a-red-[a-z0-9]{6}\.png"$/);
  await capture(page, join(SHOTS, "12-design-inspector-filed-and-download.png"));

  await inspector.getByRole("button", { name: "Delete" }).click();
  const recently = page.getByTestId("design-recently-deleted");
  await expect(recently).toContainText("Recently deleted 1");
  await recently.locator("summary").click();
  await captureElement(recently, join(SHOTS, "13-design-recently-deleted.png"));
  await recently.getByRole("button", { name: "Restore" }).click();
  await expect(page.getByTestId("design-recently-deleted")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Open The same lighthouse with a red lantern room on the canvas" }).first(),
  ).toBeVisible();

  // Removed for good: only from Recently deleted, after confirming.
  await page.getByRole("button", { name: "Open A loose sketch of a harbour on the canvas" }).first().click();
  await expect(inspector).toContainText(/Filed in\s*Unfiled/);
  await inspector.getByRole("button", { name: "Delete" }).click();
  await page.getByTestId("design-recently-deleted").locator("summary").click();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Remove for good" }).click();
  await expect(page.getByTestId("design-recently-deleted")).toHaveCount(0);
  const gallery = await api<{ generations: { generation_id: string }[]; deleted: unknown[] }>(page, "GET", "/api/images");
  expect(gallery.generations.map((row) => row.generation_id)).not.toContain(seeded[2]);
  expect(gallery.deleted).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await settled(page);
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "14-design-390.png"));
  expect(failures).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
