/**
 * VIS2-15 and VIS2-14 — the two claims that only a real browser can settle.
 *
 * VIS2-15 says a large monitor gives a *spatial* surface more room and gives
 * prose and controls nothing. That is a statement about computed widths at a
 * viewport size, so it is checked at 3840×2160 rather than argued from the
 * stylesheet.
 *
 * VIS2-14 says the two themes are composed separately without redesigning the
 * palette. The composition tokens are read back under each theme, and the
 * Design canvas — the surface the review names — is captured in both.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

test.describe.configure({ mode: "serial" });

test("a 4K display widens the canvas and leaves prose and controls alone", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);

  async function composition() {
    return page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      const read = (name: string) => style.getPropertyValue(name).trim();
      const button = document.querySelector("button");
      return {
        workspace: read("--page-workspace"),
        operational: read("--page-operational"),
        reading: read("--page-reading"),
        measure: read("--prose-measure"),
        body: read("--text-md"),
        space: read("--space-4"),
        buttonHeight: button ? getComputedStyle(button).minHeight : "",
      };
    });
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  const laptop = await composition();

  await page.setViewportSize({ width: 3840, height: 2160 });
  const display4k = await composition();

  // The canvases grow …
  expect(display4k.workspace).not.toBe(laptop.workspace);
  expect(display4k.operational).not.toBe(laptop.operational);
  // … and nothing an owner reads or presses does.
  expect(display4k.reading).toBe(laptop.reading);
  expect(display4k.measure).toBe(laptop.measure);
  expect(display4k.body).toBe(laptop.body);
  expect(display4k.space).toBe(laptop.space);
  expect(display4k.buttonHeight).toBe(laptop.buttonHeight);

  await page.goto(`${BASE}/#/observe`);
  await capture(page, `${SHOTS}/vis2-15-observe-4k.png`);
});

test("each theme composes elevation for its own ground", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.setViewportSize({ width: 1440, height: 1000 });

  async function optical(theme: "light" | "dark") {
    await page.evaluate((value) => {
      document.documentElement.setAttribute("data-theme", value);
    }, theme);
    return page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        edge: style.getPropertyValue("--elevation-edge").trim(),
        canvasEdge: style.getPropertyValue("--canvas-edge").trim(),
        canvasLift: style.getPropertyValue("--canvas-lift").trim(),
      };
    });
  }

  await page.goto(`${BASE}/#/design`);
  const light = await optical("light");
  await capture(page, `${SHOTS}/vis2-14-design-light.png`);
  const dark = await optical("dark");
  await capture(page, `${SHOTS}/vis2-14-design-dark.png`);

  // Same palette, different composition: every one of the three differs, and
  // the dark theme spends no shadow on a ground that cannot show one.
  expect(dark.edge).not.toBe(light.edge);
  expect(dark.canvasEdge).not.toBe(light.canvasEdge);
  expect(dark.canvasLift).not.toBe(light.canvasLift);
  expect(dark.canvasLift).toBe("none");
  expect(light.canvasLift).not.toBe("none");
});
