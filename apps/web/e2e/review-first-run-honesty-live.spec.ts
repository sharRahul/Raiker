import { expect, test } from "@playwright/test";
import { join } from "node:path";

/**
 * BUG-198's evidence: what stage 02 of the first-run wizard claims about
 * backends that are not installed.
 *
 * Deliberately runs against a workspace with **no** model runtime on the host —
 * no llama.cpp binary, no Ollama process, nothing listening on 11434 — because
 * the defect is that the wizard says `Connected` anyway. The spec records the
 * label next to every offered backend rather than asserting one, so the
 * screenshot and the log say the same thing.
 */

const BASE = process.env.RAIKER_LIVE_FIRSTRUN_BASE ?? "http://127.0.0.1:8766";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "First-run-honesty-1!";

test("stage 02 labels every offered backend", async ({ page }) => {
  test.setTimeout(300_000);

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 60_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  await expect(confirm).toBeVisible({ timeout: 30_000 });
  await confirm.fill(PASSWORD);
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Choose where Raiker thinks" })).toBeVisible({
    timeout: 60_000,
  });

  const choices = page.locator(".choice-list button");
  const count = await choices.count();
  const rows: string[] = [];
  for (let index = 0; index < count; index += 1) {
    rows.push((await choices.nth(index).innerText()).replace(/\s+/g, " ").trim());
  }
  console.log(`STAGE 02 OFFERS ${count} BACKENDS:\n` + rows.join("\n"));

  await page.screenshot({
    path: join(SHOTS, "bug198-first-run-connected-unreachable.png"),
    fullPage: true,
  });
});
