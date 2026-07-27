import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkInActionView from "./WorkInActionView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WorkInActionView", () => {
  it("shows a route-level loading state while live work is fetched", async () => {
    stubFetchPending();
    render(WorkInActionView);
    const statuses = await screen.findAllByRole("status");
    expect(statuses.some((el) => /loading live work/i.test(el.textContent ?? ""))).toBe(true);
  });

  it("shows a route-level error state when live work cannot load", async () => {
    stubFetch({});
    render(WorkInActionView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load live work/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("shows real subagent assignment, task progress, and waiting schedules", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z",
        illustrative_motion_notice: "Animated pulses indicate visual activity only.",
        nodes: [
          { node_id: "agent:a", node_type: "agent", label: "Researcher", status: "idle", detail: "Draft a plan", progress_percent: null, is_real: true },
          { node_id: "task:t", node_type: "task", label: "Draft a plan", status: "running", detail: "Outline", progress_percent: 40, is_real: true },
          { node_id: "schedule:t", node_type: "schedule", label: "Scheduled work", status: "waiting", detail: "2026-07-16T09:00:00Z", progress_percent: null, is_real: true },
        ],
        edges: [],
      },
    });
    render(WorkInActionView);

    await waitFor(() => expect(screen.getByText("Researcher")).toBeInTheDocument());
    expect(screen.getByText(/Idle · Draft a plan/i)).toBeInTheDocument();
    expect(screen.getByText(/Working · 40% · Outline/i)).toBeInTheDocument();
    expect(screen.getByText(/waiting · 2026-07-16/i)).toBeInTheDocument();
    expect(screen.getByText(/visual-only/i)).toBeInTheDocument();
  });

  // BUG-09 — a run that ended dropped off this page entirely, so the reason it
  // ended was visible nowhere. A blocked run is live work, not a finished one.
  it("says how the last runs ended and keeps approval-blocked work in the active list", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-27T00:00:00Z",
        illustrative_motion_notice: "Animated pulses indicate visual activity only.",
        nodes: [
          { node_id: "task:blocked", node_type: "task", label: "Publish the note", status: "waiting_for_approval", detail: "Waiting for your approval before this run can continue.", progress_percent: null, is_real: true },
          { node_id: "task:failed", node_type: "task", label: "Background agent", status: "failed", detail: "The model was unreachable.", progress_percent: null, is_real: true },
          { node_id: "task:silent", node_type: "task", label: "Nightly sweep", status: "completed", detail: null, progress_percent: null, is_real: true },
        ],
        edges: [],
      },
    });
    render(WorkInActionView);

    await waitFor(() => expect(screen.getByText("Publish the note")).toBeInTheDocument());
    expect(screen.getByText(/Waiting for approval · Waiting for your approval/i)).toBeInTheDocument();
    expect(screen.getByText("How the last runs ended")).toBeInTheDocument();
    expect(screen.getByText(/Failed · The model was unreachable\./i)).toBeInTheDocument();
    expect(screen.getByText(/Done · No reason was recorded for this outcome\./i)).toBeInTheDocument();
  });
});
