/**
 * VIS2-21 — the Work contract, read off the three running surfaces.
 *
 * The contract's claim is that Chat, Build and Design share every answer an
 * owner needs and differ in exactly one thing: what they are about. That is a
 * statement about three real pages, so it is checked by opening all three and
 * comparing what they declare — not by reading the module that declares it.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

const ROUTES: Record<string, string> = {
  chat: "#/new-chat",
  build: "#/build",
  design: "#/design",
};

test.describe.configure({ mode: "serial" });

test("every Work mode declares the contract, and no two claim the same object", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);

  const declared: Record<string, { object: string; density: string; gap: string }> = {};
  for (const [mode, route] of Object.entries(ROUTES)) {
    await page.goto(`${BASE}/${route}`);
    const shell = page.locator(`[data-work-surface="${mode}"]`);
    await expect(shell, `${mode} does not declare itself a Work surface`).toBeVisible({
      timeout: 30_000,
    });
    declared[mode] = await shell.evaluate((element) => ({
      object: element.getAttribute("data-primary-object") ?? "",
      density: element.getAttribute("data-density") ?? "",
      // The density has to reach the page as a real dimension, not as a label.
      gap: getComputedStyle(element).getPropertyValue("--surface-gap").trim(),
    }));
  }

  const objects = Object.values(declared).map((entry) => entry.object);
  expect(new Set(objects).size, "two Work modes claim the same object").toBe(3);
  const densities = Object.values(declared).map((entry) => entry.density);
  expect(new Set(densities).size, "two Work modes pack the same way").toBe(3);
  const gaps = Object.values(declared).map((entry) => entry.gap);
  expect(gaps.every((gap) => gap !== ""), "a declared density reached the page as nothing").toBe(
    true,
  );
  expect(new Set(gaps).size, "the three densities resolve to the same spacing").toBe(3);
});

test("the shared half of the contract is answered on every Work surface", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);

  for (const [mode, route] of Object.entries(ROUTES)) {
    await page.goto(`${BASE}/${route}`);
    await expect(page.locator(`[data-work-surface="${mode}"]`)).toBeVisible({ timeout: 30_000 });

    // Attachments and the rest of the turn's additions, in the same place …
    await expect(
      page.getByRole("button", { name: "Add to this turn" }),
      `${mode} has no way to add to the turn`,
    ).toBeVisible();
    // … the same Tools menu …
    await expect(
      page.getByRole("button", { name: /^Tools/ }),
      `${mode} does not offer the shared tools`,
    ).toBeVisible();
    // … and the model that will answer, named on the surface itself.
    await expect(
      page.locator(`[data-work-surface="${mode}"]`).getByText(/model|Not selected|connect one/i).first(),
      `${mode} does not say which model will answer`,
    ).toBeVisible();
    await capture(page, `${SHOTS}/vis2-21-${mode}-surface.png`);
  }
});
