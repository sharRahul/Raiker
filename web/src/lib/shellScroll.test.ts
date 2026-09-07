// The shell's scroll contract: exactly one thing scrolls the page, and it is
// `.content`. The sidebar and topbar are outside it, so they cannot move.
//
// These are source assertions rather than behavioural ones on purpose — jsdom
// performs no layout, so a rendered test cannot tell a scrolling element from a
// growing one. The rules below are the ones whose absence actually broke this:
// a chat column that resolved to `height: auto` grew past the viewport, pushed
// its composer off the bottom of the screen, and handed the overflow to the
// document, taking the navigation with it.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const read = (...parts: string[]) => readFileSync(resolve(process.cwd(), "src", ...parts), "utf8");

const appShell = read("App.svelte");
const sidebar = read("lib", "components", "Sidebar.svelte");
const chat = read("lib", "views", "ChatView.svelte");
const build = read("lib", "views", "BuildView.svelte");

/** The declarations inside one CSS rule, whitespace-normalised. */
function rule(css: string, selector: string, requiredDeclaration?: string): string {
  let start = css.indexOf(`${selector} {`);
  while (start > -1) {
    const declarations = css.slice(start, css.indexOf("}", start)).replace(/\s+/g, " ");
    if (requiredDeclaration === undefined || declarations.includes(requiredDeclaration)) return declarations;
    start = css.indexOf(`${selector} {`, start + selector.length);
  }
  expect(start, `missing rule: ${selector}`).toBeGreaterThan(-1);
  return "";
}

describe("app shell scroll containment", () => {
  it("pins the shell to the viewport and clips anything that escapes it", () => {
    // Without the clip, a page that overflows its column scrolls the document —
    // and the sidebar and topbar scroll away with it.
    const shell = rule(appShell, ".app-shell");
    expect(shell).toMatch(/height: 100dvh;/);
    expect(shell).toMatch(/overflow: hidden;/);
  });

  it("lets the shell's flex columns shrink below their content", () => {
    // A flex item defaults to min-height: auto and refuses to shrink, so the
    // column grows past the shell instead of letting `.content` scroll.
    expect(rule(appShell, ".app-main")).toMatch(/min-height: 0;/);
    expect(rule(appShell, ".content")).toMatch(/min-height: 0;/);
  });

  it("makes `.content` the page scroller and a containing block", () => {
    const content = rule(appShell, ".content");
    expect(content).toMatch(/overflow: auto;/);
    // Absolutely-positioned descendants with no positioned ancestor (a
    // visually-hidden label, say) otherwise resolve against the viewport and
    // report their offset as root overflow — a stray page scrollbar.
    expect(content).toMatch(/position: relative;/);
  });

  it("publishes the room a page has, for views that pin a footer", () => {
    // Both breakpoints must define it: the phone padding reserves space for the
    // bottom navigation, so a single desktop value would overshoot there.
    expect(appShell.match(/--content-h:/g) ?? []).toHaveLength(2);
  });

  it("scrolls a too-tall navigation inside the sidebar itself", () => {
    const rail = rule(sidebar, ".sidebar");
    expect(rail).toMatch(/overflow-y: auto;/);
    expect(rail).toMatch(/position: relative;/);
  });
});

describe("conversation columns keep their composer on screen", () => {
  for (const [name, css, columnSelector, scrollerSelector] of [
    ["Chat", chat, ".chat", ".thread"],
    ["Build", build, ".build", ".thread"],
  ] as const) {
    it(`${name} sizes its column from the shell's room, not its transcript`, () => {
      // `height: 100%` cannot express this: the page wrapper is auto-height, so
      // the percentage resolves to `auto` and the column grows with the
      // conversation.
      const column = rule(css, columnSelector);
      expect(column).toMatch(/height: var\(--content-h\)/);
      expect(column).not.toMatch(/height: 100%/);
    });

    it(`${name} scrolls the transcript inside itself`, () => {
      const scroller = rule(css, scrollerSelector, "overflow-y: auto;");
      expect(scroller).toMatch(/overflow-y: auto;/);
      expect(scroller).toMatch(/min-height: 0;/);
    });
  }
});
