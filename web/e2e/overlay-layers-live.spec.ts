/**
 * The overlay ladder, checked where stacking actually happens.
 *
 * A z-index is only ever true in a browser: a value that reads correctly in a
 * stylesheet still loses to a sibling in another stacking context. The rubric
 * test pins that every surface *names* a layer; this one opens the surfaces and
 * reads the computed value back, so the ladder is checked as the browser
 * resolves it rather than as the source claims it.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

test.describe.configure({ mode: "serial" });

test("the layer vocabulary resolves in the browser, in the order it claims", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);

  const ladder = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    const names = [
      "--z-raised", "--z-popover", "--z-popover-panel", "--z-docked",
      "--z-panel", "--z-scrim", "--z-modal", "--z-palette", "--z-alert",
    ];
    return names.map((name) => [name, Number(style.getPropertyValue(name).trim())] as const);
  });

  // Every layer is declared …
  for (const [name, value] of ladder) {
    expect(Number.isFinite(value), `${name} is not declared as a number`).toBe(true);
  }
  // … and the ladder rises, which is the whole claim: a menu can never cover a
  // modal, and nothing can cover the control that stops a running turn.
  const values = ladder.map(([, value]) => value);
  expect(values).toEqual([...values].sort((a, b) => a - b));
  const layer = Object.fromEntries(ladder);
  expect(layer["--z-modal"]).toBe(layer["--z-scrim"] + 1);
  expect(layer["--z-popover-panel"]).toBe(layer["--z-popover"] + 1);
  expect(Math.max(...values)).toBe(layer["--z-alert"]);
});

test("an open menu names its layer rather than a number of its own", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);

  const add = page.getByRole("button", { name: "Add to this turn" });
  await expect(add).toBeVisible({ timeout: 30_000 });
  await add.click();

  const menu = page.getByRole("menu").first();
  await expect(menu).toBeVisible();
  const [menuZ, popoverZ] = await page.evaluate(() => {
    const element = document.querySelector('[role="menu"]') as HTMLElement;
    return [
      Number(getComputedStyle(element).zIndex),
      Number(getComputedStyle(document.documentElement).getPropertyValue("--z-popover").trim()),
    ];
  });
  expect(menuZ).toBe(popoverZ);

  await capture(page, `${SHOTS}/vis2-17-composer-menu-layer.png`, menu);
});
