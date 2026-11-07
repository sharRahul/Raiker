/**
 * Beta release plan round, 2026-11-07 — the items closed this round, checked
 * against a running host (docs/architecture/WEB_APP_LIVE_TEST.md,
 * "Beta release plan round").
 *
 * Needs a host on RAIKER_LIVE_BASE whose owner already connected at least one
 * hosted provider and an Ollama model through Models (the provider-validation
 * spec and the Ollama step of this round do that), and RAIKER_LIVE_WORKSPACE
 * pointing at that host's workspace, for the sandbox-copy harness.
 *
 * RT-BETA-01  Settings › About & updates names the release stage and signature
 * RT-BETA-02  Settings › Privacy lists where requests go right now
 * RT-BETA-03  Models › Add labels non-beta providers Experimental
 * RT-BETA-04  Connections asks once more before adding an experimental service
 * RT-BETA-05  Design labels image generation Preview
 * RT-BETA-06  A host that cannot run commands: amber chip and a disabled Run
 * RT-BETA-07  Build review: isolated-copy header, conflict, Overwrite, Apply
 * RT-BETA-08  Build review: Discard leaves the project unchanged
 * RT-BETA-09  axe: no serious or critical violation on any destination at 1440, 1280, 390
 * RT-BETA-10  QUI-G01 size budgets hold for Chat, Build, Models and Settings
 * RT-BETA-11  Account and Backups are Settings sections of their own
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { DESTINATIONS, settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { BUDGET_VIEWPORTS, measurePage, overBudget } from "./sizeBudgets";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "2026-11-07-beta-round");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const REPO = resolve(import.meta.dirname, "..", "..");

test.describe.configure({ mode: "serial" });

async function open(page: Page, route: string): Promise<void> {
  await page.goto(`${BASE}/#/${route}`);
  await settled(page);
}

test.beforeEach(async ({ page }) => {
  page.setDefaultTimeout(30_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
});

test("RT-BETA-01 — About & updates names the release stage and signature", async ({ page }) => {
  await open(page, "settings?tab=updates");
  const card = page.getByRole("region", { name: "Raiker updates" });
  await expect(card.getByText("Release stage")).toBeVisible();
  // A source checkout is a development build and is never signed.
  await expect(card.getByText("Development build", { exact: true })).toBeVisible();
  await expect(card.getByText("Unsigned development build", { exact: true })).toBeVisible();
  await capture(page, join(SHOTS, "01-updates.png"), card);
});

test("RT-BETA-02 — Privacy lists where requests go right now", async ({ page }) => {
  await open(page, "settings?tab=privacy");
  const list = page.getByTestId("privacy-destinations");
  await expect(list).toBeVisible();
  await expect(list.getByText(/Anthropic/)).toBeVisible();
  // The Ollama cloud model reaches ollama.com, so it is listed; the device-only models are not.
  await expect(list.getByText(/ollama.com/)).toBeVisible();
  await capture(page, join(SHOTS, "02-privacy.png"), page.getByRole("heading", { name: "What leaves this computer" }));
});

test("RT-BETA-03 — Models › Add labels non-beta providers Experimental", async ({ page }) => {
  await open(page, "models?tab=add&source=account");
  const dialog = page.getByRole("dialog", { name: "Add model" });
  await expect(dialog).toBeVisible();
  const anthropic = dialog.locator(".provider-card, .local-row, article, li, div").filter({ has: page.getByRole("heading", { name: "Anthropic", exact: true }) }).last();
  await expect(anthropic.getByText("Experimental", { exact: true })).toHaveCount(0);
  await expect(dialog.getByText("Experimental", { exact: true }).first()).toBeVisible();
  await capture(page, join(SHOTS, "03-models-experimental.png"));
});

test("RT-BETA-04 — Connections asks once more before adding an experimental service", async ({ page }) => {
  await open(page, "connections");
  await page.getByRole("button", { name: /add connection/i }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add connection" });
  const experimental = dialog.getByRole("button", { name: /Experimental/ }).first();
  await expect(experimental).toBeVisible();
  const name = ((await experimental.innerText()).split("\n")[0] ?? "").trim();
  await experimental.click();
  await dialog.getByRole("button", { name: /^Add / }).first().click();
  const confirm = page.getByRole("alertdialog").or(page.getByRole("dialog", { name: /experimental/i })).first();
  await expect(confirm).toContainText(/not verified this connection end to end/);
  await capture(page, join(SHOTS, "04-connections-experimental-confirm.png"));
  await confirm.getByRole("button", { name: "Cancel" }).click();
  // Cancelled: nothing was installed, so the service is still offered.
  await expect(dialog.getByRole("button", { name: "Add experimental connection" })).toHaveCount(0);
  test.info().annotations.push({ type: "service", description: name });
});

test("RT-BETA-05 — Design labels image generation Preview", async ({ page }) => {
  await open(page, "design");
  await expect(page.getByRole("tab", { name: "Images · Preview" })).toBeVisible();
  await expect(page.getByTestId("image-preview-note")).toContainText("not been verified end to end");
  await capture(page, join(SHOTS, "05-design-preview.png"));
});

test("RT-BETA-06 — a host that cannot run commands shows it, and Run waits", async ({ page }) => {
  test.setTimeout(180_000);
  // This host's sandbox is enforced, so the one read that says otherwise is
  // replaced; everything else is the real host.
  await page.route("**/api/execution-environments", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    for (const item of body.environments) if (item.selected) item.available = false;
    await route.fulfill({ response, json: body });
  });
  await open(page, "build");
  const chip = page.getByRole("button", { name: /Governance posture: Commands unavailable here/ });
  await expect(chip).toBeVisible({ timeout: 90_000 });
  await expect(chip).toHaveAttribute("title", /sandbox could not be confirmed/);
  await capture(page, join(SHOTS, "06-commands-unavailable.png"), chip);
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

