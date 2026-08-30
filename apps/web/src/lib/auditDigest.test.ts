import { describe, expect, it } from "vitest";
import { digestEvents, isTurnTrace } from "./auditDigest";

function event(event_type: string, event_id = event_type) {
  return { event_id, event_type };
}

describe("auditDigest", () => {
  it("treats a turn's own phase timeline as trace, not as news", () => {
    for (const type of [
      "prompt_normalised",
      "intent_classified",
      "risk_classified",
      "context_gathered",
      "plan_skipped",
      "model_request_started",
      "verification_completed",
    ]) {
      expect(isTurnTrace(type), type).toBe(true);
    }
  });

  it("treats the turn state machine and the pre-read lookups as trace", () => {
    expect(isTurnTrace("turn_state_changed")).toBe(true);
    expect(isTurnTrace("skills_indexed")).toBe(true);
    expect(isTurnTrace("principal_resolved")).toBe(true);
  });

  it("keeps what actually changed, including anything a turn really did", () => {
    for (const type of [
      "action_executed",
      "action_failed",
      "capability_enabled",
      "capability_decision_mode_set",
      "task_created",
      "checkpoint_created",
      // A resolution that failed is news; the successful one is not.
      "principal_resolution_failed",
    ]) {
      expect(isTurnTrace(type), type).toBe(false);
    }
  });

  it("does not let one turn's trace fill the digest", () => {
    const oneTurn = [
      "model_request_started",
      "skills_indexed",
      "plan_skipped",
      "turn_state_changed",
      "context_gathered",
      "turn_state_changed",
      "risk_classified",
      "intent_classified",
      "turn_state_changed",
      "prompt_normalised",
      "turn_state_changed",
    ].map((type, index) => event(type, `${type}_${index}`));
    const changed = event("capability_enabled");
    expect(digestEvents([...oneTurn, changed])).toEqual([changed]);
  });

  it("caps the digest at the limit it is given", () => {
    const many = Array.from({ length: 30 }, (_unused, index) =>
      event("action_executed", `ev_${index}`),
    );
    expect(digestEvents(many)).toHaveLength(12);
    expect(digestEvents(many, 3)).toHaveLength(3);
  });
});
