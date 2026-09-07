/**
 * Every current destination at the practical viewport classes Raiker commits as
 * screenshot evidence, against a real authenticated instance.
 *
 * This is deliberately a page-level sweep rather than a feature test. It catches
 * horizontal overflow, missing icon glyphs, selected hub tabs that are off-screen,
 * undersized form controls and browser-console failures that can be invisible to
 * a narrowly scoped component spec.
 *
 * Current evidence is written to `docs/screenshots/pages/` at mobile and 1080p
 * only, in light and dark themes. 4K/8K files were useful during the original
 * responsive redesign but are not a useful committed evidence class for normal
 * product review.
 */
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { DESTINATIONS, hubReachability } from "./destinations";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE_URL ?? "http://127.0.0.1:8765";
const LIVE_USER = process.env.RAIKER_LIVE_USER;
const LIVE_PASSWORD = process.env.RAIKER_LIVE_PASSWORD;
const SHOTS = "../../docs/screenshots/pages";

const ROUTES = DESTINATIONS.map((d) => [d.name, d.route] as const);

const CAPTURES = [
  ["mobile", { width: 390, height: 844 }],
  ["1080p", { width: 1920, height: 1080 }],
] as const;

const selectedCaptures = new Set(
  process.env.RAIKER_SWEEP_CAPTURE?.split(",")
    .map((name) => name.trim())
    .filter(Boolean),
);
const ACTIVE_CAPTURES =
  selectedCaptures.size > 0
    ? CAPTURES.filter(([name]) => selectedCaptures.has(name))
    : CAPTURES;

const selectedRoutes = new Set(
  process.env.RAIKER_SWEEP_ROUTE?.split(",")
    .map((name) => name.trim())
    .filter(Boolean),
);
const ACTIVE_ROUTES =
  selectedRoutes.size > 0
    ? ROUTES.filter(([name]) => selectedRoutes.has(name))
    : ROUTES;

const THEMES = ["light", "dark"] as const;
mkdirSync(SHOTS, { recursive: true });

async function signIn(page: import("@playwright/test").Page) {
  if (!LIVE_USER || !LIVE_PASSWORD) {
    throw new Error(
      "RAIKER_LIVE_USER and RAIKER_LIVE_PASSWORD are required for the live UI sweep.",
    );
  }
  await signInAsOwner(page, BASE, { user: LIVE_USER, password: LIVE_PASSWORD });
}

async function settle(page: import("@playwright/test").Page) {
  await expect(page.locator("main#main")).toBeVisible();
  await page
    .waitForFunction(
      () =>
        ![...document.querySelectorAll("main#main *")].some((element) => {
          const node = element as HTMLElement;
          const visible = node.offsetWidth > 0 || node.offsetHeight > 0;
          return (
            visible &&
            /^(loading|reading|checking|verifying)\b/i.test(
              (node.textContent ?? "").trim(),
            )
          );
        }),
      undefined,
      { timeout: 20_000 },
    )
    .catch(() => undefined);

  // Keep the virtual pointer away from product controls so evidence does not
  // accidentally capture a hover state left by the previous route.
  await page.mouse.move(2, 2);
  await page.waitForTimeout(500);
}

