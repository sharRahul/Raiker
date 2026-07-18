// Checkpoints is a recorder timeline: every entry names its session/turn/task
// context and says plainly that it is snapshot metadata only — nothing on this
// page can restore or change state.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CheckpointsView from "./CheckpointsView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const CHECKPOINTS = [
  {
    checkpoint_id: "cp_1",
    session_id: "sess_alpha",
    turn_id: "turn_9",
    task_id: null,
    checkpoint_type: "turn_completed",
    created_at: "2026-07-17T10:00:00Z",
    summary: "Draft saved after the plan review turn.",
    last_event_id: "ev_100",
    can_restore_state: true,
    can_restore_files: false,
  },
  {
    checkpoint_id: "cp_2",
    session_id: "sess_alpha",
    turn_id: null,
    task_id: "task_7",
    checkpoint_type: "task_boundary",
    created_at: "2026-07-17T11:00:00Z",
    summary: null,
    last_event_id: null,
    can_restore_state: false,
    can_restore_files: false,
  },
];

describe("CheckpointsView", () => {
  it("shows a route-level loading state while checkpoints are fetched", async () => {
    stubFetchPending();
    render(CheckpointsView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading checkpoints/i);
  });

  it("shows a route-level error state when checkpoints cannot load", async () => {
    stubFetch({});
    render(CheckpointsView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load checkpoints/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("renders a timeline with session, turn, and task context — metadata only", async () => {
    stubFetch({ "GET /api/checkpoints": CHECKPOINTS });
    render(CheckpointsView);

    await waitFor(() => expect(screen.getByText(/draft saved after the plan review turn/i)).toBeInTheDocument());
    // Every entry states its non-restoring nature in plain text.
    expect(screen.getAllByText("Snapshot metadata only").length).toBe(2);
    // Context: the grouped session heading plus per-entry turn/task references.
    expect(screen.getByText(/sess_alp/)).toBeInTheDocument();
    expect(screen.getByText(/turn_9/)).toBeInTheDocument();
    expect(screen.getByText(/task_7/)).toBeInTheDocument();
    // No implied restore action anywhere.
    expect(screen.queryByRole("button", { name: /restore/i })).toBeNull();
  });

  it("filters by checkpoint type without refetching", async () => {
    stubFetch({ "GET /api/checkpoints": CHECKPOINTS });
    render(CheckpointsView);

    await waitFor(() => expect(screen.getByText(/draft saved/i)).toBeInTheDocument());
    await fireEvent.change(screen.getByLabelText("Filter by type"), {
      target: { value: "task_boundary" },
    });
    await waitFor(() => expect(screen.queryByText(/draft saved/i)).toBeNull());
    expect(screen.getByText(/task_7/)).toBeInTheDocument();
  });

  it("applies the session filter through the API", async () => {
    const fetchMock = stubFetch({ "GET /api/checkpoints": CHECKPOINTS });
    render(CheckpointsView);

    await waitFor(() => expect(screen.getByText(/draft saved/i)).toBeInTheDocument());
    await fireEvent.input(screen.getByLabelText("Filter by session id"), {
      target: { value: "sess_alpha" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some((c) => String(c[0]).includes("session_id=sess_alpha")),
      ).toBe(true);
    });
  });
});
