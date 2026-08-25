import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TasksView from "./TasksView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";
import { resetModels } from "../models.svelte";
import { requestSchedule, takeScheduleRequest } from "../scheduleHandoff";

afterEach(() => { vi.unstubAllGlobals(); resetModels(); takeScheduleRequest(); });

const READY_MODEL = { profile_id: "test-ready", provider: "ollama", model: "test-model", selected: true, configured: true, ready: true, readiness_state: "ready" };

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

  it("preserves task fields and disables all cadences when the model is unready", async () => {
    const stopped = { profile_id: "ollama", provider: "ollama", model: "qwen", selected: true, configured: true, ready: false, readiness_state: "runtime_stopped", readiness_summary: "Ollama is not reachable.", readiness_reason_code: "local_runtime_unreachable", readiness_remediation: "Start Ollama, then check again." };
    stubFetch({ "GET /api/tasks": [], "GET /api/models": { profiles: [stopped], chat_profiles: [stopped] } });
    render(TasksView);
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Keep title" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "Keep instructions" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Create task" })).toBeDisabled());
    expect(screen.getByText("Ollama is not reachable.")).toBeInTheDocument();
    expect(screen.getByLabelText("Task title")).toHaveValue("Keep title");
    expect(screen.getByLabelText("Instructions")).toHaveValue("Keep instructions");
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
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Review release" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "Check every change." } });
    await fireEvent.click(screen.getByRole("button", { name: "Create task" }));

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

    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Use source" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "Read it." } });
    await fireEvent.input(screen.getByLabelText("Attachment path"), { target: { value: "docs/plan.md" } });
    await fireEvent.click(screen.getByRole("button", { name: "Attach" }));
    await fireEvent.click(screen.getByRole("button", { name: "Create task" }));

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
    expect(screen.getByText("Model for each run")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /model for this turn: haiku/i })).toBeInTheDocument();
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
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Plan release" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "   " } });
    const submit = screen.getByRole("button", { name: "Create task" });

    expect(submit).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(/instructions are required/i);
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
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Plan release" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "Prepare the release notes." } });
    await fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "high" } });
    await fireEvent.input(screen.getByLabelText("First run"), { target: { value: "2026-07-14T09:30" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create routine" }));

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
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Watch the build" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "Report any failing job." } });
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
});