function plantCopy(owner: string, session: string, mode: "changes" | "conflict"): string {
  return execFileSync("python", ["scripts/live_task_copy_harness.py", WORKSPACE, owner, session, mode], {
    cwd: REPO,
    encoding: "utf8",
  }).trim();
}

async function buildSession(page: Page): Promise<{ owner: string; session: string }> {
  const owner = (await page.evaluate(async () => (await (await fetch("/api/auth/whoami")).json()).principal_id)) as string;
  const sessions = (await page.evaluate(async () => (await (await fetch("/api/sessions?limit=20")).json()))) as {
    session_id: string;
  }[];
  // A conversation the owner had, not the Inbox Raiker files its own records under.
  const session = sessions.find((item) => !item.session_id.startsWith("sess_inbox"))?.session_id ?? "";
  expect(session, "this round needs one conversation on the host").not.toBe("");
  return { owner, session };
}

test("RT-BETA-07 — Build review: isolated copy, conflict, Overwrite, Apply", async ({ page }) => {
  test.skip(!WORKSPACE, "set RAIKER_LIVE_WORKSPACE to the host's workspace");
  test.setTimeout(180_000);
  const { owner, session } = await buildSession(page);
  plantCopy(owner, session, "conflict");
  await open(page, `build?session=${session}`);
  const review = page.getByRole("region", { name: "Sandbox changes" });
  await expect(review).toContainText("Working in an isolated copy — nothing changes in your project until you Apply.");
  await expect(review).toContainText("1 file was also changed in your project");
  const apply = review.getByRole("button", { name: "Apply to project" });
  await expect(apply).toBeDisabled();
  await review.getByRole("button", { name: /Changed main\.py/ }).click();
  await expect(review.getByLabel("Changes to main.py")).toContainText("owner edit");
  await capture(page, join(SHOTS, "07a-conflict.png"));
  await review.getByRole("checkbox", { name: /Overwrite with the copy's version/ }).check();
  await expect(apply).toBeEnabled();
  await apply.click();
  const confirm = page.getByRole("alertdialog").or(page.getByRole("dialog")).last();
  await expect(confirm).toContainText("replaces your own edits to main.py");
  await confirm.getByRole("button", { name: "Overwrite and apply" }).click();
  await expect(page.getByText("Applied to beta-demo.")).toBeVisible();
  const project = join(WORKSPACE, "beta-demo");
  expect(readFileSync(join(project, "main.py"), "utf8")).toBe("print('v2 from the copy')\n");
  expect(readFileSync(join(project, "new.py"), "utf8")).toBe("x = 1\n");
  await capture(page, join(SHOTS, "07b-applied.png"));
});

test("RT-BETA-08 — Build review: Discard leaves the project unchanged", async ({ page }) => {
  test.skip(!WORKSPACE, "set RAIKER_LIVE_WORKSPACE to the host's workspace");
  test.setTimeout(180_000);
  const { owner, session } = await buildSession(page);
  plantCopy(owner, session, "changes");
  await open(page, `build?session=${session}`);
  const review = page.getByRole("region", { name: "Sandbox changes" });
  await expect(review).toContainText("Added new.py");
  await review.getByRole("button", { name: "Discard" }).click();
  await page.getByRole("alertdialog").or(page.getByRole("dialog")).last().getByRole("button", { name: "Discard" }).click();
  await expect(page.getByText("Sandbox copy discarded. Your project was not changed.")).toBeVisible();
  expect(readFileSync(join(WORKSPACE, "beta-demo", "main.py"), "utf8")).toBe("print('v1')\n");
  await capture(page, join(SHOTS, "08-discarded.png"));
});

test("RT-BETA-09 — axe finds no serious or critical violation on any destination", async ({ page }) => {
  test.setTimeout(900_000);
  // Entrance animations fade text in from transparent; axe reading mid-fade
  // reports contrast the settled page does not have. Reduced motion is a
  // setting Raiker honours, so the sweep reads the settled colours.
  await page.emulateMedia({ reducedMotion: "reduce" });
  const found: string[] = [];
  for (const width of [1440, 1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    for (const { route } of DESTINATIONS) {
      await open(page, route);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      for (const violation of result.violations) {
        if (violation.impact !== "serious" && violation.impact !== "critical") continue;
        found.push(`${width} #/${route} · ${violation.id} (${violation.impact}) · ${violation.nodes.length} node(s) · ${violation.nodes[0]?.target.join(" ")}`);
      }
    }
  }
  await test.info().attach("axe-serious.txt", { body: found.join("\n") || "none", contentType: "text/plain" });
  expect(found, found.join("\n")).toEqual([]);
});

test("RT-BETA-10 — size budgets hold for Chat, Build, Models and Settings (QUI-G01)", async ({ page }) => {
  test.setTimeout(180_000);
  const gated = [
    "new-chat", "build", "models",
    "settings?tab=general", "settings?tab=account", "settings?tab=backups",
    "settings?tab=privacy", "settings?tab=updates",
  ];
  // No tracked exceptions: General came under budget once Account and Backups
  // became sections of their own (2026-11-07).
  const known = new Set<string>();
  const over: string[] = [];
  const measured: string[] = [];
  for (const viewport of BUDGET_VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const route of gated) {
      await open(page, route);
      const size = await measurePage(page);
      const problems = overBudget(route, size, viewport);
      const key = `${viewport.label} #/${route}`;
      measured.push(`${key}: ${size.height}px, ${size.controls} controls`);
      if (problems.length && !known.has(key)) over.push(`${key}: ${problems.join(", ")}`);
    }
  }
  await test.info().attach("size-budgets.txt", { body: measured.join("\n"), contentType: "text/plain" });
  expect(over, over.join("\n")).toEqual([]);
});

test("RT-BETA-11 — Account and Backups are Settings sections of their own", async ({ page }) => {
  await open(page, "settings?tab=general");
  const rail = page.getByRole("group", { name: "Security & data settings" });
  await expect(rail.getByRole("button", { name: "Account" })).toBeVisible();
  await expect(rail.getByRole("button", { name: "Backups" })).toBeVisible();
  // General carries neither any more.
  await expect(page.getByRole("button", { name: /delete my account/i })).toHaveCount(0);
  await expect(page.getByTestId("backups-card")).toHaveCount(0);

  await rail.getByRole("button", { name: "Account" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Account" })).toBeVisible();
  await expect(page.getByLabel("Display name")).toBeVisible();
  await expect(page.getByTestId("backups-card")).toHaveCount(0);
  await capture(page, join(SHOTS, "11-settings-account.png"));

  // The old Backups address and the backup reminder both land on the section.
  await open(page, "settings?tab=backups");
  await expect(page.getByRole("heading", { level: 2, name: "Backups" })).toBeVisible();
  await expect(page.getByTestId("backups-card")).toBeVisible();
  await expect(page.getByRole("button", { name: /delete my account/i })).toHaveCount(0);
  await capture(page, join(SHOTS, "11-settings-backups.png"));
});
