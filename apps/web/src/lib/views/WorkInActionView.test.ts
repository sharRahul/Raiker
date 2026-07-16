import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkInActionView from "./WorkInActionView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WorkInActionView", () => {
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
});
