// SPDX-License-Identifier: Apache-2.0
/**
 * DESK-12 — the packaged application starts its own bundled host.
 *
 * Run against an installed or unpacked package — by hand, or by
 * `.github/workflows/desktop-package.yml` on each platform's own runner after it
 * has installed the package: RAIKER_PACKAGED_APP names the executable and
 * RAIKER_HOME an empty workspace. The shell must open its Setup window, check
 * this computer, start the frozen host from `resources/host`, verify it, and
 * then show the owner's first-run screen — no terminal, no browser, no Python
 * on the machine.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import { _electron as electron, expect, test } from "@playwright/test";

import { finishInstalling } from "./setupWindow";

const APP = process.env.RAIKER_PACKAGED_APP ?? "";
const SHOTS = process.env.RAIKER_DESKTOP_SHOTS ?? "test-results";

test("the packaged app starts its bundled host and opens on first run", async () => {
  test.skip(APP === "", "set RAIKER_PACKAGED_APP to a packaged Raiker executable");
  test.setTimeout(240_000);
  const app = await electron.launch({
    executablePath: APP,
    args: ["--no-sandbox"],
    env: {
      ...process.env,
      RAIKER_DESKTOP_USER_DATA: mkdtempSync(join(tmpdir(), "raiker-packaged-")),
    },
  });
  const page = await finishInstalling(app, SHOTS, "packaged");
  await expect(page.getByLabel("Username")).toBeVisible({ timeout: 60_000 });
  expect(page.url()).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/$/);
  await expect(page.locator("html")).toHaveAttribute("data-desktop-shell", process.platform);
  await page.screenshot({ path: join(SHOTS, "desktop-packaged-first-run.png") });
  // The host outlives the window by design. Stop it the way an owner can from
  // a terminal, so the round leaves nothing running — and before closing the
  // shell, because a detached child still holds the test runner's pipe.
  // `resources/host/` beside the executable; inside the bundle on macOS.
  const resources =
    process.platform === "darwin" ? join(dirname(APP), "..", "Resources") : join(dirname(APP), "resources");
  const host = join(resources, "host", process.platform === "win32" ? "Raiker.exe" : "Raiker");
  const quit = spawnSync(host, ["quit", "--force"], { encoding: "utf-8", env: process.env });
  expect(quit.stdout).toContain("Asked process");
  await app.close();
});
