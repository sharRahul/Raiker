/**
 * The 2026-10-01 round: BUG-310, OPT-01, -02, -13 and -16, and three defects the
 * round found by using the product.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py` and a
 * local Ollama service serving `gpt-oss:20b-cloud` — no key. Set
 * `RAIKER_LIVE_WORKSPACE` to that workspace so the probe check can read it.
 *
 * The first test creates the owner through setup, because what it proves is
 * setup's own Ready step; the rest use the shared `ownerPage` (OPT-16).
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { capture } from "./capture";
import { DESTINATIONS, settled } from "./destinations";
import { OWNER_CREDENTIALS } from "./hosted-provider";
import { expect, LIVE_BASE, runChatTurn, test } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-01-optimisation-round");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = /GPT oss:20B Cloud/;

test.describe.configure({ mode: "serial" });

test("setup chooses Ollama, and Ready's Chat opens Chat", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/workbench`);
  const confirm = page.getByLabel("Confirm password");
  await expect(page.getByLabel("Username")).toBeEnabled({ timeout: 60_000 });
  test.skip(!(await confirm.isVisible()), "needs a workspace reset for the round");
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  await confirm.fill(OWNER_CREDENTIALS.password);
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();

  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Ollama is installed here")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Other options" }).click();
  const ollama = page.getByRole("group", { name: "Ollama", exact: true });
  await ollama.getByRole("button", { name: "Change model" }).click();
  const picker = page.getByRole("dialog", { name: "Ollama models" });
  await picker.getByRole("searchbox", { name: "Search models" }).fill("oss:20b");
  await expect(picker.getByRole("checkbox")).toHaveCount(1);
  await expect(picker.getByRole("checkbox", { name: MODEL })).toBeVisible();
  await picker.getByRole("button", { name: "Use" }).click();
  await picker.getByRole("button", { name: "Done" }).click();
  await expect(ollama.getByText("Selected: GPT oss:20B Cloud")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: /Local, and the providers I connect/ }).click();
  await expect(page.getByRole("heading", { name: "Your Raiker is ready" })).toBeVisible();
  // The Design tile reads `image_models` from the generated profile type; an
  // Ollama chat model returns no images, so it says what Design still needs.
  await expect(page.getByText("Needs a provider that returns images.")).toBeVisible();
  await capture(page, join(SHOTS, "01-setup-ready.png"));

  await page.getByRole("button", { name: /^Chat/ }).first().click();
  await expect(page).toHaveURL(/#\/new-chat/);
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible();
  // The composer is on the model setup chose and checked, not the earlier default.
  await expect(page.getByRole("button", { name: /^Model for this turn: GPT oss:20B Cloud/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("No readiness check exists for this exact model.")).toHaveCount(0);
  await capture(page, join(SHOTS, "02-ready-chat-opens-chat.png"));
});

test("a real turn names its tool from the registry, and the probe leaves nothing", async ({
  ownerPage: page,
}) => {
  test.setTimeout(300_000);
  await page.goto(`${BASE}/#/new-chat`);
  const answer = await runChatTurn(
    page,
    "Use the list_directory tool on the workspace root, then tell me in one sentence what you found.",
  );
  // OPT-13 — the row's words come from the tool's definition now.
  await expect(page.getByText("List folder").first()).toBeVisible();
  await expect(answer).not.toBeEmpty();
  await capture(page, join(SHOTS, "03-chat-turn-list-folder.png"));

  test.skip(WORKSPACE === "", "RAIKER_LIVE_WORKSPACE not set");
  // The sandbox probe ran before this turn could; what it wrote is gone.
  expect(existsSync(join(WORKSPACE, ".raiker-probe-inside.tmp"))).toBe(false);
  expect(readdirSync(WORKSPACE).filter((name) => name.startsWith(".raiker-probe"))).toEqual([]);
  await expect(answer).not.toContainText(".raiker-probe");
});

test("every destination reads through the generated types and split client", async ({
  ownerPage: page,
}) => {
  test.setTimeout(300_000);
  const consoleErrors: string[] = [];
  const failures: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400) {
      failures.push(`${response.status()} ${response.url()}`);
    }
  });
  for (const destination of DESTINATIONS) {
    await page.goto(`${BASE}/#/${destination.route}`);
    await expect(page.locator("main#main")).toBeVisible();
    await settled(page);
  }
  await page.goto(`${BASE}/#/models`);
  await settled(page);
  await capture(page, join(SHOTS, "04-models.png"));
  await page.goto(`${BASE}/#/approvals`);
  await settled(page);
  await capture(page, join(SHOTS, "05-approvals.png"));
  // Hugging Face is the one host this machine cannot always reach; the hub
  // says so in its own panel (`hubReachability`), which is not a failure here.
  const relevant = failures.filter((line) => !line.includes("huggingface"));
  expect(relevant).toEqual([]);
  expect(consoleErrors.filter((line) => !/huggingface|503/i.test(line))).toEqual([]);
});

test("a second instance is created on this Windows host and opens", async ({ browser }) => {
  test.setTimeout(180_000);
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByLabel("Username")).toBeEnabled({ timeout: 60_000 });
  await page.getByRole("button", { name: /Use or create another instance/ }).click();
  const name = `round-${Date.now().toString(36)}`;
  await page.locator("#instance-name").fill(name);
  await page.locator("#username").fill("second");
  await page.locator("#password").fill(OWNER_CREDENTIALS.password);
  await page.locator("#confirm-password").fill(OWNER_CREDENTIALS.password);
  const opened = context.waitForEvent("page");
  await page.getByRole("button", { name: "Create account and open Raiker" }).click();
  const instance = await opened;
  await expect(instance).toHaveURL(new RegExp(`/instances/${name}/`));
  await expect(instance.locator("body")).toBeVisible();
  await capture(instance, join(SHOTS, "06-second-instance-opens.png"));
  if (WORKSPACE !== "") {
    expect(existsSync(join(WORKSPACE, ".raiker", "instances", name))).toBe(true);
  }
  await context.close();
});
