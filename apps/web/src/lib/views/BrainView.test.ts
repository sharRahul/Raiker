import { render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import BrainView from "./BrainView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BrainView", () => {
  it("shows a route-level loading state while the graph is fetched", async () => {
    stubFetchPending();
    render(BrainView);
    const statuses = await screen.findAllByRole("status");
    expect(statuses.some((el) => /loading the brain graph/i.test(el.textContent ?? ""))).toBe(true);
  });

  it("shows a route-level error state when the graph cannot load", async () => {
    stubFetch({});
    render(BrainView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load the brain graph/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

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
    expect(screen.getByText(/does not display hidden model reasoning/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Knowledge Map" })).toBeInTheDocument();
    expect(screen.getAllByText("Researcher").length).toBeGreaterThan(0);
    expect(screen.getByText("Workspace sources")).toBeInTheDocument();
    expect(screen.queryByText("Work in Action")).not.toBeInTheDocument();
  });
});
