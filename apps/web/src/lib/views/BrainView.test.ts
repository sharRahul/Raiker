import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import BrainView from "./BrainView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BrainView", () => {
  it("shows real runtime nodes and labels visual motion as illustrative", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z",
        illustrative_motion_notice: "Animated pulses indicate visual activity only; every node and connection is stored runtime data.",
        nodes: [
          { node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true },
          { node_id: "task:t", node_type: "task", label: "Draft a plan", status: "running", detail: "Write outline", progress_percent: 40, is_real: true },
          { node_id: "agent:a", node_type: "agent", label: "Researcher", status: "idle", detail: "Draft a plan", progress_percent: null, is_real: true },
        ],
        edges: [{ source: "principal:p", target: "task:t", relationship: "tracks", is_active: true }],
      },
    });
    render(BrainView);

    await waitFor(() => expect(screen.getAllByText("Draft a plan").length).toBeGreaterThan(0));
    expect(screen.getByText(/visual activity only/i)).toBeInTheDocument();
    expect(screen.getAllByText("Researcher").length).toBeGreaterThan(0);
    expect(screen.getByText("Workspace sources")).toBeInTheDocument();
    expect(screen.queryByText("Work in Action")).not.toBeInTheDocument();
  });
});
