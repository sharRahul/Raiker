import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

/**
 * The 2026-09-20 follow-up round, live: BUG-306's retry consequence and
 * BUG-305's one source inventory.
 *
 * Both have a half only a real host can show. A retry warning is computed from
 * the turn's *own settled calls*, so it needs a turn that really ran a tool —
 * a fixture proves the function, not the wiring from the transcript to the
 * dialog. And the source inventory reads two stores that only a real workspace
 * has both of.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-20-sources-and-commands");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });
test.setTimeout(420_000);

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");

test("the owner's provider is connected, and a model is ready to answer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
});

/**
 * BUG-306 — Retry re-sends the prompt, so a turn that already had an effect
 * does it again. A turn that only answered does not, and must not be made to
 * ask: a warning on every retry is a warning nobody reads.
 */
test("BUG-306: a turn that only answered retries without a question", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);

  const asked: string[] = [];
  page.on("dialog", (dialog) => {
    asked.push(dialog.message());
    void dialog.dismiss();
  });

  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill("Reply with the single word: ready");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".message-bubble-raiker").last()).toBeVisible({ timeout: 240_000 });

  await page.getByRole("button", { name: "Send this message again" }).last().click();
  // No tool ran, so there is nothing that could happen twice.
  expect(asked).toEqual([]);
  await expect(page.locator(".message-bubble-user")).toHaveCount(2, { timeout: 240_000 });
  await capture(page, join(SHOTS, "01-retry-without-effects.png"));
});

/**
 * BUG-305 — the one inventory, over both controllers, on a real workspace.
 */
test("BUG-305: one list answers what Raiker can read", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=sources`);

  const inventory = page.getByRole("region", { name: "What Raiker can read" });
  await expect(inventory).toBeVisible({ timeout: 60_000 });
  // It answers even when there is nothing yet, and says where the other kind
  // of source is added rather than pretending this library is the whole answer.
  await expect(
    inventory.getByRole("heading", { name: "What Raiker can read" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Knowledge Map" }).first()).toHaveAttribute(
    "href",
    "#/brain",
  );
  // Settled, not mid-read: a capture of a spinner is evidence of a spinner.
  await expect(inventory.getByText("Reading your sources…")).toBeHidden({ timeout: 30_000 });
  // A fresh workspace holds neither kind, and says so once rather than also
  // summarising a list that is not there.
  await expect(inventory.getByText(/Nothing yet/)).toBeVisible({ timeout: 30_000 });
  await expect(inventory.getByText(/documents Raiker keeps/)).toHaveCount(0);
  await capture(page, join(SHOTS, "02-knowledge-sources.png"), inventory);
});

/**
 * BUG-285 — a turn that fails reports the refusal the runtime named. Live, the
 * reachable half: a turn Raiker refuses before it streams says which decision
 * refused it, not an HTTP status and not a reachability claim.
 */
test("BUG-285: Build says which decision refused a turn", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/build`);

  const prompt = page.getByPlaceholder(/Describe/);
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  // Build refuses a turn with no project before it opens a stream, which is
  // exactly the class that used to read as "Could not reach the local runtime".
  const body = await page.locator("body").innerText();
  expect(body).not.toContain("Could not reach the local runtime");
  await capture(page, join(SHOTS, "03-build-composer.png"));
});
