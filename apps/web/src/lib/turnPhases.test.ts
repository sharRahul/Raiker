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

  // BUG-53 — each model request is a distinct answer pass. The transcript
  // needs a visible paragraph seam without disturbing token-sized deltas from
  // one streamed response.
  it("separates answer text produced by successive model requests", () => {
    expect(collectText([
      lifecycle("model_request_started"),
      delta("Reading"),
      delta(" the file…"),
      lifecycle("model_request_completed"),
      lifecycle("model_request_started"),
      delta("I found the cause."),
    ])).toBe("Reading the file…\n\nI found the cause.");
  });

  it("does not add a trailing paragraph for a tool-only model request", () => {
    expect(collectText([
      lifecycle("model_request_started"),
      delta("I will inspect that."),
      lifecycle("model_request_started"),
      lifecycle("model_request_completed"),
    ])).toBe("I will inspect that.");
  });

  it("reuses an answer boundary already present in streamed text", () => {
    expect(collectText([
      lifecycle("model_request_started"),
      delta("First response.\n"),
      lifecycle("model_request_started"),
      delta("\nSecond response."),
    ])).toBe("First response.\n\nSecond response.");
  });

  it("summarizes events in plain English", () => {
    expect(summarizeEvent(lifecycle("risk_classified", { risk_level: "high", requires_approval: true })))
      .toMatch(/high.*approval required/i);
  });

  // BUG-52 — a refused call no longer ends the turn, so the transcript has to
  // say the call was refused and say it narrowly. Without the second sentence a
  // reader takes one refusal as a verdict on everything the batch asked for.
  it("reports a per-call policy refusal as the act phase, scoped to that call", () => {
    const refused = lifecycle("model_tool_call_refused", {
      tool_name: "read_file",
      reasons: ["path_outside_workspace"],
    });
    expect(phaseForEvent("model_tool_call_refused")).toBe("act");
    expect(summarizeEvent(refused)).toBe(
      "Policy refused read_file — path_outside_workspace. The other calls in this batch were decided separately.",
    );
  });

  // C6 — the Sources strip is the surface, but the governance record has to say
  // the ledger was written too. An event the runtime streams and the timeline
  // silently drops is the invisible product surface this backlog exists to stop.
  it("reports the source ledger as the act phase, with counts and no content", () => {
    const recorded = lifecycle("turn_sources_recorded", {
      recorded: 2,
      total: 3,
      source_ids: ["s2", "s3"],
      kinds: ["file", "web"],
      tools: ["read_file", "web_fetch"],
    });
    expect(phaseForEvent("turn_sources_recorded")).toBe("act");
    expect(summarizeEvent(recorded)).toBe(
      "Recorded 2 source(s) this turn (file, web); 3 in total.",
    );
  });
});
