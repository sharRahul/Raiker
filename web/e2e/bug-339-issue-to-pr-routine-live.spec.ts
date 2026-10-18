/**
 * BUG-339 — the issue-to-pull-request routine, previewed on a running host.
 *
 * Settings → GitHub shows which steps of the routine would run before anything
 * is scheduled. This drives the preview with no delegation, which needs no
 * GitHub connection: every write step must say it asks, merge must be named as
 * never part of it, and the schedule button stays disabled until a project is
 * chosen (the component test proves the preview itself posts no task).
 * Scheduling it against a consented repository is RR-40's live round.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = "../../docs/screenshots/2026-10-18-bug-339-issue-to-pr";

test("the issue-to-PR routine shows its plan and schedules nothing by itself", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=github`);
  const form = page.getByTestId("github-issue-routine");
  await expect(form).toBeVisible({ timeout: 30_000 });

  await form.getByLabel("Repository to work in").fill("octo/demo");
  await form.getByLabel("Issue").fill("7");
  await form.getByRole("button", { name: "Show the plan" }).click();

  const plan = page.getByTestId("github-issue-routine-plan");
  await expect(plan).toBeVisible({ timeout: 30_000 });
  for (const label of ["Create a work branch", "Push the work branch", "Open a pull request"]) {
    await expect(plan.getByRole("listitem").filter({ hasText: label })).toContainText("Asks you first");
  }
  await expect(page.getByText(/^Never: .*merge/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Schedule as a Build task" })).toBeDisabled();
  await capture(page, `${SHOTS}/routine-plan.png`);
});
