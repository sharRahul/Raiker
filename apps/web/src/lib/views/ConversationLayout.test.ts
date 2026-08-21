// The stacked (below split-view) layout of the two conversation surfaces.
//
// Chat and Build pin their composer to the bottom of the room the shell gives
// them by sizing from `--content-h`. Below the split-view breakpoint they switch
// to `height: auto`, so the transcript — and, in Build, the rail stacked under
// the composer — can take the space they need instead of being trapped in a
// short inner scroller.
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

  it("lets Build grow while still filling the room the shell gives it", () => {
    const block = stackedBlock("BuildView.svelte");
    // Build's grid still releases its own height so the rail can stack under the
    // composer; the floor lives on the column that holds the composer.
    expect(block).toMatch(/\.build,[\s\S]*?height: auto;/);
    expect(block).toMatch(/\.main \{\s*min-height: var\(--content-h\);/);
  });
});
