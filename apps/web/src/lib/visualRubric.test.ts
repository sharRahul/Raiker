/**
 * VIS-24 — the parts of a visual review a machine can hold on to.
 *
 * Raiker already has unusually strong responsive and accessibility coverage:
 * the width sweep proves no page overflows, the axe scans prove contrast and
 * focus order, and `appCss.test.ts` proves the scale and the tokens exist.
 * None of that proves the interface looks calm or intentional, which is the
 * gap the visual review names — an interface can pass every one of those checks
 * and still be a wall of cards shouting in five colours.
 *
 * Most of that judgement stays human, and the rubric for it lives in
 * `docs/architecture/VISUAL_DESIGN_SPEC.md`. What is mechanised here is the
 * subset with an objective answer, and each one is a rule that was *actually
 * broken* at some point rather than a rule invented to have a test:
 *
 * * an empty state that offers no way out — every one of thirteen call sites,
 *   until VIS-12;
 * * a permanent row for a destination reached on a handful of days — nine peers
 *   in the rail, until VIS-01;
 * * a shared layout re-declared privately per view until the surfaces drift —
 *   eight byte-identical copies of `.head-row`, until VIS-23.
 *
 * A rule nobody can break silently is worth more than a rule everybody agrees
 * with.
 */
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { NAV_ITEMS, SIDEBAR_ITEM_IDS } from "./nav";

const VIEWS = resolve(process.cwd(), "src", "lib", "views");
const COMPONENTS = resolve(process.cwd(), "src", "lib", "components");
const stylesheet = readFileSync(resolve(process.cwd(), "src", "app.css"), "utf8");

function sources(directory: string): { name: string; text: string }[] {
  return readdirSync(directory)
    .filter((name) => name.endsWith(".svelte") && !name.endsWith(".test.svelte"))
    .map((name) => ({ name, text: readFileSync(resolve(directory, name), "utf8") }));
}

describe("visual rubric", () => {
  it("keeps the permanent rail short enough to read at a glance", () => {
    // VIS-01. The number is a judgement, but "no ceiling at all" is how a rail
    // reaches nine peers one reasonable addition at a time. Anything above this
    // belongs behind the gear or in the palette, both of which reach everything.
    expect(SIDEBAR_ITEM_IDS.length).toBeLessThanOrEqual(8);
  });

  it("still reaches every route from somewhere", () => {
    // The rail may shrink; the product may not. Whatever is not on the rail has
    // to be in the gear's window, and the palette lists `NAV_ITEMS` whole.
    const offRail = NAV_ITEMS.filter((item) => !SIDEBAR_ITEM_IDS.includes(item.id));
    expect(offRail.length).toBeGreaterThan(0);
    for (const item of NAV_ITEMS) expect(item.label.trim()).not.toBe("");
  });

  it("declares the page-header contract once, not once per view", () => {
    // VIS-23/VIS-04. Eight views each carried a private, byte-identical copy.
    // Nothing had to disagree for the surfaces to drift — only to be edited
    // separately.
    expect(stylesheet).toMatch(/\.head-row\s*\{/);
    const privateCopies = sources(VIEWS).filter(({ text }) =>
      /^\s*\.head-row\s*\{[^}]*display\s*:\s*flex/m.test(text),
    );
    expect(privateCopies.map((file) => file.name)).toEqual([]);
  });

  it("gives every empty state a way out", () => {
    // VIS-12. `EmptyState` has carried an `action` slot for a long time; the
    // defect was that no call site used it. A zero-data screen that names the
    // absence and stops is a dead end, and a product with this many of them
    // cannot afford thirteen.
    //
    // The exceptions are named rather than pattern-matched, because each is a
    // judgement about that screen and should have to be argued for again if
    // somebody adds a fourteenth.
    const noActionIsCorrect = new Set([
      // A filtered list with no matches: the way out is the filters the owner
      // is already looking at, and a button that clears them would be a second
      // control for the one they just used.
      "ActivityView.svelte",
      "SearchChatView.svelte",
      // "Nothing waiting on you" and "nothing has been raised" are *success*.
      // Offering an action would invent work.
      "ApprovalsView.svelte",
      "ObserveView.svelte",
      // A build that shipped without the guide is a genuine error, and the
      // rubric allows diagnostic text where the absence really is one.
      "GuideView.svelte",
      // Chat and Build open onto their own composer, which is directly below
      // the empty state and is the action.
      "ChatView.svelte",
      "BuildView.svelte",
      "BuildSidePanel.svelte",
    ]);

    const offenders: string[] = [];
    for (const { name, text } of [...sources(VIEWS), ...sources(COMPONENTS)]) {
      if (!text.includes("<EmptyState")) continue;
      if (noActionIsCorrect.has(name)) continue;
      if (!text.includes("{#snippet action()}")) offenders.push(name);
    }
    expect(offenders).toEqual([]);
  });

  it("does not send the owner to a file the product no longer reads", () => {
    // FIXED-436 removed working-directory config resolution, which turned the
    // Models empty state into an instruction to edit a file that has no effect.
    // Interface copy naming a path is a standing liability; this catches the
    // one that already went stale.
    //
    // Comments are stripped first: this is a rule about what the *owner* is
    // told, and the commentary explaining why the copy changed necessarily
    // quotes the path it removed.
    const withoutComments = (text: string) =>
      text
        .replace(/<!--[\s\S]*?-->/g, "")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/(^|[^:])\/\/.*$/gm, "$1");

    for (const { name, text } of sources(VIEWS)) {
      expect(withoutComments(text), `${name} tells the owner to edit a path Raiker no longer reads`)
        .not.toMatch(/config\/model-profiles\.json/);
    }
  });
});
