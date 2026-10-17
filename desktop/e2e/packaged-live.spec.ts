// SPDX-License-Identifier: Apache-2.0
/**
 * DESK-12 — the packaged application starts its own bundled host.
 *
 * Run by hand after `npm run package -- --linux dir` (or any `release/*-unpacked`
 * build): RAIKER_PACKAGED_APP names the executable and RAIKER_HOME an empty
 * workspace. The shell must start the frozen host from `resources/host`, wait
 * for its ready file, and show the owner's first-run screen — no terminal, no
 * browser, no Python on the machine.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import { _electron as electron, expect, test } from "@playwright/test";

const APP = process.env.RAIKER_PACKAGED_APP ?? "";
const SHOTS = process.env.RAIKER_DESKTOP_SHOTS ?? "test-results";

test("the packaged app starts its bundled host and opens on first run", async () => {
  test.skip(APP === "", "set RAIKER_PACKAGED_APP to a packaged Raiker executable");
  test.setTimeout(180_000);
  const app = await electron.launch({
    executablePath: APP,
    args: ["--no-sandbox"],
    env: {
      ...process.env,
      RAIKER_DESKTOP_USER_DATA: mkdtempSync(join(tmpdir(), "raiker-packaged-")),
    },
  });
  const page = await app.firstWindow();
  await expect(page.getByLabel("Username")).toBeVisible({ timeout: 150_000 });
  expect(page.url()).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/$/);
  await expect(page.locator("html")).toHaveAttribute("data-desktop-shell", "linux");
  await page.screenshot({ path: join(SHOTS, "desktop-packaged-first-run.png") });
  // The host outlives the window by design. Stop it the way an owner can from
  // a terminal, so the round leaves nothing running — and before closing the
  // shell, because a detached child still holds the test runner's pipe.
  const host = join(dirname(APP), "resources", "host", process.platform === "win32" ? "Raiker.exe" : "Raiker");
  const quit = spawnSync(host, ["quit", "--force"], { encoding: "utf-8", env: process.env });
  expect(quit.stdout).toContain("Asked process");
  await app.close();
});
