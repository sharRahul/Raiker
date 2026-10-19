/**
 * DW-D02 to DW-D06 — the structured Design canvas on a running host.
 *
 * On a fresh `raiker-web` (`scripts/reset_live_workspace.py`):
 *
 * 1. Design → Documents creates a square social post; text and a rectangle are
 *    added, the text is rewritten in the inspector and nudged with the arrow
 *    keys, and undo/redo walk the structured versions.
 * 2. A mobile variant is made from the frame and named as one.
 * 3. A design system is created; choosing it previews the layer changes before
 *    anything is written, then applies them as one version.
 * 4. Anthropic is connected through Models with the round's key (and workspace
 *    ID for an identity-linked key); the agent proposes typed operations for
 *    the frame, nothing applies until they are accepted, and the history then
 *    names the agent's version.
 * 5. Check states each validation result in words; PNG and SVG exports record
 *    their version and hash; **Hand to Build** puts the handoff document in
 *    Build's composer, and nothing is written to any repository.
 *
 * Needs `RAIKER_LIVE_ANTHROPIC_KEY` and, for an identity-linked key,
 * `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`. No key is written into this file.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-19-dw-design-documents");
const TITLE = `Launch post ${Date.now()}`;

async function openDocuments(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/design?view=documents`);
  await expect(page.getByTestId("design-documents")).toBeVisible({ timeout: 30_000 });
}

async function openDesign(page: Page): Promise<void> {
  await openDocuments(page);
  await page.getByRole("button", { name: new RegExp(TITLE) }).click();
  await expect(page.getByRole("application", { name: /Canvas: Frame 1/ })).toBeVisible({ timeout: 30_000 });
}

async function connectAnthropic(page: Page): Promise<void> {
  expect(KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  }
  await keepModelAvailable(page, card, MODEL);
}

test("a design is layers that are edited, undone and redone as versions", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDocuments(page);
  await capture(page, join(SHOTS, "01-documents-empty.png"));
  await page.getByPlaceholder(/Name it/).fill(TITLE);
  await page.getByRole("button", { name: "Create" }).click();
  const canvas = page.getByRole("application", { name: /Canvas: Frame 1/ });
  await expect(canvas).toBeVisible({ timeout: 30_000 });

  const layers = page.getByRole("group", { name: "Add a layer" });
  await layers.getByRole("button", { name: "Rectangle" }).click();
  await expect(page.getByText("v2")).toBeVisible();
  await layers.getByRole("button", { name: "Text" }).click();
  await expect(page.getByText("v3")).toBeVisible();

  const properties = page.getByRole("region", { name: "Layer properties" });
  await properties.getByLabel("Text").fill("Launch day — 21 October");
  await properties.getByLabel("Text").blur();
  await expect(page.getByText("v4")).toBeVisible();
  await expect(canvas).toContainText("Launch day — 21 October");

  await canvas.focus();
  await page.keyboard.press("Shift+ArrowUp");
  await expect(page.getByText("v5")).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("v6")).toBeVisible();
  await page.getByRole("button", { name: "Redo" }).click();
  await expect(page.getByText("v7")).toBeVisible();
  await capture(page, join(SHOTS, "02-canvas-layers-inspector.png"));

  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByRole("region", { name: "History" })).toContainText("Redid");
  await expect(page.getByRole("region", { name: "History" })).toContainText("Undid");
  await capture(page, join(SHOTS, "03-history.png"));
});

test("a responsive variant is linked to its source frame", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  await page.getByLabel("Responsive variant as").selectOption({ label: "Mobile screen" });
  await page.getByRole("button", { name: "Make variant" }).click();
  await expect(page.getByRole("application", { name: /Mobile screen/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("complementary", { name: "Frames and layers" })).toContainText("variant of Frame 1");
  await capture(page, join(SHOTS, "04-mobile-variant.png"));
});

test("a design system is previewed before it changes anything", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  await page.getByRole("tab", { name: "System" }).click();
  const create = page.getByRole("region", { name: "New design system" });
  await create.getByLabel("Name", { exact: true }).fill("Acme");
  await create.getByLabel(/^Colours/).fill("primary=#1144aa\nink=#101828\nsurface=#ffffff");
  await create.getByRole("button", { name: "Save system" }).click();
  const choose = page.getByRole("region", { name: "Design system", exact: true });
  await expect(choose.getByLabel("Design system to use")).toHaveValue(/dsys_/);
  await choose.getByRole("button", { name: "Preview the change" }).click();
  await expect(choose.getByRole("status")).toBeVisible();
  await capture(page, join(SHOTS, "05-system-preview.png"));
  const before = await page.locator(".version").textContent();
  await choose.getByRole("button", { name: "Apply to this design" }).click();
  await expect(choose).toContainText("This design uses Acme v1");
  expect(await page.locator(".version").textContent()).not.toBe(before);
});

test("the agent proposes typed operations and nothing applies until accepted", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);
  await connectAnthropic(page);
  await openDesign(page);
  await page.getByRole("tab", { name: "Agent" }).click();
  const agent = page.getByRole("region", { name: "Design agent" });
  const picker = agent.getByLabel("Agent model");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  const option = picker.locator("option", { hasText: /Anthropic/ }).first();
  await picker.selectOption({ value: (await option.getAttribute("value")) ?? "" });
  await agent.getByLabel("Brief for the agent").fill(
    "Add a call-to-action button below the headline: a dark blue rectangle with the white text 'Join the launch'. Keep the existing layers.",
  );
  const version = await page.locator(".version").textContent();
  await agent.getByRole("button", { name: "Propose changes" }).click();
  const proposal = page.getByRole("region", { name: "Proposal" }).first();
  await expect(proposal).toBeVisible({ timeout: 240_000 });
  await expect(proposal.getByRole("button", { name: "Accept selected" })).toBeVisible();
  expect(await page.locator(".version").textContent()).toBe(version);
  await capture(page, join(SHOTS, "06-agent-proposal.png"));
  await proposal.getByRole("button", { name: "Accept selected" }).click();
  await expect(proposal).toContainText(/accepted/, { timeout: 60_000 });
  await expect(page.locator(".badge").first()).toHaveText("agent");
  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByRole("region", { name: "History" })).toContainText("Agent proposal accepted");
  await capture(page, join(SHOTS, "07-agent-accepted.png"));
});

test("checks, exports and the Build handoff say what they are", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  await page.getByRole("tab", { name: "Check" }).click();
  const checks = page.getByRole("region", { name: "Checks" });
  await expect(checks.locator(".outcome")).toBeVisible({ timeout: 30_000 });
  await expect(checks).toContainText("Text meets WCAG AA contrast");
  await capture(page, join(SHOTS, "08-checks.png"));

  await page.getByRole("tab", { name: "Export" }).click();
  const exporter = page.getByRole("region", { name: "Export" });
  await exporter.getByLabel("Format").selectOption("png");
  await exporter.getByRole("button", { name: "Export" }).click();
  await expect(exporter.getByRole("button", { name: /^PNG · v\d+/ })).toBeVisible({ timeout: 60_000 });
  await exporter.getByLabel("Format").selectOption("svg");
  await exporter.getByRole("button", { name: "Export" }).click();
  await expect(exporter.getByRole("button", { name: /^SVG · v\d+/ })).toBeVisible({ timeout: 60_000 });
  await expect(exporter).toContainText(/sha256 [0-9a-f]{12}/);
  const download = page.waitForEvent("download");
  await exporter.getByRole("button", { name: /^PNG · v\d+/ }).click();
  expect((await download).suggestedFilename()).toMatch(/^raiker-design-frame-1-v\d+\.png$/);

  const handoff = page.getByRole("region", { name: "Hand to Build" });
  await handoff.getByLabel("What it should become").fill("web/src/routes/Launch.svelte");
  await handoff.getByRole("button", { name: "Hand to Build" }).click();
  await expect(handoff.getByRole("status")).toContainText(/Design handoff Launch post \d+ v\d+\.md/);
  await capture(page, join(SHOTS, "09-export-and-handoff.png"));
  await handoff.getByRole("link", { name: "Open Build" }).click();
  await expect(page.getByText(/Design handoff Launch post \d+ v\d+\.md/).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "10-build-carries-handoff.png"));
});

test("the workspace reflows to a phone width", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsOwner(page, BASE);
  await openDesign(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await capture(page, join(SHOTS, "11-phone-width.png"));
});
