/**
 * The key is added through the UI, and a real turn answers.
 *
 * This is the end-to-end half of the RR-MCP-02 round: the endpoint-trust
 * changes sit on the same governed path a model call takes, so the round is not
 * evidence of anything until a live provider turn still works with them in
 * place. The key is typed into the product's own Connect dialog rather than
 * written into a file, the model is chosen from the composer's own picker, and
 * the answer is the model's.
 *
 * Written separately from `bug-206-207-…` because that spec pins a model on the
 * provider card and expects the composer to already be holding it. On a
 * workspace where no global model has ever been chosen the composer is honest
 * about that — "No model is chosen" — and the turn cannot be sent. Choosing it
 * where an owner chooses it is what this spec does differently.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = "../../docs/screenshots/2026-09-13-mcp-endpoint-trust";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

test("the provider key is added through the UI and a real turn answers", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: KEY,
    model: MODEL,
  });
  await expect(card.locator("code")).toBeVisible({ timeout: 60_000 });

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("group", { name: "Message composer" });

  // Where an owner chooses the model: the picker beside Send. A workspace that
  // has never chosen one says so rather than guessing, which is right, and it
  // means the choice has to be made before a turn can go.
  await composer.getByRole("button", { name: /^Model for this turn:/ }).click();
  const menu = page.getByRole("menu", { name: "Models" });
  await expect(menu).toBeVisible({ timeout: 30_000 });
  // A radio, not a plain item: the menu is a single choice among the models the
  // owner's providers published, and it says so in its roles.
  await menu.getByRole("menuitemradio", { name: /Haiku 4\.5/i }).first().click();
  await expect(
    composer.getByRole("button", { name: /^Model for this turn: (?!Not selected)/ }),
  ).toBeVisible({ timeout: 30_000 });

  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: RRMCP LIVE");
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();

  await expect(page.getByRole("main").getByText("RRMCP LIVE", { exact: true })).toBeVisible({
    timeout: 300_000,
  });

  await capture(page, `${SHOTS}/live-anthropic-turn.png`);
});
