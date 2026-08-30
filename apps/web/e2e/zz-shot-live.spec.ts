import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
test("phone evidence for the sweep", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE, { user: "owner", password: "Guide-accuracy-1!" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/#/models`);
  await page.waitForTimeout(2500);
  await capture(page, `${SHOTS}/ui-sweep-models-phone.png`);
  await page.goto(`${BASE}/#/brain`);
  await page.waitForTimeout(6000);
  await capture(page, `${SHOTS}/ui-sweep-knowledge-map-phone.png`);
  expect(true).toBe(true);
});
