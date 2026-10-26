import { describe, expect, it } from "vitest";
import { goalTitle, requestGoalDraft, takeGoalDraft } from "./goalHandoff";

describe("QUI-F03 goal handoff", () => {
  it("titles a goal from the request's first line, capitalised and bounded", () => {
    expect(goalTitle("plan my week\nwith gym on Tuesdays")).toBe("Plan my week");
    expect(goalTitle("x".repeat(100))).toHaveLength(80);
  });

  it("is taken once", () => {
    requestGoalDraft({ title: "Plan", objective: "  Plan my week  ", fromTitle: "Week", projectId: null });
    expect(takeGoalDraft()).toEqual({ title: "Plan", objective: "Plan my week", fromTitle: "Week", projectId: null });
    expect(takeGoalDraft()).toBeNull();
  });
});
