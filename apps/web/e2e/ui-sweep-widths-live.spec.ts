/**
 * Every page, at four widths, checked for the three things a screenshot sweep
 * cannot check for you.
 *
 * `all-pages-live.spec.ts` photographs each page at one width and asserts the
 * console stayed clean. That catches a page that broke and misses a page that
 * merely does not *fit*: a table that pushes the whole document sideways on a
 * phone, a control whose only label is an icon, a heading that repeats the
 * page's own name back at it. Those are read by a person on a real window and
 * by nothing in the suite.
 *
 * So this walks the same routes at 390, 768, 1280 and 1920 and asserts three
 * properties that hold at every one of them:
 *
 * 1. **The page never scrolls sideways.** Wide content — a table, a diff, a
 *    code block — belongs in its own `overflow-x: auto` container. A document
 *    wider than its viewport is the defect this catches, and it is invisible on
 *    a desktop screenshot.
 * 2. **Nothing bleeds out of its box.** An element whose content is wider than
 *    it is, with `overflow-x: visible`, is drawing over its neighbour. A
 *    deliberate scroller (`auto`/`scroll`) and a deliberate truncation
 *    (`hidden`, which is what `text-overflow: ellipsis` needs) are both fine and
 *    are not flagged.
 * 3. **Every control says what it is.** A button or link whose accessible name
 *    is empty is an icon a sighted owner has to guess at and a screen-reader
 *    owner cannot reach at all.
 * 4. **No control is a blank shape.** A button with a name but *nothing drawn
 *    inside it* — no text, no icon with a size — is a grey circle beside Send.
 *    Raiker has shipped that defect twice, both times because a rule that hides
 *    a label at a narrow width left a control whose only other child was absent
 *    in that state. A screenshot shows it and no assertion did.
 *
 * Findings are collected across the whole sweep rather than failing on the
 * first, because "one page is wrong" and "every page is wrong at 390" are
 * different problems and the second is the useful one to read.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";

/** Every routed destination the navigation offers. */
const ROUTES = [
  ["workbench", "workbench"],
  ["chat", "new-chat"],
  ["build", "build"],
  ["threads", "search-chat"],
  ["tasks", "tasks"],
  ["projects", "projects"],
  ["memory", "memory"],
  ["brain", "brain"],
  ["approvals", "approvals"],
  ["permissions", "capabilities"],
  ["models", "models"],
  ["connectors", "extensions?tab=connectors"],
  ["mcp", "extensions?tab=mcp"],
  ["skills", "extensions?tab=skills"],
  ["hooks", "extensions?tab=hooks"],
  ["plugins", "extensions?tab=plugins"],
  ["channels", "extensions?tab=channels"],
  ["observe-overview", "observe?tab=overview"],
  ["observe-sessions", "observe?tab=sessions"],
  ["observe-activity", "observe?tab=activity"],
  ["observe-checkpoints", "observe?tab=checkpoints"],
  ["observe-diagnostics", "observe?tab=diagnostics"],
  ["observe-work", "observe?tab=work"],
  ["observe-notifications", "observe?tab=notifications"],
  ["settings", "settings"],
] as const;

/** Phone, tablet, laptop, wide desktop. */
const WIDTHS = [
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1280", width: 1280, height: 900 },
  { name: "1920", width: 1920, height: 1080 },
] as const;

/** The widths whose captures are kept as evidence. The two extremes are where
 *  a layout actually fails; the middle two are asserted and not photographed. */
const CAPTURED = new Set(["390", "1920"]);

type Finding = { route: string; width: string; kind: string; detail: string };

