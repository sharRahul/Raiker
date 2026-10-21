// SPDX-License-Identifier: Apache-2.0
/**
 * DIST-05/06 — an owner installs Raiker and completes first-run setup in the
 * installed window, with no terminal, browser or developer tool. The Setup
 * window checks the computer and verifies the installation first, so the
 * in-app setup conversation asks only what an owner decides: a name, where
 * Raiker should think, and how it will ask before acting.
 *
 * Same inputs as `packaged-live.spec.ts`: RAIKER_PACKAGED_APP names the
 * installed executable and RAIKER_HOME an empty profile. No model credential is
 * used — the owner chooses "Decide later", which is a supported path — so this
 * proves the installation and the onboarding, not a provider.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import { _electron as electron, expect, test } from "@playwright/test";

import { finishInstalling } from "./setupWindow";

const APP = process.env.RAIKER_PACKAGED_APP ?? "";
const SHOTS = process.env.RAIKER_DESKTOP_SHOTS ?? "test-results";

function hostPath(): string {
  const resources =
    process.platform === "darwin" ? join(dirname(APP), "..", "Resources") : join(dirname(APP), "resources");
  return join(resources, "host", process.platform === "win32" ? "Raiker.exe" : "Raiker");
}

test("an owner completes first-run setup in the installed window", async () => {
  test.skip(APP === "", "set RAIKER_PACKAGED_APP to an installed Raiker executable");
  test.setTimeout(300_000);
  // A profile of its own, so the owner account is always the first one.
  const env = {
    ...process.env,
    RAIKER_HOME: mkdtempSync(join(tmpdir(), "raiker-onboarding-home-")),
    RAIKER_DESKTOP_USER_DATA: mkdtempSync(join(tmpdir(), "raiker-onboarding-")),
  };
  const app = await electron.launch({ executablePath: APP, args: ["--no-sandbox"], env });
  try {
    // The computer is checked and the installation verified before any account exists.
    const page = await finishInstalling(app, SHOTS, "onboarding");
    await expect(page.getByLabel("Username")).toBeVisible({ timeout: 60_000 });
    const password = "Correct-Horse-Battery-9";
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Confirm password").fill(password);
    await page.getByRole("button", { name: "Create a User Account" }).click();

    // QUI-W02 — first run is a setup conversation. It opens on Hello, and the
    // installer already checked this computer, so the device step is absent.
    const title = page.locator("#setup-title");
    await expect(title).toHaveText(/^Hi, I'm Raiker/, { timeout: 60_000 });
    await expect(page.locator(".stage-rail")).not.toContainText("This device");
    await page.screenshot({ path: join(SHOTS, "onboarding-1-hello.png") });
    await page.getByLabel("Your name").fill("Owner");
    await page.getByRole("button", { name: "Continue", exact: true }).click();

    await expect(title).toHaveText("Where should I think?", { timeout: 60_000 });
    await page.getByRole("button", { name: /^Decide later/ }).click();

    await expect(title).toHaveText("Here is how I'll work for you.", { timeout: 30_000 });
    await page.getByRole("button", { name: "Continue", exact: true }).click();

    await expect(title).not.toHaveText("Here is how I'll work for you.", { timeout: 30_000 });
    if ((await title.textContent())?.includes("Checking your installation")) {
      const proceed = page.getByRole("button", { name: /^(Continue|Continue anyway)$/ });
      await expect(proceed).toBeEnabled({ timeout: 120_000 });
      await proceed.click();
    }
    await expect(title).toHaveText(/^Setup is saved\./, { timeout: 30_000 });
    await page.screenshot({ path: join(SHOTS, "onboarding-2-ready.png") });
    await page.getByRole("button", { name: "Go to Home" }).click();
    await expect(page).toHaveURL(/#\/home/);
    await expect(page.getByRole("heading", { name: /, Owner$/ })).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: join(SHOTS, "onboarding-3-home.png") });
  } finally {
    spawnSync(hostPath(), ["quit", "--force"], { encoding: "utf-8", env });
    await app.close();
  }
});
