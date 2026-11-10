/** Owner-requested borderless secondary composer controls; real UI, no sends. */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const surfaces = [
  { name: "home", route: "#/home", root: ".home-composer" },
  { name: "chat", route: "#/new-chat", root: ".chat-composer" },
  { name: "build", route: "#/build", root: ".composer-build" },
  { name: "design", route: "#/design", root: ".design-composer" },
  { name: "tasks", route: "#/tasks", root: ".composer-task" },
  { name: "quick-entry", route: "#/quick-entry", root: ".quick-entry" },
];
const controls = ".action-trigger, .mode-trigger, .profile > .chip, .model-trigger, .voice-button, .approval-trigger, .composer-attach > .round-btn, .bar-select, .talk-button, .composer-control, .model-scope, .send-to select";
const transparent = /^(transparent|rgba\([^)]*,\s*0\))$/;

for (const width of [1440, 390]) {
  test(`composer secondary controls are quiet and usable at ${width}px`, async ({ page }) => {
    test.setTimeout(240_000);
    page.setDefaultTimeout(30_000);
    await page.setViewportSize({ width, height: 1000 });
    await signInAsOwner(page, BASE);
    let submissions = 0;
    page.on("request", r => {
      if (r.method() === "POST" && /^\/api\/(prompts|tasks|images\/generate)/.test(new URL(r.url()).pathname)) submissions++;
    });
    for (const surface of surfaces) {
      await page.goto(`${BASE}/${surface.route}`);
      const root = page.locator(surface.root);
      await expect(root).toBeVisible();
      await page.mouse.move(0, 0);
      const styles = await root.locator(controls).evaluateAll(elements => elements.filter(el => el.getClientRects().length > 0).map(el => {
        const style = getComputedStyle(el);
        return { name: el.getAttribute("aria-label") || el.getAttribute("title") || el.textContent?.trim(), border: style.borderColor, width: style.borderWidth, background: style.backgroundColor };
      }));
      expect(styles.length, surface.name).toBeGreaterThan(0);
      for (const style of styles) {
        expect.soft(style.width === "0px" || transparent.test(style.border), `${surface.name}: ${style.name} border`).toBe(true);
        expect.soft(style.background, `${surface.name}: ${style.name} background`).toMatch(transparent);
      }
      await expect(root.locator('button[type="submit"]')).toBeVisible();
      for (const trigger of await root.locator(".action-trigger:not(:disabled), .profile > .chip:not(:disabled), .model-trigger:not(:disabled), .mode-trigger:not(:disabled)").all()) {
        if (!(await trigger.isVisible())) continue;
        await trigger.click();
        await expect(trigger).toHaveAttribute("aria-expanded", "true");
        await expect(page.getByRole("menu").or(page.getByRole("dialog")).last()).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(trigger).toHaveAttribute("aria-expanded", "false");
        await expect(trigger).toBeFocused();
      }
      const input = root.getByRole("textbox").first();
      await input.focus();
      await page.keyboard.press("Tab");
      expect(await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return false;
        const style = getComputedStyle(el);
        return (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== "none";
      }), `${surface.name}: keyboard focus stays visible`).toBe(true);
      await input.focus();
      await page.mouse.move(0, 0);
      await expect.poll(() => root.locator(controls).evaluateAll(elements => elements
        .filter(el => el.getClientRects().length > 0 && !el.matches('.active, .skip-mode, [aria-expanded="true"]'))
        .every(el => getComputedStyle(el).backgroundColor === "rgba(0, 0, 0, 0)")),
      { message: `${surface.name}: hover feedback clears before the resting-state capture` }).toBe(true);
      await capture(page, `../../output/playwright/composer-borderless/${width}-${surface.name}.png`);
      expect.soft(await root.evaluate(el => el.scrollWidth <= el.clientWidth), `${surface.name}: no composer overflow`).toBe(true);
    }
    expect(submissions).toBe(0);
  });
}
