/** Read-only live review of the shared icon, slider, switch and composer shape. */
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const root = resolve(import.meta.dirname, "../../output/playwright/2026-11-06-ui-scale");

test("RT-UI-SCALE-01: Chat, Build and Design retain the owner's preferred rounded-card shape", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  mkdirSync(root, { recursive: true });

  for (const viewport of [
    { width: 1440, height: 900, theme: "light" },
    { width: 1280, height: 800, theme: "dark" },
    { width: 390, height: 844, theme: "light" },
  ] as const) {
    await page.setViewportSize(viewport);
    await page.evaluate(theme => {
      localStorage.setItem("raiker.theme", theme);
      document.documentElement.dataset.theme = theme;
    }, viewport.theme);

    for (const surface of [
      { route: "new-chat", label: "Message composer", file: "chat" },
      { route: "build", label: "Build composer", file: "build" },
      { route: "design", label: "Image composer", file: "design" },
    ]) {
      await page.goto(`${BASE}/#/${surface.route}`);
      const composer = page.getByRole("group", { name: surface.label });
      const card = composer;
      const prompt = composer.getByRole("textbox").first();
      await expect(card).toBeVisible({ timeout: 30_000 });
      await expect(page.locator("html")).toHaveAttribute("data-theme", viewport.theme);
      const firstIconSize = Number(await card.locator("svg").first().getAttribute("width"));
      expect(firstIconSize).toBeGreaterThan(14);
      const sendButton = card.locator(".send").first();
      const sendSize = await sendButton.evaluate(element => {
        const box = element.getBoundingClientRect();
        return { width: box.width, height: box.height };
      });
      expect(sendSize).toEqual(viewport.width <= 1023 ? { width: 44, height: 44 } : { width: 40, height: 40 });
      await prompt.evaluate(element => element.blur());
      const idleRadius = await card.evaluate(element => getComputedStyle(element).borderRadius);
      expect(idleRadius).toContain(viewport.width <= 1023 ? "16px" : "20px");
      await capture(page, `${root}/${viewport.width}-${viewport.theme}-${surface.file}-idle.png`);

      await prompt.focus();
      await expect(prompt).toBeFocused();
      await prompt.fill("A draft that remains an active work surface");
      await prompt.evaluate(element => element.blur());
      const draftRadius = await card.evaluate(element => getComputedStyle(element).borderRadius);
      expect(draftRadius, `${surface.file} draft after blur`).toContain(viewport.width <= 1023 ? "16px" : "20px");
      await capture(page, `${root}/${viewport.width}-${viewport.theme}-${surface.file}-draft.png`);
    }
  }
});

test("RT-UI-SCALE-02: Privacy switch and Brain sliders have the larger shared control scale", async ({ page }) => {
  test.setTimeout(90_000);
  await signInAsOwner(page, BASE);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.evaluate(() => {
    localStorage.setItem("raiker.theme", "dark");
    document.documentElement.dataset.theme = "dark";
  });

  await page.goto(`${BASE}/#/settings?tab=privacy`);
  const privacySwitch = page.getByRole("switch", { name: "Keep the model's working with the turn" });
  await expect(privacySwitch).toBeVisible();
  const switchSize = await privacySwitch.evaluate(element => {
    const box = element.getBoundingClientRect();
    return { width: box.width, height: box.height };
  });
  expect(switchSize).toEqual({ width: 48, height: 28 });
  await capture(page, `${root}/1280-dark-privacy-switch.png`);

  await page.goto(`${BASE}/#/memory?tab=map`);
  await page.getByRole("button", { name: "Graph settings" }).click();
  const displayDisclosure = page.locator('aside[aria-label="Graph settings"] details').filter({ hasText: "Display" }).first();
  await displayDisclosure.evaluate(element => { (element as HTMLDetailsElement).open = true; });
  const slider = page.locator('aside[aria-label="Graph settings"] input[type="range"]:visible').first();
  await expect(slider).toBeVisible();
  const sliderSize = await slider.evaluate(element => {
    const box = element.getBoundingClientRect();
    return { height: box.height, minWidth: getComputedStyle(element).minWidth };
  });
  expect(sliderSize).toEqual({ height: 28, minWidth: "112px" });
  await capture(page, `${root}/1280-dark-brain-sliders.png`);
});
