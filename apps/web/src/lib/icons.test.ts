// BUG-37 — the icon set, held to the three things the audit fixed.
//
// The interesting one is uniqueness. `diagnostics` used to be byte-for-byte the
// same clock-with-a-rewind-arrow as `checkpoints`, `capabilities` the same
// ringed circle as `sun`, and `projects` the same folder outline as `folder`.
// At 16px each pair was indistinguishable while meaning entirely different
// things, and nothing would have told us — the type union was complete, every
// name resolved, and the app rendered. This is what tells us.
import { describe, expect, it } from "vitest";
import { ICON_PATHS, ICON_SIZE, type IconName } from "./icons";

describe("the icon set", () => {
  it("draws every declared name", () => {
    for (const [name, paths] of Object.entries(ICON_PATHS)) {
      expect(paths.length, name).toBeGreaterThan(0);
      for (const d of paths) expect(d.trim(), name).not.toBe("");
    }
  });

  it("gives no two unrelated meanings the same glyph", () => {
    const seen = new Map<string, IconName>();
    const collisions: string[] = [];
    for (const [name, paths] of Object.entries(ICON_PATHS) as [IconName, string[]][]) {
      const signature = paths.join("|");
      const previous = seen.get(signature);
      if (previous) collisions.push(`${previous} and ${name}`);
      else seen.set(signature, name);
    }
    expect(collisions).toEqual([]);
  });

  it("keeps the previously colliding pairs apart", () => {
    const distinct = (a: IconName, b: IconName) =>
      expect(ICON_PATHS[a].join("|"), `${a} vs ${b}`).not.toBe(ICON_PATHS[b].join("|"));
    distinct("diagnostics", "checkpoints");
    distinct("capabilities", "sun");
    distinct("projects", "folder");
  });

  it("names one optical size per role rather than seven near-identical numbers", () => {
    expect(Object.keys(ICON_SIZE)).toEqual(["sm", "md", "lg", "xl"]);
    const sizes = Object.values(ICON_SIZE);
    // Strictly ascending, so choosing the next role up always means a bigger icon.
    expect([...sizes].sort((a, b) => a - b)).toEqual(sizes);
  });

  it("starts every path with an absolute move, so the set shares one origin", () => {
    // A relative opening command inherits wherever the previous subpath ended,
    // which makes a glyph render differently depending on the order its paths
    // happen to be listed in.
    for (const [name, paths] of Object.entries(ICON_PATHS)) {
      for (const d of paths) expect(d.trimStart()[0], `${name}: ${d}`).toBe("M");
    }
  });
});
