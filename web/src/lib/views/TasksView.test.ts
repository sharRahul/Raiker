import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TasksView from "./TasksView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";
import { resetModels } from "../models.svelte";
import { requestSchedule, takeScheduleRequest } from "../scheduleHandoff";

afterEach(() => { vi.unstubAllGlobals(); resetModels(); takeScheduleRequest(); });

const READY_MODEL = { profile_id: "test-ready", provider: "ollama", model: "test-model", selected: true, configured: true, ready: true, readiness_state: "ready" };

/**
 * COMPOSER-10 — planning work is one instruction now, with the rest behind
 * Details. These two helpers are what changed for every case below: the form's
 * Title/Instructions pair became a single field, and Priority, Repeat, First
 * run and Parent work are opened rather than always on screen.
 */
async function instruct(text: string): Promise<void> {
  await fireEvent.input(screen.getByLabelText("What should Raiker do?"), {
    target: { value: text },
  });
}

async function openDetails(): Promise<void> {
  const toggle = screen.getByRole("button", { expanded: false, name: /Runs|Once|Daily|Hourly|Weekly|Every/ });
  await fireEvent.click(toggle);
}

describe("TasksView", () => {
  it("opens on Once when Chat's /schedule asked for it, and creates nothing", async () => {
    const fetchMock = stubFetch({
      "GET /api/tasks": [],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
    });
    requestSchedule();
    render(TasksView);

    // The command arranges the control it names, and stops there.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Once" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    expect(screen.getByRole("button", { name: "Task" })).toHaveAttribute("aria-pressed", "false");
    expect(
      fetchMock.mock.calls.filter(([url, init]) =>
        String(url).includes("/api/tasks") && (init as RequestInit | undefined)?.method === "POST",
      ),
    ).toHaveLength(0);
  });

  it("opens on an immediate task when nothing asked otherwise", async () => {
    stubFetch({
      "GET /api/tasks": [],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
    });
    render(TasksView);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Task" })).toHaveAttribute("aria-pressed", "true"),
    );
  });

  it("offers Run now for an unscheduled queued task and invokes only the explicit run route", async () => {
    const task = {
      task_id: "task_ready", session_id: "sess_inbox", status: "queued",
      title: "Review deliberate work", objective: "Wait for the owner.",
      current_step: null, progress_percent: null,
      created_at: "2026-08-11T09:00:00Z", updated_at: "2026-08-11T09:00:00Z",
      completed_at: null, summary: null, project_id: null,
      scheduled_at: null, recurrence: null, reminder_at: null, parent_task_id: null,
    };
    const fetchMock = stubFetch({
      "GET /api/tasks": [task],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
      "POST /api/tasks/task_ready/run": { ...task, scheduled_at: "2026-08-11T09:01:00Z" },
    });
    render(TasksView);

    expect(await screen.findByText(/Ready when you run it/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks/task_ready/run",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  // C11 — background work used to finish into a status line. Each task now runs
  // its cycles in a conversation of its own, and the card is where the owner
  // reaches it.
  it("links to the task's own conversation once it has run", async () => {
    const task = {
      task_id: "task_nightly", session_id: "sess_inbox", status: "queued",
      title: "Overnight research", objective: "Summarise what changed.",
      current_step: null, progress_percent: null,
      created_at: "2026-08-11T09:00:00Z", updated_at: "2026-08-11T09:00:00Z",
      completed_at: null, summary: null, project_id: null,
      scheduled_at: null, recurrence: "daily", reminder_at: null, parent_task_id: null,
      thread_session_id: "sess_thread_1", thread_turns: 3,
    };
    stubFetch({
      "GET /api/tasks": [task],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
    });
    render(TasksView);

    const link = await screen.findByRole("link", { name: /Thread/ });
    expect(link).toHaveAttribute("href", "#/new-chat?session=sess_thread_1");
    expect(link).toHaveTextContent("3");
  });

  it("does not offer a thread that has nothing in it yet", async () => {
    // A link to an empty transcript is a dead end, and a routine that has not
    // run has one.
    const task = {
      task_id: "task_new", session_id: "sess_inbox", status: "queued",
      title: "Overnight research", objective: "Summarise what changed.",
      current_step: null, progress_percent: null,
      created_at: "2026-08-11T09:00:00Z", updated_at: "2026-08-11T09:00:00Z",
      completed_at: null, summary: null, project_id: null,
      scheduled_at: null, recurrence: "daily", reminder_at: null, parent_task_id: null,
      thread_session_id: "sess_thread_2", thread_turns: 0,
    };
    stubFetch({
      "GET /api/tasks": [task],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
    });
    render(TasksView);

    await screen.findByRole("heading", { name: "Overnight research" });
    expect(screen.queryByRole("link", { name: /Thread/ })).toBeNull();
  });

  it("preserves task fields and disables all cadences when the model is unready", async () => {
    const stopped = { profile_id: "ollama", provider: "ollama", model: "qwen", selected: true, configured: true, ready: false, readiness_state: "runtime_stopped", readiness_summary: "Ollama is not reachable.", readiness_reason_code: "local_runtime_unreachable", readiness_remediation: "Start Ollama, then check again." };
    stubFetch({ "GET /api/tasks": [], "GET /api/models": { profiles: [stopped], chat_profiles: [stopped] } });
    render(TasksView);
    await instruct("Keep instructions");
    await waitFor(() => expect(screen.getByRole("button", { name: /Create task/ })).toBeDisabled());
    expect(screen.getByText("Ollama is not reachable.")).toBeInTheDocument();
    // The draft survives the refusal, which is the point: a model that is not
    // ready must not cost the owner what they typed.
    expect(screen.getByLabelText("What should Raiker do?")).toHaveValue("Keep instructions");
  });
  it("creates an immediate task with its own configured model pair", async () => {
    const fetchMock = stubFetch({
      "GET /api/tasks": [],
      "GET /api/models": {
        profiles: [],
        chat_profiles: [
          { profile_id: "anthropic", provider: "anthropic", model: "haiku", selected: true, configured: true, ready: true, readiness_state: "ready" },
          { profile_id: "anthropic", provider: "anthropic", model: "opus", selected: false, configured: true, ready: true, readiness_state: "ready" },
        ],
      },
      "POST /api/tasks": {},
    });
    render(TasksView);
    await screen.findByText("No work queued");

    await fireEvent.click(await screen.findByRole("button", { name: /model for this turn/i }));
    await fireEvent.click(screen.getByRole("menuitemradio", { name: /opus/i }));
    await instruct("Check every change.");
    await fireEvent.click(screen.getByRole("button", { name: /Create task/ }));

    const post = await waitFor(() => fetchMock.mock.calls.find(([, init]) => init?.method === "POST"));
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      model_profile: "anthropic",
      model: "opus",
    });
  });

  it("carries attachments into scheduled work and renders them outside the instructions", async () => {
    const task = {
      task_id: "task_files", session_id: "sess_inbox", status: "queued",
      title: "Review source", objective: "Check the attached source.",
      current_step: null, progress_percent: null,
      created_at: "2026-08-01T10:00:00Z", updated_at: "2026-08-01T10:00:00Z",
      completed_at: null, summary: null, project_id: null,
      scheduled_at: "2026-08-02T10:00:00Z",
      attachments: [{ type: "path", path: "docs/source.md" }],
    };
    const fetchMock = stubFetch({ "GET /api/tasks": [task], "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] }, "POST /api/tasks": task });
    render(TasksView);
    await screen.findByRole("heading", { name: "Review source" });

    const attachment = screen.getByText("docs/source.md");
    expect(attachment.closest(".task-attachments")).not.toBeNull();
    expect(attachment.closest(".task-title")).toBeNull();

    await instruct("Read it.");
    await fireEvent.click(screen.getByRole("button", { name: "Add to this turn" }));
    await fireEvent.click(await screen.findByRole("menuitem", { name: "Upload a file" }));
    await fireEvent.input(await screen.findByLabelText("Attachment path"), { target: { value: "docs/plan.md" } });
    await fireEvent.click(screen.getByRole("button", { name: "Attach" }));
    await fireEvent.click(screen.getByRole("button", { name: /Create task/ }));

    const post = await waitFor(() => fetchMock.mock.calls.find(([, init]) => init?.method === "POST"));
    expect(JSON.parse(String(post?.[1]?.body)).attachments).toEqual([
      { type: "path", path: "docs/plan.md" },
    ]);
  });

  it("lets a schedule retain an exact configured model", async () => {
    stubFetch({ "GET /api/tasks": [], "GET /api/models": { profiles: [], chat_profiles: [
      { profile_id: "anthropic", provider: "anthropic", model: "haiku", selected: true, configured: true, ready: true, readiness_state: "ready" },
    ] } });
    render(TasksView);
    await screen.findByText("No work queued");
    await fireEvent.click(screen.getByRole("button", { name: "Once" }));
    // COMPOSER-10 — the model sits in the composer bar as it does on every
    // other Work surface, rather than under a label of its own. What a schedule
    // captures it *onto* is said by the primary action and the timing line.
    expect(screen.getByRole("button", { name: /model for this turn: haiku/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Schedule task/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { expanded: false, name: /Once — pick a time/ })).toBeInTheDocument();
  });

  it("shows a route-level loading state while tasks are fetched", async () => {
    stubFetchPending();
    render(TasksView);
    expect(await screen.findByText(/loading tasks/i)).toBeInTheDocument();
  });

  it("shows a route-level error state when the task list cannot load", async () => {
    stubFetch({});
    render(TasksView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load tasks/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("does not create a task when instructions contain only whitespace", async () => {
    const fetchMock = stubFetch({ "GET /api/tasks": [] });
    render(TasksView);

    await waitFor(() => expect(screen.getByText("No work queued")).toBeInTheDocument());
    await instruct("   ");
    const submit = screen.getByRole("button", { name: /Create task/ });

    // One field, so one refusal: nothing to write means nothing to create, and
    // the button says so by being disabled rather than by an error under a
    // second field that no longer exists.
    expect(submit).toBeDisabled();
    await fireEvent.click(submit);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("creates a daily routine with its saved schedule", async () => {
    const fetchMock = stubFetch({
      "GET /api/tasks": [],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
      "POST /api/tasks": {
        task_id: "task_1",
        session_id: "sess_inbox",
        status: "queued",
        title: "Plan release",
        objective: "Prepare the release notes.",
        current_step: null,
        progress_percent: null,
        created_at: "2026-07-13T00:00:00Z",
        updated_at: "2026-07-13T00:00:00Z",
        completed_at: null,
        summary: null,
        priority: "high",
        scheduled_at: "2026-07-14T09:30:00Z",
        recurrence: null,
        reminder_at: null,
        parent_task_id: null,
      },
    });
    render(TasksView);

    await waitFor(() => expect(screen.getByText("No work queued")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Routine" }));
    await instruct("Prepare the release notes.");
    await openDetails();
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Plan release" } });
    await fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "high" } });
    await fireEvent.input(screen.getByLabelText("First run"), { target: { value: "2026-07-14T09:30" } });
    await fireEvent.click(screen.getByRole("button", { name: /Create routine/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks",
      expect.objectContaining({ method: "POST" }),
    ));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      title: "Plan release",
      description: "Prepare the release notes.",
      priority: "high",
      scheduled_at: new Date("2026-07-14T09:30").toISOString(),
      recurrence: "daily",
    });
  });

  it("scopes the work list to a linked session", async () => {
    const fetchMock = stubFetch({ "GET /api/tasks": [] });
    render(TasksView, { sessionId: "sess_linked" });

    await screen.findByText("No work queued");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks?session_id=sess_linked",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
  });

  // Backlog #10 — four cadences existed in the runtime and the composer offered
  // one of them, so an hourly or weekly routine could only be made from Build's
  // side panel. The chip now names the shape and the select names the interval.
  it("creates an hourly routine anchored to the first run the owner picked", async () => {
    const fetchMock = stubFetch({
      "GET /api/tasks": [],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
      "POST /api/tasks": {
        task_id: "task_hourly",
        session_id: "sess_inbox_owner",
        title: "Watch the build",
        objective: "Report any failing job.",
        status: "queued",
        created_at: "2026-07-14T08:00:00Z",
        updated_at: "2026-07-14T08:00:00Z",
        priority: "normal",
        scheduled_at: "2026-07-14T09:30:00Z",
        recurrence: "hourly",
        reminder_at: null,
        parent_task_id: null,
      },
    });
    render(TasksView);

    await waitFor(() => expect(screen.getByText("No work queued")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Routine" }));
    await instruct("Report any failing job.");
    await openDetails();
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Watch the build" } });
    await fireEvent.input(screen.getByLabelText("First run"), { target: { value: "2026-07-14T09:30" } });
    await fireEvent.change(screen.getByLabelText("Repeat"), { target: { value: "hourly" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create routine" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks",
      expect.objectContaining({ method: "POST" }),
    ));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      title: "Watch the build",
      description: "Report any failing job.",
      priority: "normal",
      scheduled_at: new Date("2026-07-14T09:30").toISOString(),
      recurrence: "hourly",
    });
  });
});


// Reverse approval link: you should learn a task is blocked where you are
// looking at the task, not only by going to the decision queue.
describe("TasksView blocked-on-approval pointer", () => {
  const TASK = {
    task_id: "task_1",
    session_id: "sess_alpha",
    status: "running",
    title: "Publish the release note",
    objective: "Draft and file it.",
    current_step: null,
    progress_percent: null,
    created_at: "2026-07-24T00:00:00Z",
    updated_at: "2026-07-24T00:01:00Z",
    completed_at: null,
    summary: null,
    priority: "normal",
    scheduled_at: null,
    recurrence: null,
    reminder_at: null,
    parent_task_id: null,
    project_id: null,
  };

  it("says a task is blocked and links to the decision that blocks it", async () => {
    stubFetch({
      "GET /api/tasks": [TASK],
      "GET /api/approvals": [
        { approval_id: "appr_1", session_id: "sess_alpha", is_expired: false },
      ],
    });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );

    expect(await screen.findByText(/waiting on a decision/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review it/i })).toHaveAttribute(
      "href",
      "#/approvals?session=sess_alpha",
    );
  });

  it("counts multiple blocking decisions", async () => {
    stubFetch({
      "GET /api/tasks": [TASK],
      "GET /api/approvals": [
        { approval_id: "appr_1", session_id: "sess_alpha", is_expired: false },
        { approval_id: "appr_2", session_id: "sess_alpha", is_expired: false },
      ],
    });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );
    expect(await screen.findByText(/waiting on 2 decisions/i)).toBeInTheDocument();
  });

  it("shows no pointer when the pending decision belongs to another session", async () => {
    stubFetch({
      "GET /api/tasks": [TASK],
      "GET /api/approvals": [
        { approval_id: "appr_1", session_id: "sess_other", is_expired: false },
      ],
    });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/waiting on/i)).not.toBeInTheDocument();
  });

  it("keeps a blocked run in the open list, says why, and still offers Stop", async () => {
    stubFetch({
      "GET /api/tasks": [
        { ...TASK, status: "waiting_for_approval", summary: "Waiting for your approval before this run can continue." },
      ],
      "GET /api/approvals": [],
    });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );

    expect(screen.getByText("waiting for approval")).toBeInTheDocument();
    expect(screen.getByText(/waiting for your approval before this run can continue/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
  });

  // BUG-39 — approving now signals the host directly, so the card must stop
  // presenting the manual button as the way to get a granted run moving.
  it("names automatic continuation and keeps Continue now as the recovery path", async () => {
    stubFetch({
      "GET /api/tasks": [{ ...TASK, status: "waiting_for_approval" }],
      "GET /api/approvals": [],
    });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );

    expect(screen.getByText("Approving continues this run automatically.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue now" })).toHaveClass("btn-ghost");
  });

  // BUG-09 — "failed" was the entire story the finished list told. The reason
  // the backend recorded is the point of the row.
  it("states why a finished run ended", async () => {
    stubFetch({
      "GET /api/tasks": [
        { ...TASK, task_id: "task_failed", status: "failed", summary: "The model was unreachable." },
        { ...TASK, task_id: "task_silent", title: "Nightly sweep", status: "cancelled", summary: "  " },
      ],
      "GET /api/approvals": [],
    });
    render(TasksView);

    await waitFor(() => expect(screen.getByText("Finished work")).toBeInTheDocument());
    expect(screen.getByText("The model was unreachable.")).toBeInTheDocument();
    expect(screen.getByText("No reason was recorded for this outcome.")).toBeInTheDocument();
  });

  it("keeps the task list usable when approvals cannot be read", async () => {
    stubFetch({ "GET /api/tasks": [TASK] });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/waiting on/i)).not.toBeInTheDocument();
  });

  // Backlog #23 — a parent that owns its children's outcomes could not say how
  // a child should work, so a task whose job is "read the repository, make the
  // change, run the tests" ran with the assistant's method for it.
  it("says which work runs as Build, and stays quiet about the default", async () => {
    stubFetch({
      "GET /api/tasks": [
        { ...TASK, task_id: "task_read", title: "Read the issue", surface: "chat" },
        { ...TASK, task_id: "task_fix", title: "Fix the failing test", surface: "build" },
      ],
      "GET /api/approvals": [],
    });
    render(TasksView);

    await screen.findByRole("heading", { name: "Fix the failing test" });
    // Said once, on the one that is not the default. VIS-14 — it is a chip in
    // the shared work-meta line now rather than "· Build" appended to a
    // sentence, so it reads the same way as a thread's project chip.
    expect(screen.getAllByText("Build")).toHaveLength(1);
  });

  // The control is offered only where Build's method can work: a repository.
  // COMPOSER-10 moved it into Details, so it is opened rather than always on
  // screen — the offer is still conditional on the project.
  it("offers the working method only inside a project", async () => {
    stubFetch({ "GET /api/tasks": [], "GET /api/approvals": [] });
    const { unmount } = render(TasksView);
    await screen.findByLabelText("What should Raiker do?");
    await openDetails();
    expect(screen.queryByRole("group", { name: "How to work" })).not.toBeInTheDocument();
    unmount();

    stubFetch({ "GET /api/tasks": [], "GET /api/approvals": [] });
    render(TasksView, { projectId: "proj_1" });
    await screen.findByLabelText("What should Raiker do?");
    await openDetails();
    expect(screen.getByRole("group", { name: "How to work" })).toBeInTheDocument();
  });

  it("plans work with one instruction rather than a form of eight controls", async () => {
    // COMPOSER-10 — asking Raiker to do something in Chat takes one field.
    // Asking it to do the same thing later took ten, which taught the owner
    // that scheduling is a more administrative act than asking. It is not.
    stubFetch({ "GET /api/tasks": [], "GET /api/approvals": [] });
    render(TasksView);

    await screen.findByLabelText("What should Raiker do?");
    for (const gone of ["Priority", "Parent work", "Repeat", "Task title"]) {
      expect(screen.queryByLabelText(gone)).not.toBeInTheDocument();
    }
    // And the timing is still legible while the details are closed.
    expect(screen.getByRole("button", { expanded: false, name: /Runs now/ })).toBeInTheDocument();
  });

  it("files the task under a title derived from the instruction", async () => {
    const fetchMock = stubFetch({
      "GET /api/tasks": [],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
      "POST /api/tasks": {},
    });
    render(TasksView);

    await screen.findByText("No work queued");
    await instruct("Summarise security news. Flag anything urgent.");
    await fireEvent.click(screen.getByRole("button", { name: /Create task/ }));

    const post = await waitFor(() =>
      fetchMock.mock.calls.find(([, init]) => init?.method === "POST"),
    );
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      title: "Summarise security news",
      description: "Summarise security news. Flag anything urgent.",
    });
  });
  // ── BUG-299 — a task's attempts have an address ──────────────────────────

  const TASK_ROW = {
    task_id: "task_1",
    session_id: "sess_inbox_owner",
    status: "completed",
    title: "Nightly digest",
    objective: "Summarise the day",
    current_step: null,
    progress_percent: null,
    created_at: "2026-09-15T08:00:00Z",
    updated_at: "2026-09-15T09:05:00Z",
    completed_at: null,
    summary: "Digest sent.",
    project_id: null,
  };

  const TASK_DETAIL = {
    task: TASK_ROW,
    approvals: [],
    truncated: false,
    attempts: [
      {
        index: 0,
        kind: "record",
        started_at: "2026-09-15T08:00:00Z",
        ended_at: null,
        outcome: "recorded",
        summary: "Filed.",
        approval_id: null,
        events: [
          {
            event_id: "evt_1",
            event_type: "task_created",
            timestamp: "2026-09-15T08:00:00Z",
            actor: "task_manager",
            detail: "Filed.",
            turn_id: null,
            session_id: "sess_inbox_owner",
          },
        ],
      },
      {
        index: 1,
        kind: "run",
        started_at: "2026-09-15T09:00:00Z",
        ended_at: "2026-09-15T09:05:00Z",
        outcome: "failed",
        summary: "The provider refused.",
        approval_id: null,
        events: [
          {
            event_id: "evt_2",
            event_type: "task_started",
            timestamp: "2026-09-15T09:00:00Z",
            actor: "task_scheduler",
            detail: "This cycle started.",
            turn_id: null,
            session_id: "sess_inbox_owner",
          },
          {
            event_id: "evt_3",
            event_type: "task_failed",
            timestamp: "2026-09-15T09:05:00Z",
            actor: "task_manager",
            detail: "The provider refused.",
            turn_id: null,
            session_id: "sess_inbox_owner",
          },
        ],
      },
    ],
  };

  it("opens one task's attempts at its own address, newest first", async () => {
    stubFetch({
      "GET /api/tasks": [TASK_ROW],
      "GET /api/approvals": [],
      "GET /api/tasks/task_1": TASK_DETAIL,
    });
    render(TasksView, { props: { taskId: "task_1" } });

    // The heading is the task, and the lead counts the attempts rather than
    // repeating the status the badge already carries.
    await screen.findByRole("heading", { name: "Nightly digest", level: 3 });
    expect(screen.getByText("1 attempt · 1 did not complete.")).toBeInTheDocument();
    // The run states what settled it, and the stated reason is the row.
    expect(screen.getByRole("heading", { name: "Attempt 1", level: 4 })).toBeInTheDocument();
    expect(screen.getAllByText("The provider refused.").length).toBeGreaterThan(0);
    // The board is still under it — following a link never costs the page.
    expect(screen.getByLabelText("What should Raiker do?")).toBeInTheDocument();
  });

  it("says a task is not this account's rather than showing an empty history", async () => {
    stubFetch({
      "GET /api/tasks": [],
      "GET /api/approvals": [],
      "GET /api/tasks/task_missing": { __status: 404, detail: { reason_code: "task_not_found" } },
    });
    render(TasksView, { props: { taskId: "task_missing" } });

    await screen.findByText("That task is not on this account's board.");
  });

  it("links every task on the board to its own history", async () => {
    stubFetch({ "GET /api/tasks": [TASK_ROW], "GET /api/approvals": [] });
    render(TasksView);

    const link = await screen.findByRole("link", { name: "Nightly digest" });
    expect(link).toHaveAttribute("href", "#/tasks?task=task_1");
  });
  // BUG-278 — the same composer grammar as asking a question.
  //
  // Task creation used to carry its own model picker, its own environment badge
  // and its own capacity chip, in the layout it had before the shared shell
  // existed — so a person who had learned the composer in Chat met a different
  // arrangement of the same controls when they scheduled the same work.
  // COMPOSER-10 rebuilt it on `Composer.svelte`; this is what stops it drifting
  // back.
  it("composes a task with the same controls Chat composes a question with", async () => {
    stubFetch({
      "GET /api/tasks": [],
      "GET /api/approvals": [],
      "GET /api/models": { profiles: [READY_MODEL], chat_profiles: [READY_MODEL] },
    });
    render(TasksView);

    // One instruction, not a form.
    await screen.findByLabelText("What should Raiker do?");
    // The two menus every Work composer carries, under the names they carry
    // everywhere else.
    expect(screen.getByRole("button", { name: "Add to this turn" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tools" })).toBeInTheDocument();
    // The one context line, rather than a separate environment badge and
    // capacity chip of this surface's own.
    expect(screen.getByRole("button", { name: /^Context for this turn:/ })).toBeInTheDocument();
    // And the model control is the shared picker, not a select of its own.
    expect(screen.getByRole("button", { name: /^Model for this turn:/ })).toBeInTheDocument();
    // The one control planning needs that asking does not, collapsed until
    // asked for — and still stating what was chosen while it is closed.
    expect(screen.getByRole("button", { expanded: false, name: /Runs now/ })).toBeInTheDocument();
  });
});
