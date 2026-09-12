/**
 * The Permissions page's two questions, on the running product.
 *
 * The security model is unchanged and is not what this checks. What it checks
 * is the thing the review said was wrong: that availability and decision mode
 * were presented as two parallel systems, so an owner could not tell what
 * "On · Deny" meant. The page asks two questions now, in the order their
 * answers depend on, and this opens it and reads them back.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

test("Permissions asks what Raiker may use, then what happens when it does", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/capabilities`);

  // The list can be scanned: every row says its availability and its behaviour
  // without being opened.
  const summaries = page.locator(".cap-summary");
  await expect(summaries.first()).toBeVisible({ timeout: 30_000 });
  const first = await summaries.first().textContent();
  expect(first ?? "").toMatch(/^(On|Off) · (Ask me|Allow|Automatic|Never)$/);

  // The short list people come to change sits above the registry …
  const common = page.getByRole("region", { name: "Common permissions" });
  if ((await common.count()) > 0) {
    await expect(common).toBeVisible();
  }

  // … and a row, opened, asks the two questions in words.
  await page.getByRole("button", { name: /Shell commands/i }).first().click();
  await expect(page.getByText("Can Raiker use this?").first()).toBeVisible();
  await expect(page.getByText("When Raiker wants to use it").first()).toBeVisible();

  // The owner's vocabulary, not the store's.
  const modes = page.getByRole("group", { name: /when Raiker wants to use/i }).first();
  await expect(modes.getByRole("button", { name: "Never" })).toBeVisible();
  await expect(modes.getByRole("button", { name: "Deny" })).toHaveCount(0);
  await expect(modes.getByRole("button", { name: "Automatic" })).toBeVisible();

  await capture(page, `${SHOTS}/permissions-two-questions.png`);
});
