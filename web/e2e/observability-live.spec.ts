import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

// This spec used to drive `127.0.0.1:5174` — a Vite dev server, not the
// `raiker-web` every other live spec runs against. It had drifted with nothing
// to catch it, because its own sign-in was one of the twenty-seven copies
// BUG-248 is about: a spec that carries its own base and its own credential is
// a spec nobody re-reads.
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";

test("live Observability and Sessions visual review", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe`);
  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Sessions" })).toBeVisible();
  await expect(page.getByText("Reading runtime status…")).toBeHidden({ timeout: 15_000 });
  await capture(page, "../../docs/plans/screenshots/working/observability-overview.png");
  await page.getByRole("tab", { name: "Sessions" }).click();
  await expect(page.getByText(/Every conversation with the runtime/)).toBeVisible();
  if (await page.locator(".layout").count()) {
    await expect(page.locator(".layout")).toHaveCSS("display", "flex");
  } else {
    await expect(page.getByText("No sessions yet")).toBeVisible();
  }
  await capture(page, "../../docs/plans/screenshots/working/observability-sessions.png");
  expect(consoleErrors).toEqual([]);
});
