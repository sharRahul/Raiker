/**
 * BUG-348 — the second Design round on a running host.
 *
 * On a fresh `raiker-web` (`scripts/reset_live_workspace.py`):
 *
 * 1. Layers are dragged, resized and rotated with the pointer; a drag snaps to
 *    the frame's centre and draws the guide it matched; each gesture is one
 *    version, and a locked layer does not move.
 * 2. Shift-click selects three layers; align and distribute line them up as one
 *    version each; the three are grouped.
 * 3. The owner's own picture is imported (no provider) and placed; Images names
 *    it as imported.
 * 4. The group becomes a component, is placed again, edited, and updated back
 *    from its component; a note is added, pinned and resolved.
 * 5. A tokens file and a picture's colours fill a new design system; a vector
 *    PDF export records its version and hash and downloads as a PDF.
 * 6. With Anthropic connected through Models, a proposal whose host is
 *    restarted while the model is asked reads as *outcome unknown* afterwards,
 *    and a normal proposal still completes. Needs `RAIKER_LIVE_ANTHROPIC_KEY`
 *    (and `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID` for an identity-linked key) and,
 *    for the restart, `RAIKER_LIVE_RESTART_COMMAND`. No key is written here.
 */
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { deflateSync } from "node:zlib";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const RESTART = process.env.RAIKER_LIVE_RESTART_COMMAND ?? "";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-20-dw-design-round-two");
const TITLE = `Round two ${Date.now()}`;

