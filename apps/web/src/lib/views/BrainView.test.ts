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
    expect(statuses.some((el) => /loading the knowledge graph/i.test(el.textContent ?? ""))).toBe(true);
  });

  it("shows a route-level error state when the graph cannot load", async () => {
    stubFetch({});
    render(BrainView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load the knowledge graph/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("renders runtime records in a force-directed graph with graph controls", async () => {
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

    await waitFor(() => expect(screen.getByRole("button", { name: /Draft a plan, task record/i })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Knowledge Map" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Researcher, agent record/i })).toBeInTheDocument();
    expect(screen.getByRole("application", { name: /interactive force-directed knowledge graph/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Global" })).toHaveAttribute("class", expect.stringContaining("active"));
    expect(screen.getByRole("button", { name: "Local" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add workspace source" })).toBeInTheDocument();
  });

  it("shows the governed starter graph and opens force settings", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z",
        illustrative_motion_notice: "Visual motion only.",
        nodes: [{ node_id: "principal:p", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: true }],
        edges: [],
      },
    });
    render(BrainView);

    expect(await screen.findByText("Build your knowledge graph")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Workspace, workspace record/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add first source, source record/i })).toBeInTheDocument();
    screen.getByRole("button", { name: "Graph settings" }).click();
    expect(await screen.findByRole("complementary", { name: "Graph settings" })).toBeInTheDocument();
    expect(screen.getByText("Centre force")).toBeInTheDocument();
    expect(screen.getByText("Always alive")).toBeInTheDocument();
  });
});
