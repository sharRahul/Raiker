// B6 — the checklist is the one place a long change says where it is. It has to
// read correctly without colour (a status word per step), report progress
// honestly, and stay a statement rather than a control.
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PlanChecklist from "./PlanChecklist.svelte";
import type { AgentPlan } from "../apiTypes";

const PLAN: AgentPlan = {
  session_id: "sess_1",
  steps: [
    { title: "Read the failing test", status: "completed" },
    { title: "Fix the boundary check", status: "in_progress" },
    { title: "Re-run the suite", status: "pending" },
    { title: "Publish the note", status: "blocked", note: "needs a key" },
  ],
};

describe("PlanChecklist", () => {
  it("lists every step with its status named, not only coloured", () => {
    render(PlanChecklist, { plan: PLAN });
    for (const step of PLAN.steps) expect(screen.getByText(step.title)).toBeInTheDocument();
    expect(screen.getByText("in progress")).toBeInTheDocument();
    expect(screen.getByText("blocked")).toBeInTheDocument();
  });

  it("reports progress as completed-over-total rather than a guess", () => {
    render(PlanChecklist, { plan: PLAN });
    expect(screen.getByText("1 of 4 done")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Plan progress" })).toHaveAttribute(
      "aria-valuenow",
      "25",
    );
  });

  it("says how many steps are blocked, so a stall is visible", () => {
    render(PlanChecklist, { plan: PLAN });
    expect(screen.getByText("1 step is blocked.")).toBeInTheDocument();
  });

  it("names the current step when collapsed", () => {
    render(PlanChecklist, { plan: PLAN, collapsed: true });
    expect(screen.getByText(/Working on: Fix the boundary check/)).toBeInTheDocument();
    expect(screen.queryByText("Re-run the suite")).not.toBeInTheDocument();
  });

  it("shows a step's note", () => {
    render(PlanChecklist, { plan: PLAN });
    expect(screen.getByText("needs a key")).toBeInTheDocument();
  });

  it("renders nothing for an empty plan rather than an empty card", () => {
    const { container } = render(PlanChecklist, { plan: { session_id: "s", steps: [] } });
    expect(container.querySelector(".plan")).toBeNull();
  });

  it("offers no control that could change a step", () => {
    // The plan is written by the governed `update_plan` tool. The only button
    // here collapses the card; anything else would be an ungoverned edit.
    render(PlanChecklist, { plan: PLAN });
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveAttribute("aria-controls", "plan-steps");
  });
});
