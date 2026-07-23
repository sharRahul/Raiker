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
