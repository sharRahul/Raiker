/**
 * The 2026-10-05 (fifth) round, lock-screen phases (BUG-323, DEC-24 steps 5–6,
 * DEC-17 step 8). Each phase starts with `raiker-web` stopped and the store put
 * into the state under test by `scripts/live_recovery_harness.py`, then the host
 * started again:
 *
 * - `RAIKER_LIVE_PHASE=damaged` — `damage`: this key no longer opens the file;
 * - `RAIKER_LIVE_PHASE=newer` — `newer`: a newer Raiker shaped the database.
 *
 * In both, the lock screen lists the workspace's backups from their manifests,
 * restores one in place with the unopenable database kept in quarantine, and
 * the owner signs in again. The first phase also proves that a conversation
 * deleted after the backup (`round-2026-10-05-recovery-live.spec.ts`) stays
 * deleted.
 */
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-recovery-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const PHASE = process.env.RAIKER_LIVE_PHASE ?? "";
const DELETED = process.env.RAIKER_LIVE_DELETED_SESSION ?? "";

test.describe.configure({ mode: "serial" });
test.use({ timezoneId: "UTC" });

function harness(...args: string[]): Record<string, unknown> {
  const out = execFileSync(PYTHON, [join(REPO, "scripts", "live_recovery_harness.py"), WORKSPACE, ...args], {
    encoding: "utf-8",
  });
  return JSON.parse(out.trim()) as Record<string, unknown>;
}

test("a damaged workspace is restored from the lock screen, and what was deleted stays deleted", async ({ page }) => {
  test.skip(PHASE !== "damaged", "runs in the damaged-store phase");
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("I cannot open my encrypted store.")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("lock-recovery");
  await expect(panel).toContainText("Restore from a backup");
  const row = page.getByTestId("lock-recovery-backup").filter({ hasText: "Taken by you" }).first();
  await expect(row).toContainText(/conversations · \d+ memories/);
  await expect(page.getByLabel("Username")).toBeDisabled();
  await capture(page, join(SHOTS, "10-lock-screen-offers-backups.png"));
  await row.getByRole("button", { name: "Restore…" }).click();
  await row.getByRole("button", { name: "Restore this backup" }).click();
  const restored = page.getByTestId("lock-restored");
  await expect(restored).toContainText(".raiker/quarantine/", { timeout: 60_000 });
  await expect(page.getByLabel("Username")).toBeEnabled({ timeout: 30_000 });
  await capture(page, join(SHOTS, "11-lock-screen-restored.png"));

  const held = harness("quarantine") as { held: string[]; notes: { restored_from: string; moved: string[] }[] };
  expect(held.held.length).toBe(1);
  expect(held.notes[0].moved).toContain("raiker.db");
  if (DELETED) {
    const left = harness("sessions") as { sessions: { session_id: string }[] };
    expect(left.sessions.map((entry) => entry.session_id)).not.toContain(DELETED);
    expect(left.sessions.length).toBeGreaterThan(0);
  }
  await signInAsOwner(page, BASE);
  await expect(page.getByText("I cannot open my encrypted store.")).toHaveCount(0);
});

test("a database a newer Raiker shaped is refused, and a backup this build can open is offered", async ({ page }) => {
  test.skip(PHASE !== "newer", "runs in the newer-schema phase");
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/last opened by a newer Raiker/).first()).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("lock-recovery");
  await expect(panel).toContainText("A newer Raiker last opened this workspace.");
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "12-lock-screen-newer-schema-390.png"));
  const row = page.getByTestId("lock-recovery-backup").filter({ hasText: "Taken by you" }).first();
  await row.getByRole("button", { name: "Restore…" }).click();
  await row.getByRole("button", { name: "Restore this backup" }).click();
  await expect(page.getByTestId("lock-restored")).toBeVisible({ timeout: 60_000 });
  await signInAsOwner(page, BASE);
});
