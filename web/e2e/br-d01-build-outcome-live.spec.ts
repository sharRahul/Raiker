/**
 * BR-D01 — the checks an owner declares on a project, on a running host.
 *
 * The owner declares one check on Projects, saves it, and reads it back after a
 * reload. A Build turn's outcome against those checks is proven by
 * `tests/test_build_outcome.py` and `BuildOutcome.test.ts`; driving it with a real
 * model waits on BUG-346, where an accepted Build write on an Ollama cloud model
 * failed as an invalid tool call, so no real turn has yet changed a file here.
 */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-18-br-d01-build-outcome");
const CHECK = "python -m pytest -q";

test("the owner's checks are saved on the project and read back after a reload", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  const name = `Outcome round ${Date.now()}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  const checks = page.getByLabel("Project checks");
  await expect(checks).toBeVisible({ timeout: 30_000 });
  await checks.fill(CHECK);
  await expect(page.getByText(/Verified/).first()).toBeVisible();
  await page.getByRole("button", { name: "Save context" }).click();
  await expect(page.getByText(/unsaved changes/)).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  await expect(page.getByLabel("Project checks")).toHaveValue(CHECK, { timeout: 30_000 });
  await capture(page, join(SHOTS, "01-project-checks.png"));
});
