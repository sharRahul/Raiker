/**
 * The 2026-10-10 round, second phase (DEC-24 step 3): after the host is
 * restarted over a routine the first phase left `running`
 * (`round-2026-10-10-revisions-live.spec.ts`), Tasks shows it settled — moved
 * to its next slot, saying the last run did not finish and was not re-run.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-10-revisions-round");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";

test.use({ timezoneId: "UTC" });

test("a routine a stopped host left running is settled at the next start", async ({ page }) => {
  test.setTimeout(120_000);
  const taskId = readFileSync(join(WORKSPACE, "..", "interrupted-task.txt"), "utf-8").trim();
  expect(taskId).toMatch(/^task_/);
  await signInAsOwner(page, LIVE_BASE);
  await page.goto(`${LIVE_BASE}/#/tasks`);
  await settled(page);
  const card = page.getByText("Morning digest (interrupted)").first();
  await expect(card).toBeVisible({ timeout: 20_000 });
  // The card shows the next slot; the attempt that did not finish is in its history.
  await expect(page.getByText(/Runs daily, next/).first()).toBeVisible();
  await page.goto(`${LIVE_BASE}/#/tasks?task=${taskId}`);
  await settled(page);
  await expect(page.getByText(/Raiker stopped while this run was in progress/).first()).toBeVisible({ timeout: 20_000 });
  await capture(page, join(SHOTS, "14-interrupted-run-settled.png"));
});
