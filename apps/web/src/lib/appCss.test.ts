import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(resolve(process.cwd(), "src", "app.css"), "utf8");

describe("global mobile accessibility styles", () => {
  it("keeps shared mobile shell controls at the 44px touch-target floor", () => {
    expect(stylesheet).toMatch(
      /@media \(max-width: 1023px\)\s*\{\s*\.btn,\s*\.input,\s*\.select,\s*\.stop-btn\s*\{\s*min-height: 44px;/s,
    );
  });

  it("disables animated scrolling when reduced motion is requested", () => {
    expect(stylesheet).toMatch(
      /@media \(prefers-reduced-motion: reduce\)\s*\{\s*html\s*\{\s*scroll-behavior: auto;/s,
    );
  });
});

// Shared primitives exist so views stop inventing their own pills, property
// lists, and hover treatments. These guards keep them token-only: a primitive
// that hard-codes a colour would break theme parity without any view changing.
describe("shared design primitives", () => {
  it("defines the primitives views are expected to reuse", () => {
    for (const selector of [
      ".card-interactive",
      ".card-grid",
      ".chip-row",
      ".chip",
      ".property-list",
      ".sticky-heading",
    ]) {
      expect(stylesheet).toContain(`${selector} {`);
    }
  });

  it("drops the interactive card lift under reduced motion", () => {
    expect(stylesheet).toMatch(
      /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.card-interactive:hover\s*\{\s*transform: none;/s,
    );
  });

  it("styles primitives from tokens rather than literal colours", () => {
    const primitives = stylesheet.slice(stylesheet.indexOf(".card-interactive {"));
    // No hex literals and no rgb()/hsl() calls: every colour must resolve
    // through a custom property so both themes stay in lockstep.
    expect(primitives).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(primitives).not.toMatch(/\b(rgb|rgba|hsl|hsla)\(/);
  });
});

// BUG-37 — the visual language, held to what it claims. Each block below pins
// one of the six things the entry said still needed a decision, so a later edit
// that quietly removes a scale step or a density hook fails here rather than in
// a screenshot nobody re-takes.
describe("type scale", () => {
  it("defines a named step for every size the app is allowed to use", () => {
    for (const token of [
      "--text-2xs",
      "--text-xs",
      "--text-sm",
      "--text-md",
      "--text-base",
      "--text-lg",
      "--text-xl",
      "--text-2xl",
      "--text-display",
    ]) {
      expect(stylesheet).toContain(`${token}:`);
    }
  });

  it("separates the heading levels by size rather than by weight alone", () => {
    const size = (token: string) =>
      Number(new RegExp(`${token}: ([\\d.]+)rem`).exec(stylesheet)?.[1] ?? "0");
    const [h3, h2, h1, display] = [
      size("--text-lg"),
      size("--text-xl"),
      size("--text-2xl"),
      size("--text-display"),
    ];
    expect(h3).toBeGreaterThan(0);
    // The old ladder was 0.95 / 1.08 / 1.45 — the first gap was 14%, which reads
    // as "the same size, bolder". Every step is now a visible interval.
    expect(h2 / h3).toBeGreaterThan(1.15);
    expect(h1 / h2).toBeGreaterThan(1.15);
    expect(display / h1).toBeGreaterThan(1.15);
  });

  it("uses the serif face for display type and only for display type", () => {
    const rule = /\.display,\s*h1\.display,\s*h2\.display\s*\{[^}]*font-family: var\(--font-serif\)/s;
    expect(stylesheet).toMatch(rule);
  });

  it("drives the headings from the scale instead of hard-coded rem values", () => {
    expect(stylesheet).toMatch(/h1 \{\s*font-size: var\(--text-2xl\)/);
    expect(stylesheet).toMatch(/h2 \{\s*font-size: var\(--text-xl\)/);
    expect(stylesheet).toMatch(/h3 \{\s*font-size: var\(--text-lg\)/);
  });
});

describe("density", () => {
  it("gives each mode its own control padding and row height", () => {
    for (const mode of ["compact", "spacious"]) {
      const block = new RegExp(`\\[data-spacing="${mode}"\\]\\s*\\{([^}]*)\\}`, "s").exec(
        stylesheet,
      )?.[1];
      expect(block).toBeTruthy();
      // The bug was that density only moved the gaps *around* a table. These
      // two are what make it reach the table itself.
      expect(block).toContain("--control-y:");
      expect(block).toContain("--row-y:");
    }
  });

  it("spends those tokens where a row height actually comes from", () => {
    expect(stylesheet).toMatch(/\.table td \{\s*padding: var\(--row-y\) var\(--row-x\)/);
    expect(stylesheet).toMatch(/padding: var\(--control-y\) var\(--control-x\)/);
    expect(stylesheet).toMatch(/\.card \{[^}]*padding: var\(--card-pad-y\) var\(--card-pad-x\)/s);
  });
});

describe("motion", () => {
  it("names three intents with a duration and an easing each", () => {
    for (const token of [
      "--motion-fast",
      "--motion-enter",
      "--motion-exit",
      "--motion-emphasis",
      "--ease-enter",
      "--ease-exit",
      "--ease-emphasis",
    ]) {
      expect(stylesheet).toContain(`${token}:`);
    }
  });

  it("honours reduced motion by naming the end state, not just a 0ms duration", () => {
    // A collapsed duration still paints the animation's first frame for an
    // instant, which is enough to flash on screen.
    expect(stylesheet).toMatch(
      /\.motion-enter,\s*\.motion-exit,\s*\.motion-emphasis \{\s*animation: none;\s*opacity: 1;\s*transform: none;/s,
    );
    expect(stylesheet).toMatch(/\.skeleton \{\s*animation: none;/);
  });
});

describe("data-visual language", () => {
  it("defines one meter and one bar rather than one per view", () => {
    for (const selector of [".meter,", ".meter-fill,", ".meter-label {", ".skeleton {"]) {
      expect(stylesheet).toContain(selector);
    }
  });

  it("gives a meter its state tones from the same tokens the badges use", () => {
    for (const tone of ["ok", "warn", "danger"]) {
      expect(stylesheet).toContain(`.meter.tone-${tone} .meter-fill`);
      expect(stylesheet).toMatch(new RegExp(`\\.meter\\.tone-${tone} \\.meter-fill \\{\\s*background: var\\(--${tone}\\)`));
    }
  });

  it("sets tabular figures wherever numbers are compared vertically", () => {
    expect(stylesheet).toMatch(/font-variant-numeric: tabular-nums/);
    expect(stylesheet).toContain(".table td.numeric");
  });

  it("never rounds a non-zero proportion down to nothing", () => {
    // A 1% fill shown as a sliver reads as "none", which is a different fact.
    expect(stylesheet).toMatch(/\.meter-fill:not\(\[data-value="0"\]\)/);
    expect(stylesheet).toMatch(/min-width: 2px/);
  });
});
