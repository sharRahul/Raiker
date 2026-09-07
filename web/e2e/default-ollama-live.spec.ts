import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

/**
 * BUG-270 — a fresh workspace must not name a model that is not installed.
 *
 * This spec used to assert the opposite: that Models, Chat and Build all read
 * "Gemma 4:31B Cloud" out of the box. They did, on a host with no `ollama`
 * binary and nothing listening on 11434, because the only `is_native_default`
 * profile hard-codes a third-party model string and nothing enforced its own
 * `disabled_until_provider_detected` declaration.
 *
 * The CI host has no Ollama, so this now walks the three surfaces the old spec
 * walked and asserts that none of them names it — and that Models says why.
 */
test("a fresh workspace names no model when the runtime is not installed", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });

  await page.goto(`${BASE}/#/models`);
  // The provider is still offered for setup — it is the model claim that was
  // wrong, not the profile's existence.
  await expect(page.getByRole("heading", { name: "Ollama" }).first()).toBeVisible();
  await expect(page.getByText("Gemma 4:31B Cloud", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Not installed on this machine").first()).toBeVisible();
  await capture(page, join(SHOTS, "bug-270-models-no-undetected-model-live.png"));

  await page.goto(`${BASE}/#/new-chat`);
  await expect(
    page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" }),
  ).toHaveCount(0);
  await capture(page, join(SHOTS, "bug-270-chat-no-undetected-model-live.png"));

  await page.goto(`${BASE}/#/build`);
  await expect(
    page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" }),
  ).toHaveCount(0);
  await capture(page, join(SHOTS, "bug-270-build-no-undetected-model-live.png"));
});
