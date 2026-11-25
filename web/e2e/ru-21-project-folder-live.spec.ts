/**
 * RT-1125-11 — RU-21 against a running host.
 *
 * **Create project** makes the project its own folder under
 * `Raiker Projects` (the host is started with `RAIKER_PROJECTS_HOME` pointing at
 * a scratch folder, so a round never writes into the owner's home), and the card
 * shows where it goes.
 */
import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { join } from "node:path";

import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { roundName } from "./naming";

const PROJECTS_HOME = process.env.RAIKER_PROJECTS_HOME ?? "";

test.describe.configure({ mode: "serial" });

test("Create project makes the project its own folder in Raiker Projects (RU-21)", async ({ page }) => {
  test.skip(PROJECTS_HOME === "", "start the host and this run with RAIKER_PROJECTS_HOME");
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  const name = roundName("Pricing");
  await page.goto(`${BASE}/#/projects`);
  await expect(page.getByTestId("project-folder-hint")).toBeVisible();
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText(name).first()).toBeVisible({ timeout: 30_000 });
  expect(existsSync(join(PROJECTS_HOME, name))).toBe(true);
  await capture(page, "../../output/playwright/ru-21-project-folder.png");
});
