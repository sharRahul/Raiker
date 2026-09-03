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
 * 4. **A control too small to hit.** Every checkbox in the app was the user
 *    agent's own 13x13 box, on five routes, and the Hooks tab had set its own
 *    16px — so they were under WCAG 2.2's 24px minimum target and not even the
 *    same size as each other (FIXED-318). Nothing looked wrong; it had to be
 *    measured.
 *
 * Signed in as the owner rather than creating a fresh account, because the
 * pages worth checking are the populated ones.
 *
 * **On the captures.** This writes the complete current-state catalogue into
 * `docs/plans/screenshots/pages/`: 26 route/tab states crossed with light/dark
 * and mobile, 1080p, 4K, and 8K. Captures are viewport-only and their PNG
 * dimensions are asserted before they are accepted.
 */
import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";

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

const CAPTURES = [
  ["mobile", { width: 390, height: 844 }],
  ["1080p", { width: 1920, height: 1080 }],
  ["4k", { width: 3840, height: 2160 }],
  ["8k", { width: 7680, height: 4320 }],
] as const;
const selectedCaptures = new Set(process.env.RAIKER_SWEEP_CAPTURE?.split(",").map((name) => name.trim()).filter(Boolean));
const ACTIVE_CAPTURES = selectedCaptures.size > 0
  ? CAPTURES.filter(([name]) => selectedCaptures.has(name))
  : CAPTURES;
const selectedRoutes = new Set(process.env.RAIKER_SWEEP_ROUTE?.split(",").map((name) => name.trim()).filter(Boolean));
const ACTIVE_ROUTES = selectedRoutes.size > 0
  ? ROUTES.filter(([name]) => selectedRoutes.has(name))
  : ROUTES;
const THEMES = ["light", "dark"] as const;

/**
 * BUG-229 — sign in through the one shared helper.
 *
 * Every spec used to carry its own copy, and each copy encoded an assumption
 * about the *state* of the instance — usually the empty-workspace greeting —
 * that had nothing to do with what the spec asserts. A suite then passed on a
 * fresh instance and failed at its first step on a used one.
 */
async function signIn(page: import("@playwright/test").Page) {
  await signInAsOwner(page, BASE, { user: "Rahul", password: "Ithink@10" });
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

/**
 * BUG-267 — the console on a locked load.
 *
 * This is the one check the sweep below cannot make, because it signs in first.
 * The page asks who this browser is before it can render either the workspace or
 * the lock screen, and "nobody" is one of the two expected answers. Asking it of
 * a route that refuses made the browser write a failed request to the console on
 * every load — routine noise in the one place a real fault is meant to stand out.
 *
 * Asserted as "nothing was refused" rather than "the console was quiet", because
 * a browser cannot be told a 4xx was expected: it logs the request either way,
 * and the only way to keep the log clean is not to be refused.
 */
test("a locked load refuses nothing and logs nothing", async ({ page }) => {
  const problems: string[] = [];
  const refused: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(String(error)));
  page.on("response", (response) => {
    if (response.status() === 401) refused.push(`401 ${response.url()}`);
  });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByLabel("Username")).toBeEnabled({ timeout: 60_000 });
  expect(refused).toEqual([]);
  expect(problems).toEqual([]);
});

