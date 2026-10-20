import { describe, expect, it } from "vitest";
import type { GoalView } from "./generated/apiContract";
import { budgetLine, goalBadge, goalButtons, goalRefusal, homeGoalGroups, profileSummary, stepProgress } from "./goalPresentation";

function goal(over: Partial<GoalView>): GoalView {
  return {
    goal_id: "goal_1", title: "Trip", objective: "", project_id: null, model_profile: "anthropic-hosted", model: "claude-haiku-4-5-20251001", status: "running", reason: "", reason_text: "",
    reason_detail: "", revision: 3, allowed_actions: ["pause", "confirm", "stop"], created_at: "", updated_at: "",
    accepted_at: null, settled_at: null, criteria: [],
    steps: [
      { step_id: "s1", title: "a", instruction: "", surface: "chat", depends_on: [], criterion_ids: [], state: "done", reason: "", task_id: "t", task_status: "completed", task_summary: null },
      { step_id: "s2", title: "b", instruction: "", surface: "chat", depends_on: ["s1"], criterion_ids: [], state: "running", reason: "", task_id: "u", task_status: "running", task_summary: null },
    ],
    profile: null, profile_current: true, profile_source: "active",
    budget: { max_step_runs: 10, step_runs: 2, max_cost_usd: 5, spent_usd: 0.125, unpriced_models: [] },
    providers_used: [], providers_outside_profile: [], events: [],
    ...over,
  };
}

describe("goal presentation", () => {
  it("counts finished steps rather than inventing a percentage", () => {
    expect(stepProgress(goal({}))).toBe("1 of 2 steps finished");
  });

  it("draws only the buttons the server allows, in a fixed order", () => {
    expect(goalButtons(goal({ allowed_actions: ["stop", "pause", "confirm"] }))).toEqual(["pause", "stop"]);
    expect(goalButtons(goal({ allowed_actions: ["edit", "accept", "archive"] }))).toEqual(["accept", "archive"]);
  });

  it("groups Home by what needs the owner, what moves and what finished", () => {
    const groups = homeGoalGroups([
      goal({ goal_id: "a", status: "waiting", reason: "needs_decision" }),
      goal({ goal_id: "b", status: "running" }),
      goal({ goal_id: "c", status: "completed" }),
      goal({ goal_id: "d", status: "draft" }),
      goal({ goal_id: "e", status: "waiting", reason: "profile_blocks_model" }),
      goal({ goal_id: "f", status: "partial" }),
    ]);
    expect(groups.needsYou.map((g) => g.goal_id)).toEqual(["a", "e", "f"]);
    expect(groups.moving.map((g) => g.goal_id)).toEqual(["b"]);
    expect(groups.finished.map((g) => g.goal_id)).toEqual(["c"]);
  });

  it("states a profile's boundary in one sentence", () => {
    const base = { profile_id: "x", version: 1, name: "P", template: "balanced", allowed_providers: [], max_step_runs: 10, max_cost_usd: null, created_at: "" };
    expect(profileSummary({ ...base, allow_local: true, allow_hosted: false, memory_to_hosted: false })).toBe(
      "Only models on this machine; nothing leaves this machine; up to 10 step runs per goal.",
    );
    expect(profileSummary({ ...base, allow_local: true, allow_hosted: true, memory_to_hosted: false, allowed_providers: ["anthropic"], max_cost_usd: 5 })).toBe(
      "Local and hosted models (anthropic); personal memory stays off hosted models; up to 10 step runs, at most $5.00 per goal.",
    );
    expect(profileSummary(null)).toBe("No execution profile is chosen.");
  });

  it("reads the budget from the server's counts", () => {
    expect(budgetLine(goal({}))).toBe("2 of 10 step runs · $0.13 of $5.00 spent");
  });

  it("explains a refusal, with the named model when the profile blocks it", () => {
    expect(goalRefusal("profile_blocks_model:openai (hosted)")).toBe(
      "The execution profile does not allow a model this goal's work would use: openai (hosted). Change the profile in Settings or your models.",
    );
    expect(goalRefusal("no_execution_profile")).toMatch(/Settings → Execution profiles/);
    expect(goalRefusal("something_else")).toBe("That did not work. (something_else)");
  });

  it("badges every state", () => {
    expect(goalBadge("waiting")).toEqual({ variant: "needs-approval", label: "Waiting" });
    expect(goalBadge("partial").label).toBe("Partly done");
  });
});