async function settle(page: import("@playwright/test").Page): Promise<void> {
  await expect(page.locator("main#main")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(
    () =>
      ![...document.querySelectorAll("main#main *")].some((element) => {
        const node = element as HTMLElement;
        const visible = node.offsetWidth > 0 || node.offsetHeight > 0;
        return visible && /^(loading|reading|checking|verifying)\b/i.test((node.textContent ?? "").trim());
      }),
    undefined,
    { timeout: 20_000 },
  );
  await page.waitForTimeout(400);
}

test("every page fits, contains itself, and names its controls at four widths", async ({ page }) => {
  test.setTimeout(600_000);
  const findings: Finding[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE);

  for (const viewport of WIDTHS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const [name, route] of ROUTES) {
      await page.goto(`${BASE}/#/${route}`);
      await settle(page);

      const report = await page.evaluate(() => {
        const out = {
          documentWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
          bleeding: [] as string[],
          unnamed: [] as string[],
          blank: [] as string[],
        };

        const describe = (element: Element): string => {
          const tag = element.tagName.toLowerCase();
          const cls = (element.getAttribute("class") ?? "").split(/\s+/).filter(Boolean).slice(0, 2);
          const text = (element.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 40);
          return `${tag}${cls.length ? `.${cls.join(".")}` : ""}${text ? ` “${text}”` : ""}`;
        };

        for (const element of Array.from(document.querySelectorAll<HTMLElement>("main#main *"))) {
          if (element.offsetWidth === 0 && element.offsetHeight === 0) continue;
          // SVG has its own layout model: `clientWidth` on an `<svg:text>` is
          // not a content box, and comparing it to `scrollWidth` reported a
          // graph label as bleeding when it was drawing exactly where the graph
          // put it. A label that outgrows its node is a rendering question for
          // that view, not a page-layout defect, and this check is about the
          // page.
          if (element.namespaceURI !== "http://www.w3.org/1999/xhtml") continue;
          const style = getComputedStyle(element);
          // A deliberate scroller and a deliberate truncation are both correct.
          // Only content bleeding out of a `visible` box is a defect.
          if (style.overflowX !== "visible") continue;
          if (element.scrollWidth > element.clientWidth + 2 && element.clientWidth > 0) {
            out.bleeding.push(`${describe(element)} (${element.scrollWidth} in ${element.clientWidth})`);
          }
        }

        for (const element of Array.from(
          document.querySelectorAll<HTMLElement>("button, a[href], [role='button'], [role='tab']"),
        )) {
          if (element.offsetWidth === 0 && element.offsetHeight === 0) continue;
          // Nothing *rendered* inside a control that has a box of its own.
          //
          // `textContent` is the wrong test and was the first thing tried here:
          // it reports a label the CSS has set to `display: none`, which is
          // exactly the state this check exists to catch. A Range over the
          // element's contents measures what is actually painted, and a
          // descendant with a real box covers an icon.
          const range = document.createRange();
          range.selectNodeContents(element);
          const painted = Array.from(range.getClientRects()).some(
            (rect) => rect.width > 0 && rect.height > 0,
          );
          const drawsSomething =
            painted ||
            Array.from(element.querySelectorAll<HTMLElement>("*")).some((child) => {
              const box = child.getBoundingClientRect();
              return box.width > 0 && box.height > 0;
            });
          if (!drawsSomething) out.blank.push(describe(element));
          const named =
            (element.textContent ?? "").trim() ||
            element.getAttribute("aria-label") ||
            element.getAttribute("title") ||
            (element.getAttribute("aria-labelledby") ?? "") ||
            element.querySelector("img[alt]")?.getAttribute("alt") ||
            "";
          if (!named.trim()) out.unnamed.push(describe(element));
        }
        return out;
      });

      if (report.documentWidth > report.viewportWidth + 1) {
        findings.push({
          route: name,
          width: viewport.name,
          kind: "page scrolls sideways",
          detail: `document ${report.documentWidth}px in a ${report.viewportWidth}px window`,
        });
      }
      for (const detail of report.bleeding.slice(0, 5)) {
        findings.push({ route: name, width: viewport.name, kind: "content bleeds out of its box", detail });
      }
      for (const detail of report.unnamed.slice(0, 5)) {
        findings.push({ route: name, width: viewport.name, kind: "control has no accessible name", detail });
      }
      for (const detail of report.blank.slice(0, 5)) {
        findings.push({ route: name, width: viewport.name, kind: "control draws nothing", detail });
      }

      if (CAPTURED.has(viewport.name)) {
        await capture(page, `../../docs/plans/screenshots/widths/${viewport.name}-${name}.png`);
      }
    }
  }

  if (findings.length > 0) {
    // One readable table rather than a stack trace: which page, which width,
    // and what the browser measured.
    console.log(
      findings
        .map((finding) => `${finding.width}px · ${finding.route}: ${finding.kind} — ${finding.detail}`)
        .join("\n"),
    );
  }
  expect(findings, `UI findings:\n${findings.map((f) => `${f.width}px ${f.route}: ${f.kind} — ${f.detail}`).join("\n")}`).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
