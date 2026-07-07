import { describe, expect, it } from "vitest";
import {
  capabilityDescription,
  capabilityLabel,
  DECISION_MODE_COPY,
  DECISION_MODES,
  isDecisionMode,
} from "./capabilityModel";

describe("capability copy", () => {
  it("labels known capabilities with friendly names", () => {
    expect(capabilityLabel("shell_execution")).toBe("Shell commands");
    expect(capabilityLabel("hosted_model_runtime")).toBe("Hosted models");
    expect(capabilityLabel("vector_embedding_runtime")).toBe("Vector embeddings");
  });

  it("never hides an unknown capability — falls back to a humanised name", () => {
    expect(capabilityLabel("brand_new_capability")).toBe("Brand new capability");
    expect(capabilityDescription("brand_new_capability")).toBe("Governed capability.");
  });

  it("keeps honest descriptions for fail-closed sensitive domains", () => {
    expect(capabilityDescription("finance_runtime").toLowerCase()).toContain("fails closed");
    expect(capabilityDescription("email_runtime").toLowerCase()).toContain("never transmits");
  });
});

describe("decision modes", () => {
  it("exposes exactly the four canonical modes with ask as the default copy", () => {
    expect([...DECISION_MODES]).toEqual(["ask", "allow", "auto", "deny"]);
    expect(DECISION_MODE_COPY.ask.hint.toLowerCase()).toContain("default");
  });

  it("validates decision mode strings", () => {
    expect(isDecisionMode("ask")).toBe(true);
    expect(isDecisionMode("deny")).toBe(true);
    expect(isDecisionMode("always_allow")).toBe(false);
    expect(isDecisionMode(undefined)).toBe(false);
  });
});
