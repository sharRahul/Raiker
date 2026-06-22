import { describe, expect, it } from "vitest";
import type { StreamEvent } from "./apiTypes";
import { collectText, groupPhases, phaseForEvent, summarizeEvent } from "./turnPhases";

function lifecycle(eventType: string, payload: Record<string, unknown> = {}): StreamEvent {
  return { kind: "lifecycle", text: "", event_type: eventType, payload, response: null };
}
function delta(text: string): StreamEvent {
  return { kind: "text_delta", text, event_type: "", payload: {}, response: null };
}

describe("turnPhases", () => {
  it("maps lifecycle event types to the four governed phases", () => {
    expect(phaseForEvent("intent_classified")).toBe("gather");
    expect(phaseForEvent("plan_created")).toBe("plan");
    expect(phaseForEvent("model_request_started")).toBe("act");
    expect(phaseForEvent("verification_completed")).toBe("verify");
    expect(phaseForEvent("policy_decision")).toBeNull();
  });

  it("groups events into ordered, non-empty phase rows", () => {
    const events = [
      lifecycle("model_request_started", { provider: "mock", model: "test" }),
      lifecycle("intent_classified", { intent: "qa", confidence: 0.9 }),
      lifecycle("verification_completed", { status: "ok" }),
      delta("ignored here"),
    ];
    const rows = groupPhases(events);
    expect(rows.map((r) => r.phase)).toEqual(["gather", "act", "verify"]);
  });

  it("collects streamed text deltas in order", () => {
    expect(collectText([delta("Hel"), lifecycle("intent_classified"), delta("lo")])).toBe("Hello");
  });

  it("summarizes events in plain English", () => {
    expect(summarizeEvent(lifecycle("risk_classified", { risk_level: "high", requires_approval: true })))
      .toMatch(/high.*approval required/i);
  });
});
