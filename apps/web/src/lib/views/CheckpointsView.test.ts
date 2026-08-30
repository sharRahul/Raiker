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

// ── Rewind preflight (B18: the funnel is now `RewindPanel`) ─────────────────────────────────────────────────────
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
    expect(screen.getByText(/puts every workspace file changed after this point back as it was/i)).toBeInTheDocument();
    expect(screen.getByText(/computed from stored metadata and changed nothing/i)).toBeInTheDocument();
    expect(screen.getByText(/this panel never performs a rewind/i)).toBeInTheDocument();
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

  it("withholds the request until the impact is acknowledged", async () => {
    stubFetch({
      "GET /api/checkpoints": CHECKPOINTS,
      "GET /api/checkpoints/cp_1/restore-plan": PLAN,
    });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    expect(await screen.findByText(/confirm you have read the impact/i)).toBeInTheDocument();
    const request = screen.getByRole("button", { name: /request this rewind/i });
    expect(request).toBeDisabled();
    await fireEvent.click(screen.getByRole("checkbox"));
    expect(request).toBeEnabled();
    expect(screen.getByText(/raises a governed approval/i)).toBeInTheDocument();
  });

  // BUG-230 — the rewind. The panel asks for it and never performs one: the
  // server recomputes the plan, raises an approval and returns its id.
  it("raises a governed approval and says nothing has changed yet", async () => {
    stubFetch({
      "GET /api/checkpoints": CHECKPOINTS,
      "GET /api/checkpoints/cp_1/restore-plan": PLAN,
      "POST /api/checkpoints/cp_1/restore": {
        status: "approval_required",
        approval_id: "appr_abc123",
        action_id: "act_abc123",
        checkpoint_id: "cp_1",
        critical: false,
        executes_action: false,
        restore_content_count: 1,
        delete_count: 0,
        skip_count: 0,
      },
    });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));
    await screen.findByText(/confirm you have read the impact/i);
    await fireEvent.click(screen.getByRole("checkbox"));
    await fireEvent.click(screen.getByRole("button", { name: /request this rewind/i }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/raised as approval/i);
    expect(status).toHaveTextContent(/nothing has changed yet/i);
  });

  it("reports a failed preflight instead of an empty plan", async () => {
    stubFetch({ "GET /api/checkpoints": CHECKPOINTS });
    render(CheckpointsView);
    await waitFor(() => expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument());
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    expect(await screen.findByText(/preflight unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/to rewrite/i)).not.toBeInTheDocument();
  });

  // B18 — "nothing to rewind" is an answer, not a form to fill in. Before this
  // the panel rendered the whole funnel — the reminders, the acknowledgement
  // and a permanently disabled button — around a change that did not exist.
  it("answers an empty plan instead of rendering a funnel nobody can finish", async () => {
    stubFetch({
      "GET /api/checkpoints": CHECKPOINTS,
      "GET /api/checkpoints/cp_1/restore-plan": {
        ...PLAN,
        files: [],
        restore_content_count: 0,
        delete_count: 0,
        skip_count: 0,
        changed_count: 0,
      },
    });
    render(CheckpointsView);
    await waitFor(() =>
      expect(screen.getByLabelText(/checkpoint cp_1 would change/i)).toBeInTheDocument(),
    );
    await fireEvent.click(screen.getByLabelText(/checkpoint cp_1 would change/i));

    expect(await screen.findByText(/a rewind would change nothing/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /request this rewind/i })).toBeNull();
    expect(screen.queryByText(/before you ask for this/i)).toBeNull();
  });
});
