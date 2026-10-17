// SPDX-License-Identifier: Apache-2.0
/**
 * DIST-05 — the Setup window a packaged Raiker opens on its first start
 * (src/setup.ts): the owner presses Finish installing, watches this computer
 * checked, the host started and verified, and opens Raiker.
 */
import { join } from "node:path";

import { expect, type ElectronApplication, type Page } from "@playwright/test";

export async function finishInstalling(app: ElectronApplication, shots: string, prefix: string): Promise<Page> {
  const setup = await app.firstWindow();
  await expect(setup).toHaveTitle("Raiker Setup", { timeout: 60_000 });
  await expect(setup.getByRole("heading", { name: "Welcome to Raiker" })).toBeVisible();
  await setup.screenshot({ path: join(shots, `${prefix}-setup-1-welcome.png`) });
  await setup.getByRole("button", { name: "Finish installing" }).click();

  // The computer check runs first and lists what it found under its step.
  const found = setup.getByRole("list", { name: "This computer" });
  await expect(found).toBeVisible({ timeout: 60_000 });
  await expect(found.getByText("Operating system")).toBeVisible();
  await setup.screenshot({ path: join(shots, `${prefix}-setup-2-progress.png`) });

  await expect(setup.getByRole("heading", { name: "Raiker is ready" })).toBeVisible({ timeout: 150_000 });
  await setup.screenshot({ path: join(shots, `${prefix}-setup-3-ready.png`) });
  const [main] = await Promise.all([
    app.waitForEvent("window"),
    setup.getByRole("button", { name: "Open Raiker" }).click(),
  ]);
  return main;
}
