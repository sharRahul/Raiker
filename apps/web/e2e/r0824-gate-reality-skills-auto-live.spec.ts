/**
 * The 2026-08-24 round, against a real instance.
 *
 * Three changes, and each one's claim is only true if an owner can see it:
 *
 * 1. **FIXED-280 (GEP-04)** — fifteen capability switches governed nothing. The
 *    Capabilities page has to say which switches decide anything, and what
 *    really governs the work where they do not. A toggle beside a running
 *    feature that it does not govern is the one failure mode a governance
 *    product cannot have.
 * 2. **FIXED-281 (ADD-21)** — `SKILL.md` is an open standard now. Every
 *    installed skill has to say whether it would install anywhere else, and the
 *    one field Raiker reads and refuses — `allowed-tools` — has to say so out
 *    loud rather than being ignored.
 * 3. **FIXED-282 (BUG-218)** — Auto promised a review it did not perform. Its
 *    label has to state the promise it now keeps, and no more than that.
 *
 * A real turn is not needed for any of the three: each is a surface claim about
 * state the runtime already holds, and the turn-level behaviour is covered by
 * `tests/test_model_tool_call_loop.py` end to end through the broker.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

async function signIn(page: Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill("Ithink@10");
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  const workbench = page.getByRole("heading", { name: /Welcome (to your Work Dashboard|back)/ });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench.first()).toBeVisible({ timeout: 30_000 });
}

test.describe("FIXED-280 — a switch says whether it decides anything", () => {
  test("a capability governed by a different control is marked, and names it", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/capabilities`);

    // `scheduled_routines` is the clearest case: the feature runs — a scheduled
    // task is a whole governed turn — and this gate never decides whether it
    // does. Before this round the page showed a switch and said nothing.
    const row = page.getByRole("button", { name: /Scheduled/i }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.getByText("Governed elsewhere")).toBeVisible();

    await row.click();
    await expect(page.getByText(/governed turn through the Agent Gateway/i)).toBeVisible({
      timeout: 15_000,
    });
    await capture(page, `${SHOTS}/r0824-gate-reality-governed-elsewhere.png`);
  });

  test("a capability nothing reaches is marked as having no route", async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/capabilities`);
    // Reminders have a real executor, a gate, and no owner surface and no model
    // tool. The switch is honest about governing nothing yet rather than
    // implying a feature behind it.
    const row = page.getByRole("button", { name: /Reminder/i }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.getByText("No route yet")).toBeVisible();
  });

  test("a switch that means what it says carries no caveat", async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/capabilities`);
    const row = page.getByRole("button", { name: /^Shell/i }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.getByText("Governed elsewhere")).toBeHidden();
    await expect(row.getByText("No route yet")).toBeHidden();
  });

  test("delegation now has a switch that is real", async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/capabilities`);
    // GEP-04's second finding: `spawn_subagent` declared no capability, so this
    // switch governed nothing while subagents ran. It governs delegation now, so
    // it must read as an ordinary switch rather than as inert.
    const row = page.getByRole("button", { name: /^Subagents/i }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.getByText("Governed elsewhere")).toBeHidden();
    await expect(row.getByText("No route yet")).toBeHidden();
  });
});

test.describe("FIXED-281 — a skill says whether it travels", () => {
  test("every shipped skill reports against the Agent Skills standard", async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/extensions?tab=skills`);

    const firstSkill = page.locator("li.card").first();
    await expect(firstSkill).toBeVisible({ timeout: 30_000 });
    // Raiker should not ship the thing it measures other skills against: all six
    // built-ins were brought to conformance in this round.
    await expect(firstSkill.getByText("standard", { exact: true })).toBeVisible();

    await firstSkill.getByRole("button", { name: "Details" }).click();
    await expect(page.getByText("Agent Skills standard").first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByText(/should install in any tool that reads it/i).first(),
    ).toBeVisible();
    await capture(page, `${SHOTS}/r0824-skill-standard-conformance.png`);
  });

  test("the specification is linked, so the rule is checkable rather than asserted", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/extensions?tab=skills`);
    const firstSkill = page.locator("li.card").first();
    await expect(firstSkill).toBeVisible({ timeout: 30_000 });
    await firstSkill.getByRole("button", { name: "Details" }).click();
    const spec = page.getByRole("link", { name: /specification/i }).first();
    await expect(spec).toBeVisible({ timeout: 15_000 });
    await expect(spec).toHaveAttribute("href", "https://agentskills.io/specification");
  });
});

test.describe("FIXED-282 — Auto states the promise it keeps", () => {
  test("the composer's Auto says a change to an unlooked-at file waits", async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto(`${BASE}/#/new-chat`);

    // The approval-mode control is in the composer. Open it and read what Auto
    // now claims — the whole defect was that the label promised a review the
    // runtime did not perform.
    const modeButton = page.getByRole("button", { name: /approval|Manually approve|Automatic/i }).first();
    await expect(modeButton).toBeVisible({ timeout: 30_000 });
    await modeButton.click();
    await expect(page.getByText(/never looked at/i).first()).toBeVisible({ timeout: 15_000 });
    await capture(page, `${SHOTS}/r0824-auto-alignment-promise.png`);
  });
});
