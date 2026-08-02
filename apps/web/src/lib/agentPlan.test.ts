// B6 — the plan arrives as an untrusted stream payload, so it is validated
// before it is rendered. These cover the two things that go wrong when it is
// not: a plan that renders as blank steps, and a status the CSS has no rule for.
import { describe, expect, it } from "vitest";
import { hasSteps, planFromEvent, planFromPayload } from "./agentPlan";
import type { StreamEvent } from "./apiTypes";

function event(eventType: string, payload: Record<string, unknown>): StreamEvent {
  return { kind: "lifecycle", text: "", event_type: eventType, payload, response: null };
}

describe("reading a plan out of a live turn", () => {
  it("takes the plan from an agent_plan_updated event", () => {
    const plan = planFromEvent(
      event("agent_plan_updated", {
        session_id: "sess_1",
        steps: [
          { title: "Read the code", status: "completed" },
          { title: "Make the change", status: "in_progress" },
        ],
        updated_at: "2026-08-02T00:00:00Z",
      }),
    );
    expect(plan?.steps.map((step) => step.status)).toEqual(["completed", "in_progress"]);
    expect(plan?.session_id).toBe("sess_1");
  });

  it("ignores every other lifecycle event", () => {
    expect(planFromEvent(event("context_gathered", { steps: [{ title: "x" }] }))).toBeNull();
  });

  it("ignores text deltas even if they carry a payload", () => {
    expect(
      planFromEvent({
        kind: "text_delta",
        text: "hello",
        event_type: "agent_plan_updated",
        payload: { steps: [{ title: "x", status: "pending" }] },
        response: null,
      }),
    ).toBeNull();
  });

  it("drops steps with no title rather than rendering an empty row", () => {
    const plan = planFromPayload({
      steps: [{ title: "  ", status: "pending" }, { title: "Real", status: "pending" }],
    });
    expect(plan?.steps).toHaveLength(1);
    expect(plan?.steps[0].title).toBe("Real");
  });

  it("falls back to pending for a status the checklist cannot draw", () => {
    const plan = planFromPayload({ steps: [{ title: "Odd", status: "halfway" }] });
    expect(plan?.steps[0].status).toBe("pending");
  });

  it("returns null when nothing usable survives validation", () => {
    expect(planFromPayload({ steps: [] })).toBeNull();
    expect(planFromPayload({ steps: "not a list" })).toBeNull();
    expect(planFromPayload({})).toBeNull();
  });

  it("says when a fetched plan is worth showing", () => {
    expect(hasSteps(null)).toBe(false);
    expect(hasSteps({ session_id: "s", steps: [] })).toBe(false);
    expect(hasSteps({ session_id: "s", steps: [{ title: "A", status: "pending" }] })).toBe(true);
  });
});