test.describe.configure({ mode: "serial" });

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

      // Theme lives in Settings and project context is carried by the Work
      // surfaces; neither should regrow a permanent top-bar selector.
      await expect(page.getByRole("button", { name: /^Theme: / })).toHaveCount(0);
      await expect(page.getByLabel("Active project")).toHaveCount(0);

      const overflowing: string[] = [];
      const iconless: string[] = [];
      const offscreenTab: string[] = [];
      const undersized: string[] = [];
      const hub = hubReachability(page);
      const consoleErrors: string[] = [];
      page.on("console", (message) => {
        if (message.type() === "error") consoleErrors.push(message.text());
      });

      for (const [name, route] of ACTIVE_ROUTES) {
        await page.goto(`${BASE}/#/${route}`);
        await settle(page);

        const overflow = await page.evaluate(
          () =>
            document.documentElement.scrollWidth -
            document.documentElement.clientWidth,
        );
        if (overflow > 1) overflowing.push(`${name} (+${overflow}px)`);

        const empty = await page.evaluate(
          () =>
            [
              ...document.querySelectorAll(
                "main#main svg, header svg, nav svg",
              ),
            ].filter((svg) => {
              const node = svg as SVGElement;
              const visible = node.getBoundingClientRect().width > 0;
              return visible && node.children.length === 0;
            }).length,
        );
        if (empty > 0) iconless.push(`${name} (${empty})`);

        // On compact layouts controls need the full WCAG 2.2 24px target floor.
        // On desktop the invariant is primarily that the app does not regress
        // into several unrelated native checkbox/radio sizes.
        const minTarget = viewport.width < 1024 ? 24 : 16;
        const sizes = await page.evaluate(
          () => [
            ...new Set(
              [
                ...document.querySelectorAll<HTMLElement>(
                  'main#main input[type="checkbox"], main#main input[type="radio"]',
                ),
              ]
                .map((node) => node.getBoundingClientRect())
                .filter((box) => box.width > 0)
                .map(
                  (box) =>
                    `${Math.round(box.width)}x${Math.round(box.height)}`,
                ),
            ),
          ],
        );
        const tooSmall = sizes.filter(
          (size) => Math.min(...size.split("x").map(Number)) < minTarget,
        );
        if (tooSmall.length > 0) {
          undersized.push(
            `${name} under ${minTarget}px (${tooSmall.join(", ")})`,
          );
        }
        if (sizes.length > 1) {
          undersized.push(
            `${name} has ${sizes.length} sizes (${sizes.join(", ")})`,
          );
        }

        const selected = page.locator('[role="tab"][aria-selected="true"]');
        if ((await selected.count()) > 0) {
          const inView = await selected.first().evaluate((node) => {
            const box = node.getBoundingClientRect();
            return box.left >= -1 && box.right <= window.innerWidth + 1;
          });
          if (!inView) offscreenTab.push(name);
        }

        if (label !== "mobile") {
          const bounds = await page
            .locator('[data-testid="responsive-page"]')
            .evaluate((node) => {
              const pageBox = node.getBoundingClientRect();
              const content = document
                .querySelector("main#main")!
                .getBoundingClientRect();
              const layout = (node as HTMLElement).dataset.layout;
              return {
                width: pageBox.width,
                max:
                  layout === "reading"
                    ? 72 * 16
                    : layout === "operational"
                      ? 112 * 16
                      : layout === "work-surface"
                        ? content.width
                        : 90 * 16,
                centeringError: Math.abs(
                  pageBox.left -
                    content.left -
                    (content.right - pageBox.right),
                ),
              };
            });
          expect(bounds.width).toBeLessThanOrEqual(bounds.max + 1);
          expect(bounds.centeringError).toBeLessThanOrEqual(1);
        }

        if (label === "mobile" && (name === "chat" || name === "build")) {
          const composerBottom = await page
            .locator("form.composer:visible")
            .evaluate((node) =>
              Math.max(
                node.getBoundingClientRect().bottom,
                ...[...node.querySelectorAll("*")]
                  .filter(
                    (child) =>
                      (child as HTMLElement).offsetParent !== null,
                  )
                  .map((child) => child.getBoundingClientRect().bottom),
              ),
            );
          expect(
            composerBottom,
            `${name} composer bottom edge`,
          ).toBeLessThanOrEqual(viewport.height + 1);
        }

        const image = await page.screenshot({
          path: `${SHOTS}/${label}-${theme}-${name}.png`,
        });
        expect(image.readUInt32BE(16), `${name} PNG width`).toBe(
          viewport.width,
        );
        expect(image.readUInt32BE(20), `${name} PNG height`).toBe(
          viewport.height,
        );
      }

      expect(
        overflowing,
        `pages overflowing horizontally at ${label}`,
      ).toEqual([]);
      expect(
        iconless,
        `pages rendering an icon with no glyph at ${label}`,
      ).toEqual([]);
      expect(
        offscreenTab,
        `pages whose selected tab is off screen at ${label}`,
      ).toEqual([]);
      expect(
        undersized,
        `pages with an undersized checkbox or radio at ${label}`,
      ).toEqual([]);
      expect(hub.filter(consoleErrors), `console errors at ${label}/${theme}`).toEqual(
        [],
      );
    });
  }
}
