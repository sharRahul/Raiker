/**
 * Every destination the app has, photographed from a live instance, and every
 * one of them checked for a sideways bleed at four widths.
 *
 * The list is no longer written here. It is derived from the app's own nav
 * registry by `destinations.ts`, which says why: this file's own comment —
 * *"The sweep is only a sweep if it covers every tab the nav offers"* — was
 * written the last time the hand-copied list had drifted, and it had drifted
 * again. Two routes it swept no longer exist and twenty that exist were missing.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { DESTINATIONS, horizontalBleed, hubReachability, settled, WIDTHS } from "./destinations";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";

/** Wait for the routed view to have finished arriving, not merely to exist. */
async function settle(page: import("@playwright/test").Page): Promise<void> {
  await expect(page.locator("main#main")).toBeVisible();
  await page.waitForLoadState("networkidle");
  // `settled` is shared with the two width sweeps and the Build restore spec:
  // all four had their own copy, and all four read the composer's "Checking
  // this model — you can still send." as an unfinished load.
  await settled(page);
}

test("capture every application page from a live instance", async ({ page }) => {
  test.setTimeout(240_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  // The one console error a sweep may forgive, and the condition it has to meet
  // — see `hubReachability`. The panel has to be saying it, or this still fails.
  const hub = hubReachability(page);
  // The five-stage setup wizard is modal over a brand-new instance (FIXED-172),
  // so a sweep that does not finish it photographs the wizard once per
  // destination instead of the pages underneath. The shared sign-in does that as
  // part of arriving, from whichever stage the workspace resumes on.
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByRole("heading", { name: /Welcome (back|to your Work Dashboard)/ })).toBeVisible({
    timeout: 30_000,
  });

  for (const { route, name } of DESTINATIONS) {
    await page.goto(`${BASE}/#/${route}`);
    await settle(page);
    await page.waitForTimeout(name === "home" ? 10_000 : 1_000);
    if (name === "models-huggingface" && hub.refused()) {
      await expect(page.getByText("Hugging Face could not be reached")).toBeVisible();
    }
    // Found 2026-09-15. This wrote the page catalogue into
    // `docs/plans/screenshots/pages/`, which `docs/plans/README.md` describes
    // as *historical* evidence that "may intentionally contain obsolete
    // states", while `docs/screenshots/README.md` names exactly one generator
    // for the current catalogue — `ui-sweep-responsive-live` — and one place
    // for it. So two trees each claimed to be the page catalogue, the
    // historical one was the one being kept current, and the canonical one was
    // empty.
    //
    // This sweep is not that generator, so its captures belong with the run
    // rather than in either tree: the run directory is where evidence that is
    // about one execution goes.
    await capture(page, `../../output/playwright/pages/${name}.png`);
  }
  expect(hub.filter(consoleErrors)).toEqual([]);
});

/**
 * The width sweep that found FIXED-395's three mobile bleeds, kept as a guard
 * rather than as a thing somebody remembers to do.
 *
 * It asserts the property rather than a screenshot: nothing in the routed view
 * sticks out past the right edge unless a scroll container is clipping it on
 * purpose. That is what makes it re-runnable against a workspace that has been
 * worked in — the layout has to hold whatever the content is, which is the only
 * version of this check worth having.
 */
test("no destination bleeds sideways at any width", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);

  const bleeds: string[] = [];
  for (const size of WIDTHS) {
    await page.setViewportSize({ width: size.width, height: size.height });
    for (const { route } of DESTINATIONS) {
      await page.goto(`${BASE}/#/${route}`);
      await settle(page);
      for (const offender of await horizontalBleed(page)) {
        bleeds.push(`${size.label}px · #/${route} · ${offender}`);
      }
    }
  }
  expect(bleeds).toEqual([]);
});
