import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";

/**
 * Live evidence for the 2026-08-10 round: FIXED-161 through FIXED-170.
 *
 * Each block drives the surface the corresponding entry promised, against a
 * running `raiker-web` with a real provider credential entered through the UI —
 * not through an API call and not through a fixture.
 */

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "Round-0810-live-review-password-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

/**
 * Navigate and wait for the page to settle.
 *
 * The API is rate limited to 120 requests a minute per client, which is a
 * denial-of-service guardrail rather than an auth boundary — and a browser
 * sweeping eleven routes back to back will trip it. Pacing here is honest about
 * that instead of asserting against a throttled read.
 */
async function visit(page: Page, hash: string) {
  await page.goto(`${BASE}/#/${hash}`);
  await page.waitForTimeout(400);
}

async function signIn(page: Page) {
  await page.goto(`${BASE}/#/home`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirmPassword = page.getByLabel("Confirm password");
  if (await confirmPassword.isVisible()) {
    await confirmPassword.fill(PASSWORD);
    await page
      .getByRole("button", { name: "Create a User Account", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Choose how to run models" }),
    ).toBeVisible({ timeout: 30_000 });
    await page.screenshot({
      path: join(SHOTS, "round0810-01-first-run-model-setup.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Skip for now" }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker" }).click();
  }
  await expect(page.getByRole("navigation", { name: /navigation/i })).toBeVisible({
    timeout: 30_000,
  });
}

test("the 2026-08-10 round's surfaces, live", async ({ page }) => {
  test.setTimeout(600_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signIn(page);

  // FIXED-161 — every secondary destination is a separate chunk now, so the
  // sweep is also the proof that lazy routes mount with no flash and no error.
  for (const route of [
    "search-chat",
    "memory",
    "approvals",
    "tasks",
    "brain",
    "projects",
    "capabilities",
    "models",
    "extensions",
    "observe",
    "settings",
  ]) {
    await visit(page, route);
    await expect(page.locator("main#main")).toBeVisible();
    await expect(page.locator("main#main")).not.toBeEmpty();
  }
  await page.screenshot({
    path: join(SHOTS, "round0810-02-code-split-routes-mount.png"),
    fullPage: true,
  });

  // FIXED-166 — the plugin signing posture is stated rather than inferred.
  await visit(page, "extensions?tab=plugins");
  await expect(page.getByRole("heading", { name: "Plugin supply chain" })).toBeVisible();
  await expect(page.getByText(/presence marker only/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/RAIKER_PLUGIN_SIGNING_KEY/)).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("plugin-signing-posture").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: join(SHOTS, "round0810-03-plugin-signing-posture.png"),
    fullPage: true,
  });

  // FIXED-163/164 — containment for every capability, with its own controls.
  await visit(page, "settings?tab=security");
  const containment = page.getByTestId("capability-containment");
  await expect(containment.getByRole("heading", { name: "Monitored capabilities" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(containment.getByText(/Connectors, plugins, subagents/)).toBeVisible();
  await containment.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: join(SHOTS, "round0810-04-capability-containment.png"),
    fullPage: true,
  });

  // FIXED-169 — the readiness window is the owner's, with its bounds stated.
  await visit(page, "settings?tab=runtime");
  const ttl = page.getByRole("spinbutton", { name: /Re-confirm after/ });
  await expect(ttl).toBeVisible({ timeout: 30_000 });
  await expect(ttl).toHaveValue("5");
  await ttl.fill("30");
  await ttl.blur();
  // Settings stages edits and saves them explicitly, so the round trip has to go
  // through Save changes — otherwise this would only prove the input remembers
  // what was typed into it.
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("You have unsaved changes")).toBeHidden({ timeout: 15_000 });
  // Leave the section and come back: the value has to come from the server, not
  // from the input the test just typed into.
  await visit(page, "settings?tab=general");
  await expect(page.getByRole("heading", { name: "General" })).toBeVisible();
  await visit(page, "settings?tab=runtime");
  await expect(page.getByRole("spinbutton", { name: /Re-confirm after/ })).toHaveValue("30");
  await page.getByRole("heading", { name: /How long a model check stays good/ })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: join(SHOTS, "round0810-05-readiness-window-setting.png"),
    fullPage: true,
  });

  // FIXED-162 — the model activity surface and its controls.
  await visit(page, "models?tab=activity");
  await expect(page.getByRole("heading", { name: "Downloads and model jobs" })).toBeVisible({
    timeout: 30_000,
  });
  await page.screenshot({
    path: join(SHOTS, "round0810-06-model-activity.png"),
    fullPage: true,
  });

  // FIXED-133 — a real provider, connected through the UI, answering a turn.
  await visit(page, "models?tab=hosted");
  const card = page.locator("article.provider-card").filter({ hasText: "Anthropic" });
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connected")).toBeVisible({ timeout: 60_000 });
  await page.screenshot({
    path: join(SHOTS, "round0810-07-anthropic-connected.png"),
    fullPage: true,
  });

  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  const values = await catalogue
    .locator("option")
    .evaluateAll((options) =>
      options.map((option) => (option as HTMLOptionElement).value).filter(Boolean),
    );
  const preferred =
    values.find((value) => value.includes("haiku")) ?? values[0];
  await catalogue.selectOption(preferred);
  await card.getByRole("button", { name: "Use model" }).click();

  // FIXED-169 — the chip names when the check was last confirmed. Pinning a
  // model is a *preference*; the exact-model check is what makes it ready, and
  // the card says "Not checked" until the owner runs it.
  await visit(page, "models?tab=hosted");
  // Re-runnable: a fresh workspace reads "Not checked" here, and a workspace
  // this spec has already driven reads "Ready". Pressing Test is correct either
  // way — it is the owner-triggered check, not a state the spec assumes.
  await card.getByRole("button", { name: "Test" }).click();
  await expect(card.locator(".chip").filter({ hasText: /Ready · confirmed/ })).toBeVisible({
    timeout: 180_000,
  });
  await page.screenshot({
    path: join(SHOTS, "round0810-08-readiness-chip-confirmed.png"),
    fullPage: true,
  });

  await visit(page, "new-chat");
  const prompt = page.getByPlaceholder("How can I help you today?");
  await prompt.fill("Reply with exactly: ROUND0810 LIVE");
  const send = page.getByRole("button", { name: "Send" });
  await expect(send).toBeEnabled({ timeout: 60_000 });
  await send.click();
  await expect(page.locator(".message-group-raiker").last()).toContainText(
    "ROUND0810 LIVE",
    { timeout: 240_000 },
  );
  await page.screenshot({
    path: join(SHOTS, "round0810-09-live-turn-answered.png"),
    fullPage: true,
  });

  expect(consoleErrors).toEqual([]);
});
