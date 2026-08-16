// The Workbench is the default screen. It is a board, not a composer: it must
// answer "what is Raiker doing right now" from the tasks the backend already
// owns, classify them the way the scheduler does, and never become a second send
// path for a prompt.
import { render, screen, waitFor, within } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkbenchView from "./WorkbenchView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";
import { resetModels } from "../models.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  resetModels();
});

const SESSION = {
  session_id: "sess_1",
  title: "Draft the quarterly note",
  status: "active",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-24T00:00:00Z",
  turn_count: 3,
  pinned: false,
  tags: [],
};

function task(partial: Record<string, unknown>) {
  return {
    task_id: "task_1",
    session_id: "sess_inbox_prin_owner",
    status: "running",
    title: "A task",
    objective: "Do the thing",
    current_step: null,
    progress_percent: null,
    created_at: "2026-07-24T00:00:00Z",
    updated_at: "2026-07-24T00:05:00Z",
    completed_at: null,
    summary: null,
    recurrence: null,
    scheduled_at: null,
    project_id: null,
    ...partial,
  };
}

// The three facts the board separates, in the shapes the scheduler produces: a
// run in flight, a repeating task re-armed as `queued` with its next slot, and a
// one-off future run.
const RUNNING = task({ task_id: "t_run", title: "Reindex the code map", status: "running", current_step: "Walking src/" });
const AGENT = task({
  task_id: "t_agent",
  title: "Watch the release branch",
  status: "queued",
  recurrence: "hourly",
  scheduled_at: "2099-01-01T00:00:00Z",
});
const SCHEDULED = task({
  task_id: "t_sched",
  title: "Post the weekly summary",
  status: "queued",
  scheduled_at: "2099-01-01T00:00:00Z",
});

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/sessions": [SESSION],
    "GET /api/tasks": [],
    "GET /api/approvals": [],
    "GET /api/projects": {
      projects: [
        {
          project_id: "proj_1",
          name: "Quarterly note",
          root_subpath: "projects/quarterly-note",
          created_at: "2026-07-01T00:00:00Z",
          session_count: 1,
          selected: true,
          parent_id: null,
          path: "/",
          is_archived: false,
          archived_at: null,
        },
      ],
      active_project_id: "proj_1",
    },
    ...overrides,
  };
}

