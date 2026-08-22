/**
 * Every page, at every width the app claims to support, against a real instance.
 *
 * The three failures this is built to catch are the ones a per-feature spec
 * never sees, because each of them is a property of the *page* rather than of
 * the feature that changed:
 *
 * 1. **Horizontal overflow.** A table, a code block or a long identifier that
 *    pushes the document sideways. At 390px it makes a page unusable, and it is
 *    invisible at 1440px where most work is done.
 * 2. **A missing icon.** `Icon` renders a named sprite; a name that does not
 *    exist renders nothing and leaves a button with no visible affordance. An
 *    empty `<svg>` is the signature.
 * 3. **A control off its own screen.** The hub tab strips scroll, so the
 *    selected tab can be scrolled out of view — the page then shows one panel
 *    under a strip that appears to have another selected (FIXED-257).
 *
 * Signed in as the owner rather than creating a fresh account, because the
 * pages worth checking are the populated ones.
 *
 * **On the captures.** This writes every page at every width into
 * `docs/plans/screenshots/pages/`. What is *committed* is a deliberate subset —
 * every page at `mobile`, where layout actually breaks, plus all three widths of
 * the six Extensions tabs, which is the surface most rounds change. Running this
 * spec regenerates the complete set locally; the assertions above are the part
 * that has to hold, and they do not depend on which files are kept.
 */
import { expect, test } from "@playwright/test";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/pages";

const ROUTES = [
  ["workbench", "workbench"],
  ["chat", "new-chat"],
  ["build", "build"],
  ["search-chat", "search-chat"],
  ["tasks", "tasks"],
  ["projects", "projects"],
  ["memory", "memory"],
  ["brain", "brain"],
  ["approvals", "approvals"],
  ["permissions", "capabilities"],
  ["models", "models"],
  ["extensions-connectors", "extensions?tab=connectors"],
  ["extensions-mcp", "extensions?tab=mcp"],
  ["extensions-skills", "extensions?tab=skills"],
  ["extensions-hooks", "extensions?tab=hooks"],
  ["extensions-plugins", "extensions?tab=plugins"],
  ["extensions-channels", "extensions?tab=channels"],
  ["observe-overview", "observe?tab=overview"],
  ["observe-sessions", "observe?tab=sessions"],
  ["observe-activity", "observe?tab=activity"],
  ["observe-checkpoints", "observe?tab=checkpoints"],
  ["observe-diagnostics", "observe?tab=diagnostics"],
  ["observe-work", "observe?tab=work"],
  ["observe-notifications", "observe?tab=notifications"],
  ["guide", "guide"],
  ["settings", "settings"],
] as const;

const WIDTHS = [
  ["mobile", { width: 390, height: 844 }],
  ["tablet", { width: 834, height: 1112 }],
  ["desktop", { width: 1440, height: 1000 }],
] as const;

async function signIn(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill("Ithink@10");
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  const workbench = page.getByRole("heading", { name: "Welcome to your Work Dashboard" });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench).toBeVisible({ timeout: 30_000 });
}

async function settle(page: import("@playwright/test").Page) {
  await expect(page.locator("main#main")).toBeVisible();
  await page
    .waitForFunction(
      () =>
        ![...document.querySelectorAll("main#main *")].some((element) => {
          const node = element as HTMLElement;
          const visible = node.offsetWidth > 0 || node.offsetHeight > 0;
          return visible && /^(loading|reading|checking|verifying)\b/i.test(
            (node.textContent ?? "").trim(),
          );
        }),
      undefined,
      { timeout: 20_000 },
    )
    .catch(() => undefined);
  // Park the pointer in a corner before every capture. Playwright's virtual
  // mouse stays wherever the last click left it, which at 390px is over the
  // phone nav — so a screenshot taken without this shows a hover state no user
  // would be looking at, and the evidence misleads.
  await page.mouse.move(2, 2);
  await page.waitForTimeout(500);
}

test.describe.configure({ mode: "serial" });

for (const [label, viewport] of WIDTHS) {
  test(`every page fits, keeps its icons and its selected tab at ${label}`, async ({ page }) => {
    test.setTimeout(600_000);
    await page.setViewportSize(viewport);
    await signIn(page);

    const overflowing: string[] = [];
    const iconless: string[] = [];
    const offscreenTab: string[] = [];

    for (const [name, route] of ROUTES) {
      await page.goto(`${BASE}/#/${route}`);
      await settle(page);

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      // One pixel of slack: sub-pixel layout rounding is not a defect.
      if (overflow > 1) overflowing.push(`${name} (+${overflow}px)`);

      // An `Icon` whose name does not resolve renders an empty <svg>. It leaves a
      // button looking like a gap, which no other check would notice.
      const empty = await page.evaluate(
        () =>
          [...document.querySelectorAll("main#main svg, header svg, nav svg")].filter((svg) => {
            const node = svg as SVGElement;
            const visible = node.getBoundingClientRect().width > 0;
            return visible && node.children.length === 0;
          }).length,
      );
      if (empty > 0) iconless.push(`${name} (${empty})`);

      const selected = page.locator('[role="tab"][aria-selected="true"]');
      if ((await selected.count()) > 0) {
        const inView = await selected.first().evaluate((node) => {
          const box = node.getBoundingClientRect();
          return box.left >= -1 && box.right <= window.innerWidth + 1;
        });
        if (!inView) offscreenTab.push(name);
      }

      await page.screenshot({ path: `${SHOTS}/${label}-${name}.png`, fullPage: true });
    }

    expect(overflowing, `pages overflowing horizontally at ${label}`).toEqual([]);
    expect(iconless, `pages rendering an icon with no glyph at ${label}`).toEqual([]);
    expect(offscreenTab, `pages whose selected tab is off screen at ${label}`).toEqual([]);
  });
}
