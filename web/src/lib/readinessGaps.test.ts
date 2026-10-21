import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { KNOWN_GAPS, readinessGaps } from "./readinessGaps";

describe("readinessGaps", () => {
  it("names a missing default model plainly and links to Models", () => {
    expect(readinessGaps(["No model profile is selected."], true)).toEqual([
      { id: "gap-0", title: "No default model is chosen.", action: { label: "Choose a model", href: "#/models" } },
    ]);
  });

  it("keeps the runtime's own sentence for a gap it has no plainer wording for", () => {
    const [row] = readinessGaps(["No acting principal is available."], false);
    expect(row.title).toBe("No acting principal is available.");
    expect(row.action).toMatchObject({ label: "Open diagnostics", href: "#/observe?tab=diagnostics" });
  });

  it("gives one row per gap, never a count", () => {
    expect(readinessGaps(["No model profile is selected.", "No runtime mode is active."], false)).toHaveLength(2);
  });

  it("still says something when the runtime is not ready and names no gap", () => {
    expect(readinessGaps([], false)).toEqual([
      expect.objectContaining({ title: "Raiker is not ready to run work." }),
    ]);
    expect(readinessGaps([], true)).toEqual([]);
  });

  it("matches only sentences the runtime still writes", () => {
    // A reworded gap in the runtime must fail here, not silently lose its fix.
    const source = readFileSync(
      join(import.meta.dirname, "..", "..", "..", "raiker", "control", "dashboard_parts", "models.py"),
      "utf8",
    );
    for (const sentence of Object.keys(KNOWN_GAPS)) {
      expect(source, sentence).toContain(`"${sentence}"`);
    }
  });
});
