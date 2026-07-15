import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TasksView from "./TasksView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

describe("TasksView", () => {
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
});
