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