/** A small solid PNG, built here so the round needs no fixture file. */
function png(width: number, height: number, rgb: [number, number, number]): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buffer: Buffer) => {
    let c = 0xffffffff;
    for (const byte of buffer) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([length, body, sum]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8);
  const rows = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) rows.set(rgb, y * (width * 3 + 1) + 1 + x * 3);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function openDocuments(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/design?view=documents`);
  await expect(page.getByTestId("design-documents")).toBeVisible({ timeout: 30_000 });
}

async function openDesign(page: Page): Promise<void> {
  await openDocuments(page);
  await page.getByRole("button", { name: new RegExp(TITLE) }).click();
  await expect(page.getByRole("application", { name: /Canvas: Frame 1/ })).toBeVisible({ timeout: 30_000 });
}

async function version(page: Page): Promise<number> {
  return Number(((await page.locator(".version").textContent()) ?? "v0").slice(1));
}

async function waitVersion(page: Page, expected: number): Promise<void> {
  await expect(page.locator(".version")).toHaveText(`v${expected}`, { timeout: 30_000 });
}

async function centreOf(page: Page, selector: string): Promise<{ x: number; y: number }> {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`${selector} is not on screen`);
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

async function field(page: Page, label: string): Promise<number> {
  return Number(await page.getByRole("region", { name: "Layer properties" }).getByLabel(label, { exact: true }).inputValue());
}

test("layers are dragged, resized and rotated as one version per gesture", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDocuments(page);
  await page.getByPlaceholder(/Name it/).fill(TITLE);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("application", { name: /Canvas: Frame 1/ })).toBeVisible({ timeout: 30_000 });
  const adds = page.getByRole("group", { name: "Add a layer" });
  await adds.getByRole("button", { name: "Rectangle" }).click();
  await waitVersion(page, 2);

  // Move: a new rectangle sits at the frame's centre; drag it up and left, then
  // back near the centre, where it snaps and a guide is drawn.
  const start = await centreOf(page, '[data-layer="rect-1"] > rect.hit');
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x - 120, start.y - 80, { steps: 8 });
  await page.mouse.up();
  await waitVersion(page, 3);
  expect(await field(page, "X")).toBeLessThan(420);

  const moved = await centreOf(page, '[data-layer="rect-1"] > rect.hit');
  await page.mouse.move(moved.x, moved.y);
  await page.mouse.down();
  await page.mouse.move(start.x + 2, start.y + 1, { steps: 10 });
  await expect(page.locator("line.guide").first()).toBeAttached();
  await capture(page, join(SHOTS, "01-drag-snaps-to-centre.png"));
  await page.mouse.up();
  await waitVersion(page, 4);
  expect(await field(page, "X")).toBe(420); // (1080 − 240) / 2, snapped to the frame's centre

  // Resize from the bottom-right handle.
  const corner = await centreOf(page, '[data-handle="se"]');
  await page.mouse.move(corner.x, corner.y);
  await page.mouse.down();
  await page.mouse.move(corner.x + 60, corner.y + 30, { steps: 6 });
  await page.mouse.up();
  await waitVersion(page, 5);
  expect(await field(page, "W")).toBeGreaterThan(240);

  // Rotate with Shift held: snapped to 15°.
  const knob = await centreOf(page, '[data-handle="rotate"]');
  await page.keyboard.down("Shift");
  await page.mouse.move(knob.x, knob.y);
  await page.mouse.down();
  await page.mouse.move(knob.x + 150, knob.y + 40, { steps: 8 });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await waitVersion(page, 6);
  expect((await field(page, "Rotate")) % 15).toBe(0);
  expect(await field(page, "Rotate")).not.toBe(0);
  await capture(page, join(SHOTS, "02-resized-and-rotated.png"));

  // A locked layer does not move.
  await page.getByRole("button", { name: "Lock Rectangle" }).click();
  await waitVersion(page, 7);
  const locked = await centreOf(page, '[data-layer="rect-1"] > rect.hit');
  await page.mouse.move(locked.x, locked.y);
  await page.mouse.down();
  await page.mouse.move(locked.x + 100, locked.y + 100, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  expect(await version(page)).toBe(7);
  await page.getByRole("button", { name: "Unlock Rectangle" }).click();
  await waitVersion(page, 8);
  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByRole("region", { name: "History" })).toContainText("changed Rectangle");
});

test("three layers are selected, aligned, distributed and grouped", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  const adds = page.getByRole("group", { name: "Add a layer" });
  const before = await version(page);
  await adds.getByRole("button", { name: "Ellipse" }).click();
  await waitVersion(page, before + 1);
  await adds.getByRole("button", { name: "Text" }).click();
  await waitVersion(page, before + 2);
  const layers = page.getByRole("complementary", { name: "Frames and layers" });
  await layers.getByRole("button", { name: "rect Rectangle", exact: true }).click();
  await layers.getByRole("button", { name: "ellipse Ellipse", exact: true }).click({ modifiers: ["Shift"] });
  await layers.getByRole("button", { name: "text Text", exact: true }).click({ modifiers: ["Shift"] });
  const selected = page.getByRole("region", { name: "Selected layers" });
  await expect(selected).toContainText("3 layers selected");
  await selected.getByRole("button", { name: "Align left" }).click();
  await waitVersion(page, before + 3);
  await selected.getByRole("button", { name: "Distribute down" }).click();
  await waitVersion(page, before + 4);
  await capture(page, join(SHOTS, "03-three-selected-aligned.png"));
  await selected.getByRole("button", { name: "Group" }).click();
  await waitVersion(page, before + 5);
  await expect(layers.getByRole("button", { name: /group Group/ })).toBeVisible();
});

test("the owner's own picture is imported without a provider and placed", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  const before = await version(page);
  await page.getByRole("group", { name: "Add a layer" }).getByRole("button", { name: "Image" }).click();
  await page.locator('input[type="file"][accept^="image/"]').setInputFiles({
    name: "brand-logo.png",
    mimeType: "image/png",
    buffer: png(64, 32, [255, 102, 0]),
  });
  await waitVersion(page, before + 1);
  await expect(page.getByRole("region", { name: "Layer properties" })).toContainText("image");
  await capture(page, join(SHOTS, "04-imported-picture-placed.png"));
  await page.getByRole("tab", { name: "Images" }).click();
  const picture = page.getByRole("button", { name: "Open brand-logo.png on the canvas" }).first();
  await expect(picture).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Imported · 64x32/).first()).toBeVisible();
  await picture.click();
  await expect(page.getByText("No provider has seen it")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Imported").first()).toBeVisible();
  await capture(page, join(SHOTS, "05-images-names-it-imported.png"));
});

test("a component is placed, edited and updated back; a note is pinned and resolved", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  const layers = page.getByRole("complementary", { name: "Frames and layers" });
  await layers.getByRole("button", { name: /group Group/ }).click();
  const component = page.getByRole("region", { name: "Component" });
  await component.getByLabel("Name").fill("Feature card");
  let at = await version(page);
  await component.getByRole("button", { name: "Make component" }).click();
  await waitVersion(page, at + 1);
  await layers.getByRole("button", { name: "Place Feature card" }).click();
  await waitVersion(page, at + 2);
  await expect(component).toContainText("Placed from Feature card");
  await expect(component).toContainText("It matches the component");

  // Edit inside the instance, then update it back from the component.
  const instance = await page.locator(".layers .current").first().textContent();
  expect(instance).toContain("instance");
  await layers.getByRole("button", { name: /^ellipse / }).first().click(); // the instance is front-most
  await page.getByRole("region", { name: "Layer properties" }).getByLabel("W", { exact: true }).fill("320");
  await page.getByRole("region", { name: "Layer properties" }).getByLabel("W", { exact: true }).blur();
  await waitVersion(page, at + 3);
  await layers.getByRole("button", { name: /instance Feature card/ }).click();
  await expect(component).toContainText("It differs from the component now");
  await component.getByRole("button", { name: "Update from component" }).click();
  await waitVersion(page, at + 4);
  await expect(component).toContainText("It matches the component");
  await capture(page, join(SHOTS, "06-component-instance.png"));

  // A note on the instance.
  at = await version(page);
  const notes = page.getByRole("region", { name: "Notes" });
  await notes.getByLabel(/New note on/).fill("Swap the photo for the October launch shot");
  await notes.getByRole("button", { name: "Add note" }).click();
  await waitVersion(page, at + 1);
  await expect(page.locator(".note-pin").first()).toBeVisible();
  await capture(page, join(SHOTS, "07-note-pinned.png"));
  await notes.getByRole("button", { name: "Resolve" }).click();
  await waitVersion(page, at + 2);
  await expect(notes).toContainText("resolved");
});

test("a tokens file and a picture's colours fill a system; a vector PDF says what it is", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await openDesign(page);
  await page.getByRole("tab", { name: "System" }).click();
  const create = page.getByRole("region", { name: "New design system" });
  await create.getByLabel(/Import from a tokens file/).setInputFiles({
    name: "brand-tokens.css",
    mimeType: "text/css",
    buffer: Buffer.from(
      ":root { --color-primary: #1144aa; --ink: #101828; --font-body: 'Inter', sans-serif; --space-md: 16px; --shadow-sm: 0 1px 2px #000; }",
    ),
  });
  await expect(create.getByRole("status")).toContainText("Read 4 values from brand-tokens.css");
  await expect(create.getByRole("status")).toContainText("shadow-sm: not a colour, font or size");
  await expect(create.getByLabel(/^Colours/)).toHaveValue("primary=#1144aa\nink=#101828");
  await expect(create.getByLabel("Where it came from")).toHaveValue(/brand-tokens\.css \(sha256 [0-9a-f]{12}/);
  await capture(page, join(SHOTS, "08-tokens-imported.png"));
  await create.getByLabel("Picture to read colours from").selectOption({ label: "brand-logo.png" });
  await create.getByRole("button", { name: "Read colours" }).click();
  await expect(create.getByLabel(/^Colours/)).toHaveValue(/brand-1=#ff6600/);
  await create.getByRole("button", { name: "Save system" }).click();
  await expect(page.getByRole("region", { name: "Design system", exact: true }).getByLabel("Design system to use")).toHaveValue(/dsys_/);

  await page.getByRole("tab", { name: "Export" }).click();
  const exporter = page.getByRole("region", { name: "Export" });
  await exporter.getByLabel("Format").selectOption("vector_pdf");
  await exporter.getByRole("button", { name: "Export" }).click();
  const listed = exporter.getByRole("button", { name: /^PDF \(vector\) · v\d+/ });
  await expect(listed).toBeVisible({ timeout: 60_000 });
  await expect(exporter).toContainText(/sha256 [0-9a-f]{12}/);
  const download = page.waitForEvent("download");
  await listed.click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^raiker-design-frame-1-v\d+\.pdf$/);
  const path = await file.path();
  expect(readFileSync(path).subarray(0, 8).toString("latin1")).toBe("%PDF-1.4");
  await capture(page, join(SHOTS, "09-vector-pdf-export.png"));
});

async function connectAnthropic(page: Page): Promise<void> {
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

test("a proposal the host did not survive reads as outcome unknown; the next one completes", async ({ page }) => {
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
  const brief = "Add a short white caption 'Launching 21 October' at the bottom of the frame. Keep every other layer.";
  await agent.getByLabel("Brief for the agent").fill(brief);

  if (RESTART) {
    await agent.getByRole("button", { name: "Propose changes" }).click();
    await page.waitForTimeout(400);
    execSync(RESTART, { stdio: "inherit", timeout: 120_000 });
    // The browser session outlives the host process; sign in only if asked.
    await page.goto(`${BASE}/#/home`);
    const asked = await page.getByLabel("Username").isVisible({ timeout: 10_000 }).catch(() => false);
    if (asked) await signInAsOwner(page, BASE);
    await openDesign(page);
    await page.getByRole("tab", { name: "Agent" }).click();
    const lost = page.getByRole("region", { name: "Proposal" }).first();
    await expect(lost).toContainText("Outcome unknown", { timeout: 30_000 });
    await expect(lost).toContainText("whether the provider answered is not known");
    await capture(page, join(SHOTS, "10-proposal-outcome-unknown.png"));
    await lost.getByRole("button", { name: "Ask again with this brief" }).click();
    await expect(page.getByLabel("Brief for the agent")).toHaveValue(brief);
  } else {
    await agent.getByLabel("Brief for the agent").fill(brief);
  }
  await page.getByRole("region", { name: "Design agent" }).getByRole("button", { name: "Propose changes" }).click();
  const proposal = page.getByRole("region", { name: "Proposal" }).first();
  await expect(proposal).toContainText("Proposed", { timeout: 240_000 });
  await expect(proposal.getByRole("button", { name: "Accept selected" })).toBeVisible();
  await capture(page, join(SHOTS, "11-proposal-after-restart.png"));
  await proposal.getByRole("button", { name: "Accept selected" }).click();
  await expect(proposal).toContainText(/Accepted|Partly accepted/, { timeout: 60_000 });
});

test("the round-two controls reflow to a phone width", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsOwner(page, BASE);
  await openDesign(page);
  await page.getByRole("complementary", { name: "Frames and layers" }).getByRole("button", { name: /^rect / }).first().click();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await capture(page, join(SHOTS, "12-phone-width.png"));
});
