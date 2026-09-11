import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  densityGap,
  SHARED_WORK_CONTRACT,
  WORK_MODES,
  WORK_SURFACES,
  workSurface,
} from "./workSurface";

const VIEWS = resolve(process.cwd(), "src", "lib", "views");
const COMPONENTS = resolve(process.cwd(), "src", "lib", "components");
const SHELLS: Record<string, string> = {
  chat: "ChatView.svelte",
  build: "BuildView.svelte",
  design: "DesignView.svelte",
};
/**
 * Where each mode *spends* the density its shell declares. Chat and Build set
 * the gap on the region they own directly; Design's object lives in its own
 * region component (VIS2-20), so that is where its density lands.
 */
const SPENDERS: Record<string, string> = {
  chat: resolve(VIEWS, "ChatView.svelte"),
  build: resolve(VIEWS, "BuildView.svelte"),
  design: resolve(COMPONENTS, "DesignCanvasRegion.svelte"),
};

describe("the shared Work contract (VIS2-21)", () => {
  it("holds every Work mode to the same answers", () => {
    // The contract is what a mode owes whatever it is about. Specialising is
    // not a licence to drop one of these: a Design surface that cannot say
    // which model will answer has not become more itself, it has lost an
    // answer its owner needs.
    expect([...SHARED_WORK_CONTRACT]).toEqual([
      "project",
      "model",
      "posture",
      "attachments",
      "turn-control",
      "palette",
      "states",
    ]);
    for (const mode of WORK_MODES) {
      expect(workSurface(mode).mode).toBe(mode);
    }
  });

  it("gives each mode an object no other mode claims", () => {
    // Two modes about the same thing would mean one of them has no reason to
    // be a separate mode — the exact collapse that made Design a third chat
    // screen before it was promoted.
    const objects = WORK_MODES.map((mode) => WORK_SURFACES[mode].primaryObject);
    expect(new Set(objects).size).toBe(WORK_MODES.length);
    const densities = WORK_MODES.map((mode) => WORK_SURFACES[mode].density);
    expect(new Set(densities).size).toBe(WORK_MODES.length);
  });

  it("makes density a dimension rather than a label", () => {
    // A workbench packs tighter than a canvas, which packs tighter than a
    // transcript. If two of these ever returned the same token the contract
    // would be describing a difference the page does not have.
    const gaps = [densityGap("high"), densityGap("spatial"), densityGap("low")];
    expect(new Set(gaps).size).toBe(3);
    expect(gaps.every((gap) => gap.startsWith("var(--space-"))).toBe(true);
  });

  it("is declared by each surface where it can be read off the page", () => {
    for (const mode of WORK_MODES) {
      const text = readFileSync(resolve(VIEWS, SHELLS[mode]), "utf8");
      const surface = WORK_SURFACES[mode];
      expect(text, `${SHELLS[mode]} does not declare its Work surface`).toContain(
        'data-work-surface={surface.mode}',
      );
      expect(text, `${SHELLS[mode]} does not declare its primary object`).toContain(
        "data-primary-object={surface.primaryObject}",
      );
      expect(text, `${SHELLS[mode]} does not declare its density`).toContain(
        "data-density={surface.density}",
      );
      // Declared from the contract, not restated locally: a literal would let
      // the page and the module disagree.
      expect(text, `${SHELLS[mode]} hard-codes its mode instead of asking`).toContain(
        `workSurface("${surface.mode}")`,
      );
      // The shell declares the density …
      expect(text, `${SHELLS[mode]} does not declare its density as a dimension`).toContain(
        "--surface-gap:${densityGap(surface.density)}",
      );
      // … and the region that holds the object spends it.
      expect(
        readFileSync(SPENDERS[mode], "utf8"),
        `${mode} declares a density nothing spends`,
      ).toMatch(/var\(--surface-gap/);
    }
  });
});
