import { describe, expect, it } from "vitest";
import { evidenceStrength, memoryEvidence, proposalEvidence } from "./memoryEvidence";

describe("memoryEvidence (UX-MEM-04)", () => {
  it("says who wrote it when the owner did, with no strength to judge", () => {
    expect(memoryEvidence({ source: "agent", provenance: { source_type: "user_ui" }, confidence: 1 }).label).toBe("You wrote this");
    expect(memoryEvidence({ source: "human_correction", provenance: {}, confidence: 1 }).label).toBe("You corrected this");
    const imported = memoryEvidence({ source: "agent", provenance: { source_type: "user_import" }, confidence: 1 });
    expect(imported.label).toBe("Imported by you");
    expect(imported.strength).toBeNull();
    expect(imported.why).toMatch(/only as reliable as the file/);
  });

  it("bands an inferred record's confidence and never shows the decimal", () => {
    const approved = memoryEvidence({
      source: "human_approved_proposal",
      provenance: { source_type: "memory_proposal" },
      confidence: 0.62,
    });
    expect(approved.label).toBe("Some evidence · approved by you");
    expect(approved.why).toMatch(/not measured probabilities/);
    expect(approved.why).not.toMatch(/0\.62|62%/);
    expect(memoryEvidence({ source: "agent", provenance: {}, confidence: 0.3 }).label).toBe("Weak evidence · written by Raiker");
  });

  it("uses the same bands for proposals", () => {
    expect(evidenceStrength(0.85)).toBe("strong");
    expect(evidenceStrength(0.6)).toBe("some");
    expect(evidenceStrength(0.59)).toBe("weak");
    expect(proposalEvidence(0.97).label).toBe("Strong evidence");
  });
});
