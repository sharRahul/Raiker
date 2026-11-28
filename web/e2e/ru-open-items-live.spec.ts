/** RU-12/RU-13 regression qualification against a real host, without API mocks.
 * Provider credentials are supplied by the run and entered through Models.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, refreshHostedReadiness, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY, ANTHROPIC_MODEL, LIVE_BASE, sendTurn } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "ru-open-items");

async function activateProfile(page: Page, name: "Balanced" | "Private local") {
  await page.goto(`${LIVE_BASE}/#/settings?tab=execution-profiles`);
  const profiles = page.getByRole("list", { name: "Profiles", exact: true });
  await expect(profiles).toBeVisible();
  const profile = profiles.getByRole("listitem").filter({ has: page.locator("strong", { hasText: new RegExp(`^${name}$`) }) }).first();
  if (await profile.count() === 0) {
    await page.getByRole("button", { name: `Create ${name}`, exact: true }).click();
    await expect(profile).toBeVisible();
  }
  const activate = profile.getByRole("button", { name: "Make active", exact: true });
  if (await activate.isVisible()) await activate.click();
  await expect(profile.getByText("Active", { exact: true })).toBeVisible();
}

test("RT-RU-OPEN-01 — real answer, preflight refusal without a phantom session, and honest memory/host controls", async ({ page }) => {
  test.setTimeout(420_000);
  expect(ANTHROPIC_KEY, "Supply RAIKER_LIVE_ANTHROPIC_KEY for UI connection").not.toBe("");
  await page.emulateMedia({ reducedMotion: "reduce" });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await signInAsOwner(page, LIVE_BASE);
  await activateProfile(page, "Balanced");
  const card = await hostedProviderCard(page, LIVE_BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible()) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
    const workspace = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID;
    if (workspace) {
      await page.getByRole("button", { name: "Advanced", exact: true }).click();
      await page.getByPlaceholder("wrkspc_…").fill(workspace);
    }
    await page.locator(".signin-connect").click();
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await keepModelAvailable(page, card, ANTHROPIC_MODEL);
  await refreshHostedReadiness(page, LIVE_BASE, "Anthropic");
  await page.goto(`${LIVE_BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku|claude/i);
  await sendTurn(page, "Reply with exactly: live connection verified. Do not use tools.");
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(/live connection verified/i, { timeout: 120_000 });
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 120_000 });
  await capture(page, join(SHOTS, "real-answer.png"));

  await activateProfile(page, "Private local");
  await page.goto(`${LIVE_BASE}/#/new-chat`);
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await chooseModelForTurn(page, /Haiku|claude/i);
  const reads: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/sessions/")) reads.push(new URL(request.url()).pathname);
  });
  await sendTurn(page, "Say ready without tools.");
  await expect(page.getByText(/does not allow Anthropic/).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("turn-control")).toBeHidden();
  expect(reads).toEqual([]);
  await expect(page).not.toHaveURL(/session=/);
  await expect(page.getByText("Goes to Anthropic", { exact: true })).toBeVisible();
  await capture(page, join(SHOTS, "preflight-no-session.png"));

  for (const theme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(`${LIVE_BASE}/#/memory?tab=memories`);
      await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
      const navigation = page.getByRole("banner").getByRole("button", { name: /navigation/ });
      await expect(navigation).toHaveAttribute("aria-label", width === 390 ? /^(Open|Close) navigation$/ : /^(Collapse|Expand) navigation$/);
      const closeNavigation = page.getByRole("button", { name: "Close navigation", exact: true });
      if (await closeNavigation.isVisible()) await closeNavigation.click();
      await expect(page.locator(".drawer-scrim")).toBeHidden();
      await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState !== "running"));
      await expect(page.getByText(/Memory tools are off/)).toBeVisible();
      await expect(page.getByText(/lessons from project work follow Ask before remembering/)).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
      await capture(page, join(SHOTS, `memory-${theme}-${width}.png`));
      await page.getByRole("button", { name: /^(Host status|Host:|Host$)/ }).click();
      const panel = page.getByRole("region", { name: "Host control" });
      await expect(panel.getByRole("button", { name: "Restart", exact: true })).toBeDisabled();
      await expect(panel).toContainText("No — run");
      await capture(page, join(SHOTS, `host-${theme}-${width}.png`));
      await page.keyboard.press("Escape");
    }
  }
  expect(errors).toEqual([]);
});
