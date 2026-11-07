/** QUI-C04 composer control deck (2026-11-07) against a running host.
 *
 * Real UI writes: the send-key setting is saved through Settings, files are
 * uploaded to the host's governed store, and turns are answered by the hosted
 * model connected beforehand through Models. Nothing is seeded or mocked.
 */
import { expect as baseExpect, test, type Page } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";

const expect = baseExpect.configure({ timeout: 30_000 });
const SHOTS = "../../output/playwright/2026-11-07-composer-control-deck";
test.describe.configure({ mode: "serial", timeout: 300_000 });

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
});

async function newChat(page: Page) {
  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("group", { name: "Message composer", exact: true });
  await expect(composer).toBeVisible({ timeout: 60_000 });
  return composer;
}

async function openAttach(composer: ReturnType<Page["getByRole"]>) {
  await composer.getByRole("button", { name: "Add to this turn", exact: true }).click();
  await composer.page().getByRole("menuitem", { name: /^Upload a file/ }).click();
}

async function setSendKey(page: Page, value: "enter" | "mod_enter", from: "enter" | "mod_enter") {
  // Read the stored value first: before it loads the select shows the default.
  const read = page.waitForResponse((r) => r.url().endsWith("/api/settings") && r.request().method() === "GET");
  await page.goto(`${BASE}/#/settings?tab=personalisation`);
  await read;
  const select = page.getByRole("combobox", { name: "Send with", exact: true });
  await expect(select).toBeVisible();
  await expect(select).toHaveValue(from);
  await select.selectOption(value);
  const saved = page.waitForResponse((r) => r.url().endsWith("/api/settings") && r.request().method() === "PUT");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  expect((await saved).status()).toBe(200);
  // Leave only once the page has settled the save, as a person would.
  await expect(page.getByText("All changes saved.", { exact: true })).toBeVisible();
}

test("RT-COMPOSER-01: the glass capsule floats over Chat, Build and Design in both themes", async ({ page }) => {
  await newChat(page);
  for (const [route, label, name] of [
    ["new-chat", "Message composer", "chat"],
    ["build", "Build composer", "build"],
    ["design", "Image composer", "design"],
  ] as const) {
    for (const theme of ["light", "dark"] as const) {
      await page.goto(`${BASE}/#/${route}`);
      await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
      const card = page.getByRole("group", { name: label, exact: true });
      await expect(card).toBeVisible({ timeout: 60_000 });
      const style = await card.evaluate((el) => {
        // The glass is a layer behind the content, so fixed menus inside the
        // card still position against the viewport.
        const s = getComputedStyle(el, "::before");
        return {
          blur: s.backdropFilter || s.getPropertyValue("-webkit-backdrop-filter"),
          bg: s.backgroundColor,
          cardFilter: getComputedStyle(el).backdropFilter,
        };
      });
      expect(style.blur).toContain("blur");
      expect(style.cardFilter === "" || style.cardFilter === "none").toBe(true);
      // Translucent: the surface is mixed with transparency, never fully opaque.
      expect(style.bg).toMatch(/rgba?\(.*\)|color\(srgb .* \/ 0\.\d+\)|oklab|color-mix/);
      expect(style.bg).not.toMatch(/^rgb\(\d+, \d+, \d+\)$/);
      await capture(page, `${SHOTS}/01-${name}-${theme}.png`);
    }
  }
});

test("RT-COMPOSER-02: the input grows to five lines, then scrolls", async ({ page }) => {
  const composer = await newChat(page);
  const box = composer.getByRole("textbox").first();
  await box.fill(Array.from({ length: 12 }, (_, i) => `Line ${i + 1} of a long system prompt`).join("\n"));
  // Five lines (owner decision, 2026-11-07), measured from the input's own line height.
  const { height, line, padding, scrolls } = await box.evaluate((el) => {
    const style = getComputedStyle(el);
    return {
      height: el.getBoundingClientRect().height,
      line: parseFloat(style.lineHeight),
      padding: parseFloat(style.paddingTop) + parseFloat(style.paddingBottom),
      scrolls: el.scrollHeight > el.clientHeight,
    };
  });
  expect(Math.abs(height - (line * 5 + padding))).toBeLessThanOrEqual(1);
  expect(scrolls).toBe(true);
  await capture(page, `${SHOTS}/02-long-prompt.png`);
  await box.fill("");
});

test("RT-COMPOSER-03: Ctrl + Enter sends when chosen; Enter only adds a line", async ({ page }) => {
  await setSendKey(page, "mod_enter", "enter");
  const composer = await newChat(page);
  const box = composer.getByRole("textbox").first();
  await expect(box).toHaveAttribute("title", /Ctrl \+ Enter to send · Enter for a new line/);
  await box.fill("What is 20 + 22?");
  await box.press("Enter");
  await box.type("Reply only with the number. Do not use tools.");
  await expect(box).toHaveValue("What is 20 + 22?\nReply only with the number. Do not use tools.");
  const sent = page.waitForRequest((r) => r.url().endsWith("/api/prompts/stream") && r.method() === "POST");
  await box.press("Control+Enter");
  expect((await sent).postDataJSON().text).toContain("20 + 22");
  await expect(page.getByRole("button", { name: "Copy response", exact: true }).last()).toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".message-group-raiker").last()).toContainText("42");
  await setSendKey(page, "enter", "mod_enter");
});

