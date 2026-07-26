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

  it("loads checkpoints scoped to a linked session", async () => {
    const fetchMock = stubFetch({ "GET /api/checkpoints": [] });
    render(CheckpointsView, { sessionId: "sess_alpha" });

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("session_id=sess_alpha"))).toBe(true);
    });
    expect(screen.getByLabelText("Filter by session id")).toHaveValue("sess_alpha");
  });

  it("keeps a manual session filter when the active project changes", async () => {
    const fetchMock = stubFetch({ "GET /api/checkpoints": CHECKPOINTS });
    const { rerender } = render(CheckpointsView, {
      props: { projectId: "proj_a", sessionId: "sess_route" },
    });

    await waitFor(() => expect(screen.getByLabelText("Filter by session id")).toHaveValue("sess_route"));
    await fireEvent.input(screen.getByLabelText("Filter by session id"), {
      target: { value: "sess_manual" },
    });
    await rerender({ projectId: "proj_b", sessionId: "sess_route" });

    expect(screen.getByLabelText("Filter by session id")).toHaveValue("sess_manual");
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some((call) => {
          const url = String(call[0]);
          return url.includes("session_id=sess_manual") && url.includes("project_id=proj_b");
        }),
      ).toBe(true);
    });
  });
});

// ── Restore preflight ─────────────────────────────────────────────────────
// Restoring is a funnel, not a button. The preflight reads a server-computed,
// metadata-only plan; this view must never perform or claim a restore.
describe("CheckpointsView restore preflight", () => {
  const PLAN = {
    status: "restore_plan",
    checkpoint_id: "cp_1",
    session_id: "sess_alpha",
    checkpoint_created_at: "2026-07-17T10:00:00Z",
    can_execute: true,
    requires_approval: true,
    files: [
      {
        workspace_path: "notes/brief.md",
        op: "restore_content",
        pre_image_sha256: "abc",
        pre_image_size: 120,
        current_sha256: "def",
        current_size: 200,
        changed: true,
        changed_by_other_principal: false,
      },
    ],
    restore_content_count: 1,
    delete_count: 0,
    skip_count: 0,
    changed_count: 1,
    touches_other_principal: false,
  };

  it("shows the affected files and says reading the plan changed nothing", async () => {
    stubFetch({
      "GET /api/checkpoints": CHECKPOINTS,
      "GET /api/checkpoints/cp_1/restore-plan": PLAN,
    });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    expect(await screen.findByText("notes/brief.md")).toBeInTheDocument();
    expect(screen.getByText(/rewinds every workspace file changed after this checkpoint/i)).toBeInTheDocument();
    expect(screen.getByText(/it is a preview computed from stored metadata/i)).toBeInTheDocument();
    expect(screen.getByText(/this panel cannot start a restore/i)).toBeInTheDocument();
  });

  it("names a cross-principal escalation before anything is requested", async () => {
    stubFetch({
      "GET /api/checkpoints": CHECKPOINTS,
      "GET /api/checkpoints/cp_1/restore-plan": {
        ...PLAN,
        touches_other_principal: true,
        files: [{ ...PLAN.files[0], changed_by_other_principal: true }],
      },
    });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/cross-principal escalation/i);
    expect(screen.getAllByText(/last changed by a different principal/i).length).toBeGreaterThan(0);
  });

  it("withholds the request instructions until the impact is acknowledged", async () => {
    stubFetch({
      "GET /api/checkpoints": CHECKPOINTS,
      "GET /api/checkpoints/cp_1/restore-plan": PLAN,
    });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    expect(await screen.findByText(/confirm you have read the impact/i)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByText(/raises it as a governed approval/i)).toBeInTheDocument();
  });

  it("reports a failed preflight instead of an empty plan", async () => {
    stubFetch({ "GET /api/checkpoints": CHECKPOINTS });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    expect(await screen.findByText(/preflight unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/to rewrite/i)).not.toBeInTheDocument();
  });
});
