// PA-D06 — Work → Goals draws what the server sends: its state, its reason, its
// allowed actions and its profile, never a control the state does not offer.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import GoalsView from "./GoalsView.svelte";
import { stubFetch } from "../test-helpers";
import { requestGoalDraft } from "../goalHandoff";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const PROFILE = {
  profile_id: "xprof_1", version: 1, name: "Balanced", template: "balanced", allow_local: true, allow_hosted: true,
  allowed_providers: [], memory_to_hosted: false, max_step_runs: 10, max_cost_usd: null, created_at: "",
};

const GOAL = {
  goal_id: "goal_1", title: "Plan the trip", objective: "", project_id: null, status: "waiting", reason: "needs_decision",
  reason_text: "A step is waiting for your decision", reason_detail: "", revision: 4,
  allowed_actions: ["pause", "confirm", "stop"], created_at: "", updated_at: "", accepted_at: "", settled_at: null,
  criteria: [{ criterion_id: "c1", text: "Itinerary exists", mandatory: true, validator: "steps_finish", evidence_kind: null, evidence_ref: null, evidence_note: null, verified_at: null }],
  steps: [{ step_id: "s1", title: "Research", instruction: "x", surface: "chat", depends_on: [], criterion_ids: ["c1"], state: "waiting", reason: "needs_decision", task_id: "task_1", task_status: "waiting_for_approval", task_summary: null }],
  profile: PROFILE, profile_current: true, profile_source: "active",
  budget: { max_step_runs: 10, step_runs: 1, max_cost_usd: null, spent_usd: 0, unpriced_models: [] },
  providers_used: [], providers_outside_profile: [], events: [],
};

describe("GoalsView", () => {
  it("says no profile is chosen and routes to Settings", async () => {
    stubFetch({ "GET /api/goals": { goals: [], archived: [], active_profile: null } });
    render(GoalsView);
    await waitFor(() => expect(screen.getByText(/No execution profile yet/)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Choose one in Settings" })).toHaveAttribute("href", "#/settings?tab=execution-profiles");
    expect(await screen.findByText("No goals yet")).toBeInTheDocument();
  });

  it("shows a waiting goal's reason, its task link and only the actions it allows", async () => {
    stubFetch({
      "GET /api/goals": { goals: [GOAL], archived: [], active_profile: PROFILE },
      "GET /api/goals/goal_1": GOAL,
    });
    render(GoalsView);
    await fireEvent.click(await screen.findByRole("button", { name: /Plan the trip/ }));
    await waitFor(() => expect(screen.getByTestId("goal-detail")).toBeInTheDocument());
    expect(screen.getAllByText(/A step is waiting for your decision/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Open its task" })).toHaveAttribute("href", "#/tasks?task=task_1");
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Accept plan" })).toBeNull();
  });

  it("asks once more before Stop", async () => {
    const fetch = stubFetch({
      "GET /api/goals": { goals: [GOAL], archived: [], active_profile: PROFILE },
      "GET /api/goals/goal_1": GOAL,
      "POST /api/goals/goal_1/stop": { ok: true, steps_done: 0, steps_stopped: 1, tasks_stopped: 1, goal: { ...GOAL, status: "stopped", allowed_actions: ["archive"], reason: "", reason_text: "" } },
    });
    render(GoalsView);
    await fireEvent.click(await screen.findByRole("button", { name: /Plan the trip/ }));
    await fireEvent.click(await screen.findByRole("button", { name: "Stop goal" }));
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/stop"))).toBe(false);
    await fireEvent.click(screen.getByRole("button", { name: "Stop every step now" }));
    await waitFor(() => expect(screen.getByText(/1 running task was stopped/)).toBeInTheDocument());
  });

  it("opens a goal started from Chat with the form filled in and asks only for what is missing", async () => {
    requestGoalDraft({ title: "Plan my week", objective: "Plan my week with gym on Tuesdays", fromTitle: "Week planning", projectId: null });
    stubFetch({ "GET /api/goals": { goals: [], archived: [], active_profile: PROFILE } });
    render(GoalsView);
    expect(await screen.findByText(/Filled in from “Week planning”\. Add how you will know it is done/)).toBeInTheDocument();
    expect(screen.getByLabelText("Outcome")).toHaveValue("Plan my week");
    expect(screen.getByLabelText("Step 1 instruction")).toHaveValue("Plan my week with gym on Tuesdays");
    expect(screen.getByLabelText("Criterion 1 text")).toHaveValue("");
  });
});