test("RT-COMPOSER-04: several files at once, JSON accepted, chips show size and ≈ tokens", async ({ page }) => {
  const composer = await newChat(page);
  await openAttach(composer);
  const input = page.getByLabel("Upload document", { exact: true });
  await input.setInputFiles([
    { name: "metrics.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify({ revenue: [12, 15, 19], region: "EU" }, null, 2).repeat(40)) },
    { name: "table.csv", mimeType: "text/csv", buffer: Buffer.from("month,revenue\nJan,12\nFeb,15\nMar,19\n".repeat(60)) },
  ]);
  await expect(page.getByRole("button", { name: "Remove attachment metrics.json", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove attachment table.csv", exact: true })).toBeVisible();
  await expect(composer.getByText(/^JSON · \d+ KB · ≈ [\d.]+k? tokens$/)).toBeVisible();
  await expect(composer.getByText(/^CSV · \d+ KB · ≈ [\d.]+k? tokens$/)).toBeVisible();
  await capture(page, `${SHOTS}/04-chips.png`, composer);
  const box = composer.getByRole("textbox").first();
  await box.fill("From metrics.json, what is the region value? Reply with one word. Do not use tools.");
  await box.press("Enter");
  await expect(page.getByRole("button", { name: "Copy response", exact: true }).last()).toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".message-group-raiker").last()).toContainText("EU");
});

test("RT-COMPOSER-05: dragging files over the composer shows the drop zone", async ({ page }) => {
  const composer = await newChat(page);
  const transfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(["hello"], "dragged.txt", { type: "text/plain" }));
    return data;
  });
  await composer.dispatchEvent("dragenter", { dataTransfer: transfer });
  await composer.dispatchEvent("dragover", { dataTransfer: transfer });
  await expect(composer.getByText("Drop documents, data files or images here to add them as context", { exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/05-drop-zone.png`, composer);
  await composer.dispatchEvent("drop", { dataTransfer: transfer });
  await expect(page.getByRole("button", { name: "Remove attachment dragged.txt", exact: true })).toBeVisible();
});

test("RT-COMPOSER-06: a prompt near the context window turns the card amber", async ({ page }) => {
  const composer = await newChat(page);
  await openAttach(composer);
  // ≈ 175k tokens of text against Haiku's 200k window.
  await page.getByLabel("Upload document", { exact: true }).setInputFiles({
    name: "large-log.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("2026-11-07 INFO request served in 12 ms\n".repeat(17_500)),
  });
  await expect(page.getByRole("button", { name: "Remove attachment large-log.txt", exact: true })).toBeVisible({ timeout: 60_000 });
  const warning = composer.getByText(/With what you are adding, this prompt is about \d+% of the model's context window/);
  await expect(warning).toBeVisible();
  await expect(composer).toHaveClass(/context-warn/);
  await capture(page, `${SHOTS}/06-context-warning.png`, composer);
  await page.getByRole("button", { name: "Remove attachment large-log.txt", exact: true }).click();
  await expect(warning).toHaveCount(0);
});

test("RT-COMPOSER-07: Add to prompt pins an earlier answer and sends it as quoted context", async ({ page }) => {
  const composer = await newChat(page);
  const box = composer.getByRole("textbox").first();
  await box.fill("Name three primary colours, comma separated, nothing else. Do not use tools.");
  await box.press("Enter");
  await expect(page.getByRole("button", { name: "Copy response", exact: true }).last()).toBeVisible({ timeout: 180_000 });
  await page.getByRole("button", { name: "Add answer 1 to the prompt", exact: true }).click();
  await expect(composer.getByText("Answer 1", { exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/07-pinned-answer.png`, composer);
  await box.fill("How many colours are in the quoted answer? Reply only with the number. Do not use tools.");
  const sent = page.waitForRequest((r) => r.url().endsWith("/api/prompts/stream") && r.method() === "POST");
  await box.press("Enter");
  expect((await sent).postDataJSON().text).toMatch(/^Context from answer 1 in this conversation:\n> /);
  await expect(page.getByRole("button", { name: "Copy response", exact: true })).toHaveCount(2, { timeout: 180_000 });
  await expect(page.locator(".message-group-raiker").last()).toContainText("3");
  await expect(composer.getByText("Answer 1", { exact: true })).toHaveCount(0);
});

test("RT-COMPOSER-08: Build shows dictation beside Run, as Chat and Design do", async ({ page }) => {
  for (const [route, label] of [["build", "Build composer"], ["new-chat", "Message composer"], ["design", "Image composer"]] as const) {
    await page.goto(`${BASE}/#/${route}`);
    const composer = page.getByRole("group", { name: label, exact: true });
    await expect(composer).toBeVisible({ timeout: 60_000 });
    await expect(composer.getByRole("button", { name: "Dictate", exact: true })).toBeVisible();
  }
  await page.goto(`${BASE}/#/build`);
  await capture(page, `${SHOTS}/08-build-dictation.png`, page.getByRole("group", { name: "Build composer", exact: true }));
});