for (const [label, viewport] of ACTIVE_CAPTURES) {
  for (const theme of THEMES) {
  test(`every page fits at ${label} in ${theme}`, async ({ page }) => {
    test.setTimeout(900_000);
    await page.setViewportSize(viewport);
    await page.addInitScript((selectedTheme) => {
      localStorage.setItem("raiker.theme", selectedTheme);
    }, theme);
    await signIn(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    // The theme is applied from the stored override, not from a shell control:
    // the toggle moved to Settings -> Personalisation, and the top bar carries
    // no project selector either. Both absences are asserted here because they
    // are the shell contract, not an incidental layout detail.
    await expect(page.getByRole("button", { name: /^Theme: / })).toHaveCount(0);
    await expect(page.getByLabel("Active project")).toHaveCount(0);

    const overflowing: string[] = [];
    const iconless: string[] = [];
    const offscreenTab: string[] = [];
    const undersized: string[] = [];
    const consoleErrors: string[] = [];
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });

    for (const [name, route] of ACTIVE_ROUTES) {
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

      // FIXED-318 — the fourth page-level property, and the one that was
      // invisible to every other check here: a control too small to hit.
      // Checkboxes were the user agent's own 13x13 box on five routes, under
      // WCAG 2.2 SC 2.5.8's 24px minimum, and the Hooks tab had set its own
      // 16px — so they were not even the same size as each other.
      //
      // The floor is width-aware for the same reason the 44px shell-control
      // floor is: a precise pointer meets SC 2.5.8's spacing exception, a
      // finger does not. Below the shell's own 1024px breakpoint the minimum
      // is the full 24px; above it the requirement is that they are one size
      // rather than three, which is what the Hooks divergence actually was.
      const minTarget = viewport.width < 1024 ? 24 : 16;
      const sizes = await page.evaluate(
        () =>
          [
            ...new Set(
              [...document.querySelectorAll<HTMLElement>(
                'main#main input[type="checkbox"], main#main input[type="radio"]',
              )]
                .map((node) => node.getBoundingClientRect())
                .filter((box) => box.width > 0)
                .map((box) => `${Math.round(box.width)}x${Math.round(box.height)}`),
            ),
          ],
      );
      const tooSmall = sizes.filter(
        (size) => Math.min(...size.split("x").map(Number)) < minTarget,
      );
      if (tooSmall.length > 0) undersized.push(`${name} under ${minTarget}px (${tooSmall.join(", ")})`);
      if (sizes.length > 1) undersized.push(`${name} has ${sizes.length} sizes (${sizes.join(", ")})`);

      const selected = page.locator('[role="tab"][aria-selected="true"]');
      if ((await selected.count()) > 0) {
        const inView = await selected.first().evaluate((node) => {
          const box = node.getBoundingClientRect();
          return box.left >= -1 && box.right <= window.innerWidth + 1;
        });
      if (!inView) offscreenTab.push(name);
      }

      if (label !== "mobile") {
        const bounds = await page.locator('[data-testid="responsive-page"]').evaluate((node) => {
          const pageBox = node.getBoundingClientRect();
          const content = document.querySelector("main#main")!.getBoundingClientRect();
          const layout = (node as HTMLElement).dataset.layout;
          return {
            width: pageBox.width,
            max: layout === "reading"
              ? 72 * 16
              : layout === "operational"
                ? 112 * 16
                : layout === "work-surface"
                  ? content.width
                  : 90 * 16,
            centeringError: Math.abs((pageBox.left - content.left) - (content.right - pageBox.right)),
          };
        });
        expect(bounds.width).toBeLessThanOrEqual(bounds.max + 1);
        expect(bounds.centeringError).toBeLessThanOrEqual(1);
      }

      if (label === "mobile" && (name === "chat" || name === "build")) {
        const composerBottom = await page.locator("form.composer:visible").evaluate(
          (node) => Math.max(
            node.getBoundingClientRect().bottom,
            ...[...node.querySelectorAll("*")]
              .filter((child) => (child as HTMLElement).offsetParent !== null)
              .map((child) => child.getBoundingClientRect().bottom),
          ),
        );
        expect(composerBottom, `${name} composer bottom edge`).toBeLessThanOrEqual(viewport.height + 1);
      }

      const image = await page.screenshot({ path: `${SHOTS}/${label}-${theme}-${name}.png` });
      expect(image.readUInt32BE(16), `${name} PNG width`).toBe(viewport.width);
      expect(image.readUInt32BE(20), `${name} PNG height`).toBe(viewport.height);
    }

    expect(overflowing, `pages overflowing horizontally at ${label}`).toEqual([]);
    expect(iconless, `pages rendering an icon with no glyph at ${label}`).toEqual([]);
    expect(offscreenTab, `pages whose selected tab is off screen at ${label}`).toEqual([]);
    expect(undersized, `pages with an undersized checkbox or radio at ${label}`).toEqual([]);
    expect(consoleErrors, `console errors at ${label}/${theme}`).toEqual([]);
  });
  }
}
