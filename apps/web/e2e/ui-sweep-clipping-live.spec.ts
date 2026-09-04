/**
 * Every route, at four widths, with nothing clipped off the edge.
 *
 * The sweep this replaces was a set of screenshots somebody had to look at.
 * Looking is how three defects survived several rounds of it:
 *
 *   * **Models on a phone.** `.panel` is a grid whose column was left at `auto`,
 *     so one unwrappable descendant sized the track to 416px inside a 366px
 *     page and *every sibling stretched to match* — including plain paragraphs,
 *     which were then clipped mid-sentence.
 *   * **The Knowledge Map canvas never resized.** Its `ResizeObserver` attached
 *     in `onMount` to an element that lives on the `{:else}` branch of a load
 *     state, so on any render where that branch was not up yet it observed
 *     nothing and never ran again. The canvas stayed at its 900px default on
 *     every window.
 *   * **Two bottom bars in the same corner.** The graph's status and its zoom
 *     controls are pinned bottom-left and bottom-right, and below ~540px they
 *     are wider together than the window, so each hid half of the other.
 *
 * All three are measurements, so this measures them. Content inside something
 * that scrolls or clips on purpose — a tab strip, a wide table, a pannable
 * canvas — is not a defect and is excluded by walking up for that ancestor.
 */
import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";

const ROUTES = [
  "workbench", "new-chat", "build", "search-chat", "tasks", "projects", "memory",
  "brain", "approvals", "capabilities", "models",
  "extensions?tab=connectors", "extensions?tab=mcp", "extensions?tab=skills",
  "extensions?tab=hooks", "extensions?tab=plugins", "extensions?tab=channels",
  "observe?tab=overview", "observe?tab=sessions", "observe?tab=activity",
  "observe?tab=checkpoints", "observe?tab=diagnostics", "observe?tab=work",
  "observe?tab=notifications", "settings", "guide",
] as const;

// Four, not three. 768 is where the shell's own breakpoints change hands —
// several views collapse a two-column grid there and a rail becomes a sheet —
// so a sweep that jumps 390 → 1024 steps over the width most likely to break.
const WIDTHS = [
  ["phone", 390, 844],
  ["narrow", 768, 900],
  ["tablet", 1024, 800],
  ["desktop", 1440, 1000],
] as const;

/** Anything reaching past the window that nothing scrolls or clips on purpose. */
async function clipped(page: import("@playwright/test").Page): Promise<string[]> {
  return page.evaluate(() => {
    const limit = document.documentElement.clientWidth;
    const out: string[] = [];
    const contained = (el: HTMLElement): boolean => {
      let node: HTMLElement | null = el;
      while (node !== null && node !== document.body) {
        const style = getComputedStyle(node);
        if (/auto|scroll|hidden|clip/.test(style.overflowX)) return true;
        node = node.parentElement;
      }
      return false;
    };
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("main#main *"))) {
      const box = el.getBoundingClientRect();
      if (box.width === 0 && box.height === 0) continue;
      if (box.right > limit + 2 && !contained(el)) {
        out.push(`${el.tagName.toLowerCase()}.${String(el.className ?? "").slice(0, 36)}`);
      }
      if (out.length > 4) break;
    }
    return [...new Set(out)];
  });
}

test("no route clips its own content at any of the four widths", async ({ page }) => {
  test.setTimeout(900_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await signInAsOwner(page, BASE);

  const found: string[] = [];
  for (const [label, width, height] of WIDTHS) {
    await page.setViewportSize({ width, height });
    for (const route of ROUTES) {
      await page.goto(`${BASE}/#/${route}`);
      await page.waitForTimeout(1_000);
      const bad = await clipped(page);
      if (bad.length > 0) found.push(`${label} ${route}: ${bad.join(" | ")}`);
    }
  }
  expect(found, found.join("\n")).toEqual([]);
  // A sweep that clips nothing and logs an uncaught error has not passed.
  expect(consoleErrors).toEqual([]);
});

test("the knowledge map fits itself into a phone rather than starting off screen", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/#/brain`);
  await expect(page.getByRole("application")).toBeVisible({ timeout: 60_000 });
  // The canvas is the size of the box it is drawn in, not a 900px default.
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const stage = document.querySelector<SVGSVGElement>("svg.graph-stage");
          const box = stage?.parentElement?.getBoundingClientRect();
          return Math.abs(Number(stage?.getAttribute("width")) - (box?.width ?? 0));
        }),
      { timeout: 30_000 },
    )
    .toBeLessThan(4);

  // And after the auto-fit, most of the graph is where the owner can see it.
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const limit = document.documentElement.clientWidth;
          const nodes = Array.from(document.querySelectorAll<SVGGElement>("g.graph-node"));
          if (nodes.length === 0) return 0;
          const on = nodes.filter((node) => {
            const box = node.getBoundingClientRect();
            return box.left >= -2 && box.right <= limit + 2;
          });
          return on.length / nodes.length;
        }),
      { timeout: 30_000 },
    )
    .toBeGreaterThan(0.7);
});

test("the graph's two bottom bars do not sit on top of each other on a phone", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/#/brain`);
  const status = page.getByText("Live workspace graph");
  const zoom = page.getByRole("button", { name: "Fit graph" });
  await expect(status).toBeVisible({ timeout: 60_000 });
  await expect(zoom).toBeVisible();
  const a = await status.boundingBox();
  const b = await zoom.boundingBox();
  expect(a).not.toBeNull();
  expect(b).not.toBeNull();
  const overlaps =
    a !== null &&
    b !== null &&
    a.x < b.x + b.width &&
    b.x < a.x + a.width &&
    a.y < b.y + b.height &&
    b.y < a.y + a.height;
  expect(overlaps).toBe(false);
});
