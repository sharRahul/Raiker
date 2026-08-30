// The compact (below split-view) layout of the two conversation surfaces.
//
// Chat and Build pin their composer to the bottom of the room the shell gives
// them by sizing from `--content-h`. Below the split-view breakpoint they switch
// Chat grows normally. Build now keeps the transcript in the shell's available
// room while its background-work panel floats as a right drawer, so opening the
// panel cannot change message wrapping.
//
// That switch used to drop the floor along with the ceiling. On a tall tablet an
// empty or short conversation then collapsed to its own content and left the
// composer floating in the middle of the page with half the screen blank under
// it. Keeping `min-height: var(--content-h)` alongside `height: auto` is what
// holds both properties at once, so it is asserted here rather than left to be
// re-broken by the next layout change.
//
// This reads the component source rather than a rendered page because jsdom
// applies no media queries: the rule is only observable in a real browser at a
// real width, and the mocked Playwright suite covers it there.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const STACKED = /@media \(max-width: 63\.9rem\)\s*\{([\s\S]*?)\n {2}\}/;

function stackedBlock(view: string): string {
  const source = readFileSync(resolve(process.cwd(), "src", "lib", "views", view), "utf8");
  const match = STACKED.exec(source);
  expect(match, `${view} has no split-view breakpoint block`).not.toBeNull();
  return match![1];
}

describe("stacked conversation layout", () => {
  it("lets Chat grow while still filling the room the shell gives it", () => {
    const block = stackedBlock("ChatView.svelte");
    expect(block).toMatch(/\.chat \{[\s\S]*?height: auto;/);
    expect(block).toMatch(/\.chat \{[\s\S]*?min-height: var\(--content-h\);/);
    // The floor must never be re-zeroed: that is the exact regression.
    expect(block).not.toMatch(/\.chat \{[\s\S]*?min-height: 0;/);
  });

  it("keeps Build bounded while background work floats as a drawer", () => {
    const block = stackedBlock("BuildView.svelte");
    expect(block).toMatch(/\.build,[\s\S]*?height: var\(--content-h\);/);
    expect(block).toMatch(/\.rail-slot\.drawer \{[\s\S]*?position: fixed;/);
    expect(block).toMatch(/\.rail-slot\.drawer \{[\s\S]*?inset: 0 0 0 auto;/);
  });

  it("uses the same compact composer grammar in Chat and Build", () => {
    for (const view of ["ChatView.svelte", "BuildView.svelte"]) {
      const source = readFileSync(resolve(process.cwd(), "src", "lib", "views", view), "utf8");
      expect(source).toMatch(/\.composer-card \{[\s\S]*?padding: \.55rem \.6rem;/);
      // Wrap, not nowrap. `nowrap` plus a `display: none` per control is how
      // Build came to print "Select a project to start." under a bar with no
      // project picker in it, and how the model control became an empty circle
      // in both composers below 1024px.
      expect(source).toMatch(/\.composer-bar \{ flex-wrap: wrap;/);
      expect(source).toMatch(/\.send \{[\s\S]*?width: 2\.75rem;/);
      expect(source).toMatch(/\.send-label \{ display: none; \}/);
      expect(source).toMatch(/\.shortcut-hint/);
    }
  });

  it("removes Build-only secondary chrome from the default compact surface", () => {
    const source = readFileSync(resolve(process.cwd(), "src", "lib", "views", "BuildView.svelte"), "utf8");
    expect(source).toMatch(/:global\(\.command-pane:not\(\.expanded\)\) \{ display: none; \}/);
    expect(source).toMatch(/\.standing-wide \{ display: none; \}/);
    expect(source).toContain("Auto follows your Permissions.");
    // What gates sending is not secondary chrome. The project picker stays.
    expect(source).not.toMatch(/\.project-picker,[^\n]*display: none/);
  });

  it("keeps the provider logo on the compact model control in both composers", () => {
    for (const view of ["ChatView.svelte", "BuildView.svelte"]) {
      const source = readFileSync(resolve(process.cwd(), "src", "lib", "views", view), "utf8");
      expect(source).toMatch(
        /:global\(\.composer-card \.model-trigger > span:not\(\.provider-logo\)\)/,
      );
      expect(source).not.toMatch(/:global\(\.composer-card \.model-trigger > span\),/);
    }
  });
});