describe("WorkbenchView", () => {
  it("has no composer at all — starting work is a link to the surface that owns one", async () => {
    stubFetch(routes());
    render(WorkbenchView);

    await waitFor(() => expect(screen.getByText("Running now")).toBeInTheDocument());
    // The removed box: a prompt field, its mode tabs, and its send control.
    expect(screen.queryByLabelText(/what would you like raiker to do/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Build" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start build/i })).not.toBeInTheDocument();
    const start = screen.getByRole("navigation", { name: "Start work" });
    expect(within(start).getByRole("link", { name: /start a conversation/i })).toHaveAttribute(
      "href",
      "#/new-chat",
    );
    expect(within(start).getByRole("link", { name: /start a build/i })).toHaveAttribute("href", "#/build");
    expect(within(start).getByRole("link", { name: /plan a task or agent/i })).toHaveAttribute("href", "#/tasks");
    // The active project is named on the board rather than picked on it.
    expect(within(start).getByText("Quarterly note")).toBeInTheDocument();
  });

  it("separates a run in flight from a standing agent from a scheduled run", async () => {
    stubFetch(routes({ "GET /api/tasks": [RUNNING, AGENT, SCHEDULED] }));
    render(WorkbenchView);

    const running = await screen.findByRole("region", { name: "Running now" });
    const agents = screen.getByRole("region", { name: "Standing agents" });
    const schedules = screen.getByRole("region", { name: "Scheduled runs" });

    expect(within(running).getByText("Reindex the code map")).toBeInTheDocument();
    expect(within(running).getByText("Walking src/")).toBeInTheDocument();
    // An armed task is `queued` with a future slot. Listing it as running was the
    // overcount this classification exists to prevent.
    expect(within(running).queryByText("Watch the release branch")).not.toBeInTheDocument();
    expect(within(running).queryByText("Post the weekly summary")).not.toBeInTheDocument();

    expect(within(agents).getByText("Watch the release branch")).toBeInTheDocument();
    expect(within(agents).getByText("Runs hourly")).toBeInTheDocument();
    expect(within(agents).queryByText("Post the weekly summary")).not.toBeInTheDocument();

    expect(within(schedules).getByText("Post the weekly summary")).toBeInTheDocument();
    expect(within(schedules).queryByText("Watch the release branch")).not.toBeInTheDocument();
  });

  it("says each group is empty rather than leaving a blank card", async () => {
    stubFetch(routes());
    render(WorkbenchView);

    expect(await screen.findByText("Nothing is running.")).toBeInTheDocument();
    expect(screen.getByText("No agent is standing.")).toBeInTheDocument();
    expect(screen.getByText("Nothing is scheduled.")).toBeInTheDocument();
    expect(
      screen.getByText(/Nothing is running, standing, or scheduled/),
    ).toBeInTheDocument();
  });

  it("stops a run at its safe boundary through the governed interrupt", async () => {
    const fetchMock = stubFetch(
      routes({
        "GET /api/tasks": [RUNNING],
        "POST /api/interrupts": { applied: [{ task_id: "t_run", result: "cancelling" }], safe_boundary: true },
      }),
    );
    render(WorkbenchView);

    const running = await screen.findByRole("region", { name: "Running now" });
    await fireEvent.click(within(running).getByRole("button", { name: "Stop" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).endsWith("/api/interrupts")),
      ).toBe(true),
    );
    const body = JSON.parse(
      String(
        fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/interrupts"))?.[1]?.body,
      ),
    );
    expect(body).toMatchObject({ task_id: "t_run", action_type: "cancel" });
    expect(await screen.findByText(/stop at its next safe boundary/)).toBeInTheDocument();
  });

  it("names the decision a blocked run is waiting on and links to it", async () => {
    stubFetch(
      routes({
        "GET /api/tasks": [task({ task_id: "t_block", title: "Apply the patch", status: "waiting_for_approval" })],
      }),
    );
    render(WorkbenchView);

    const running = await screen.findByRole("region", { name: "Running now" });
    expect(
      within(running).getByText("Blocked on a decision you have not made yet."),
    ).toBeInTheDocument();
    expect(within(running).getByRole("link", { name: "Decide" })).toHaveAttribute(
      "href",
      "#/approvals",
    );
  });

  it("counts each actionable runtime configuration gap once", async () => {
    stubFetch(
      routes({
        "GET /api/diagnostics": {
          missing_config: ["No model profile is selected.", "No runtime mode is active."],
          production_ready_local_single_user_runtime: false,
        },
      }),
    );
    render(WorkbenchView);

    const tile = (await screen.findByText("Runtime issues")).closest("article");
    await waitFor(() => expect(tile).toHaveTextContent("2"));
    expect(tile).not.toHaveTextContent("3");
  });

  it("shows a loading state for live status before it is known", async () => {
    stubFetchPending();
    render(WorkbenchView);
    expect(await screen.findAllByText(/loading status/i)).not.toHaveLength(0);
  });

  it("says status is unavailable rather than reporting zeroes", async () => {
    stubFetch({});
    render(WorkbenchView);
    expect(await screen.findByText(/workbench status is unavailable/i)).toBeInTheDocument();
    expect(screen.getAllByText(/no work was started or changed/i)).not.toHaveLength(0);
  });

  it("offers only conversations to resume, never a task's own server-owned session", async () => {
    const fetchMock = stubFetch(routes());
    render(WorkbenchView);

    await waitFor(() => expect(screen.getByText(SESSION.title)).toBeInTheDocument());
    const sessionCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/api/sessions"));
    expect(String(sessionCall?.[0])).toContain("origin=chat");
  });
});
