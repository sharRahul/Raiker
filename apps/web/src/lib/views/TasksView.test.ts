import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TasksView from "./TasksView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("TasksView", () => {
  it("shows a route-level loading state while tasks are fetched", async () => {
    stubFetchPending();
    render(TasksView);
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/loading tasks/i);
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
    await fireEvent.click(screen.getByRole("button", { name: "Daily routine" }));
    await fireEvent.input(screen.getByLabelText("Task title"), { target: { value: "Plan release" } });
    await fireEvent.input(screen.getByLabelText("Instructions"), { target: { value: "Prepare the release notes." } });
    await fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "high" } });
    await fireEvent.input(screen.getByLabelText("Start time"), { target: { value: "2026-07-14T09:30" } });
    await fireEvent.click(screen.getByRole("button", { name: "Create daily routine" }));

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

  it("keeps the task list usable when approvals cannot be read", async () => {
    stubFetch({ "GET /api/tasks": [TASK] });
    render(TasksView);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Publish the release note" })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/waiting on/i)).not.toBeInTheDocument();
  });
});
