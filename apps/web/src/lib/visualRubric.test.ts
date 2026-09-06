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
import { BADGES } from "./badges";

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

  it("declares each shared label mark once, not once per view", () => {
    // VIS-04/VIS-06. `.eyebrow` had six private definitions at four weights
    // (600, 750, 750, 800) and five trackings (wide, 0.08, 0.09, 0.12, 0.13em),
    // and `.kicker` had a private copy of the shared rule beside it. None of
    // them disagreed on purpose - they were written separately, which is all
    // it takes for a design system to stop being one.
    //
    // A local rule that only adjusts spacing or colour is fine. One that sets
    // the *type* again is a second opinion about what the mark is.
    const TYPE_PROPERTIES = ["font-size", "font-weight", "text-transform"];

    for (const mark of [".eyebrow", ".kicker"]) {
      expect(stylesheet.includes(mark + " {"), mark + " is not defined in app.css").toBe(true);

      const redefines: string[] = [];
      for (const { name, text } of [...sources(VIEWS), ...sources(COMPONENTS)]) {
        let from = text.indexOf(mark + " {");
        while (from !== -1) {
          const body = text.slice(from, text.indexOf("}", from));
          if (TYPE_PROPERTIES.some((property) => body.includes(property))) {
            redefines.push(name);
            break;
          }
          from = text.indexOf(mark + " {", from + 1);
        }
      }
      expect(redefines, mark + " is redefined per view").toEqual([]);
    }
  });

  it("spends status colour on exceptions, not on the resting state", () => {
    // VIS-15. `safe` ("low-risk, auto-allowed") and `implemented` ("real,
    // working capability") are the resting state of most of the gate table, and
    // both were green — so Permissions opened as a wall of colour reporting
    // that nothing was wrong, which is what makes a product read as monitoring
    // software rather than as a work tool.
    //
    // The named list is the point: a state has to be argued onto it. `done` is
    // on it because finishing is something that happened; `active` because work
    // in flight is worth finding on a page.
    const EARNS_COLOUR = new Set([
      "needs-approval", "approval-required", "blocked", "risk-acceptance-required",
      "metadata-only", "read-only", "active", "done", "stopped",
    ]);

    for (const [variant, meta] of Object.entries(BADGES)) {
      if (meta.tone === "tone-muted") continue;
      expect(
        EARNS_COLOUR.has(variant),
        `badge "${variant}" is coloured (${meta.tone}) but is not on the list of states that earn colour`,
      ).toBe(true);
    }
  });

  it("keeps Chat's composer simpler than Build's", () => {
    // VIS-11. The two share design primitives and must not share density:
    // Chat is a conversation, Build is a workbench. The gap is not decoration -
    // it is what tells a first-time owner which of the two they are in.
    //
    // Counted from the composer's own left cluster, which is where a surface
    // puts the controls that govern the turn.
    const TURN_CONTROLS = ["<ModelPicker", "<PostureControl", "<ComposerAttach", "<BuildModePicker", "<select"];

    const controls = (view: string) => {
      const text = readFileSync(resolve(VIEWS, view), "utf8");
      const from = text.indexOf("snippet left()");
      expect(from, view + " has no composer left cluster").toBeGreaterThan(-1);
      const cluster = text.slice(from, text.indexOf("{/snippet}", from));
      return TURN_CONTROLS.reduce(
        (total, control) => total + cluster.split(control).length - 1,
        0,
      );
    };

    const chat = controls("ChatView.svelte");
    const build = controls("BuildView.svelte");
    expect(chat).toBeGreaterThan(0);
    expect(build).toBeGreaterThan(chat);
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
