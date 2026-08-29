/**
 * Live evidence for the second 2026-08-17 round, driven through the product's
 * own UI against a real `raiker-web` and a real hosted provider.
 *
 * Two claims, each proved on the surface an owner actually uses:
 *
 * * **FIXED-237 (MEM-04)** — a governed tool result really does produce an
 *   eidetic observation, and Memory really does show it. This is the exact
 *   thing MEM-04 said could not happen: the entry's reproduction was "run a
 *   turn that reads a file, then count the rows — it is zero, on every
 *   workspace". Here the turn is real, the file is real, and the row is on
 *   screen with its retention, its expiry and its checksum.
 * * **FIXED-238 / FIXED-239 (BUG-194)** — Settings → Runtime states what each
 *   execution boundary really does between commands, built from the backend's
 *   own capabilities rather than from configuration, and offers the reset
 *   control only where a boundary genuinely persists.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { writeFileSync } from "node:fs";
import { dismissFirstRunModelSetup, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const PASSWORD = "Round-2026-08-17-review-password-1!";

const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "/tmp/raiker-live";

test.describe.configure({ mode: "serial" });

async function signIn(page: import("@playwright/test").Page): Promise<void> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  const username = page.getByLabel("Username");
  await expect(username).toBeVisible({ timeout: 20_000 });
  await username.fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /Sign in|Unlock/ }).click();
  }
  await expect(
    page
      .getByRole("button", { name: "Decide later" })
      .or(page.getByRole("heading", { name: "Welcome to your Work Dashboard" }))
      .first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
}

test("a governed read is recorded as an observation, and Memory shows it (MEM-04)", async ({
  page,
}) => {
  test.setTimeout(400_000);
  test.skip(!ANTHROPIC_KEY, "RAIKER_LIVE_ANTHROPIC_KEY is not set for this run");
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  // Something real for the turn to read. The observation records that this was
  // read — never what it said — so the file's contents matter only in that they
  // have to be long enough to be material rather than a status.
  writeFileSync(
    `${WORKSPACE}/deployment-runbook.md`,
    [
      "# Deployment runbook",
      "",
      "The release is cut on the first Tuesday of each month.",
      "Rollback is a revert of the release tag followed by a redeploy.",
      "The on-call engineer owns the decision to roll back.",
    ].join("\n"),
    "utf-8",
  );

  await signIn(page);
  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: /API key/i,
    key: ANTHROPIC_KEY,
    model: "claude-haiku-4-5-20251001",
  });
  await expect(card.getByText(/can reach/i)).toBeVisible({ timeout: 120_000 });

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("textbox", { name: /Message|Ask|Prompt/i }).first();
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(
    "Read the file deployment-runbook.md in the workspace and tell me in one sentence when the release is cut.",
  );
  const send = page.getByRole("button", { name: "Send", exact: true }).first();
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();
  // A real streamed answer, not a stub.
  await expect(page.getByText(/Tuesday/i).first()).toBeVisible({ timeout: 180_000 });
  await page.waitForTimeout(2_000);

  await page.goto(`${BASE}/#/memory`);
  const observations = page.locator("section[aria-label='Observations']");
  await expect(observations.getByRole("heading", { name: "Observations" })).toBeVisible({
    timeout: 30_000,
  });

  // The exact thing MEM-04 said could not happen. Before this change the count
  // was zero on every workspace, so an empty list here is the defect returning.
  const rows = observations.locator("article.observation");
  await expect(rows.first()).toBeVisible({ timeout: 30_000 });
  await expect(observations.getByText(/read_file/).first()).toBeVisible();
  // Metadata, and only metadata: a retention class, an expiry and a checksum.
  await expect(observations.getByText(/Kept \d+ days/).first()).toBeVisible();
  await expect(observations.getByText(/bytes$/).first()).toBeVisible();
  // And never the material. If the runbook's own sentences appear on this page
  // the observation has become a second copy of what the agent read.
  await expect(observations).not.toContainText("on-call engineer owns the decision");

  await capture(page, `${SHOTS}/r0817b-01-memory-observations-captured.png`);
  expect(consoleErrors).toEqual([]);
});

test("Runtime states what each boundary does between commands (BUG-194)", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  await signIn(page);
  await page.goto(`${BASE}/#/settings?tab=runtime`);
  const environments = page.locator("section.environment-settings");
  await expect(
    environments.getByRole("heading", { name: /Local, remote, and cloud environments/ }),
  ).toBeVisible({ timeout: 30_000 });

  const local = environments.locator("article").filter({ hasText: "Local strict" });
  // Read from the backend, not from configuration. Before this round the card
  // claimed neither of these while the backend offered both, so the environment
  // the owner read about was a different product from the one that ran their
  // command.
  await expect(local.getByText("Runs work in the background")).toBeVisible();
  await expect(local.getByText("Survives a Raiker restart")).toBeVisible();

  // The native sandbox does not persist and does not survive a restart, so it
  // gets neither line and no reset control — absent rather than disabled.
  const native = environments.locator("article").filter({ hasText: "Native OS sandbox" });
  await expect(native.getByText("Keeps its state between commands")).toHaveCount(0);
  await expect(native.getByRole("button", { name: "Reset environment" })).toHaveCount(0);

  await capture(page, `${SHOTS}/r0817b-02-runtime-environment-capabilities.png`);
  expect(consoleErrors).toEqual([]);
});
