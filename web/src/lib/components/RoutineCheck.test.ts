import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, setToken } from "../api";
import { taskView } from "../test-helpers";
import RoutineCheck from "./RoutineCheck.svelte";

/**
 * DEC-12 steps 6 and 8 — "will this routine run?" asked before the run that
 * would have failed, and how long one run may take.
 */
afterEach(() => {
  setToken(null);
  vi.restoreAllMocks();
});

describe("RoutineCheck", () => {
  it("lists what the doctor found, with a way to fix what is not fine", async () => {
    setToken("t");
    const doctor = vi.spyOn(api, "taskDoctor").mockResolvedValue({
      task_id: "task_1",
      state: "blocked",
      checked_at: "2026-10-05T10:00:00Z",
      checks: [
        { key: "scheduler", label: "The scheduler", state: "ok", detail: "Running.", href: null },
        { key: "schedule", label: "Its schedule", state: "blocked", detail: "This routine is paused.", href: "#/tasks?task=task_1" },
        { key: "model", label: "Its model", state: "unknown", detail: "Could not be read.", href: null },
      ],
    });
    render(RoutineCheck, { task: taskView({ task_id: "task_1", recurrence: "daily" }) });
    await fireEvent.click(screen.getByRole("button", { name: "Will it run?" }));
    const panel = await screen.findByTestId("routine-check");
    expect(doctor).toHaveBeenCalledWith("task_1");
    expect(panel).toHaveTextContent("Something on record will stop its next run.");
    expect(panel).toHaveTextContent("Will not run");
    expect(panel).toHaveTextContent("Unknown");
    expect(screen.getAllByRole("link", { name: "Fix it" })).toHaveLength(1);
  });

  it("saves a run limit inside its bounds and refuses one outside them", async () => {
    setToken("t");
    vi.spyOn(api, "taskDoctor").mockResolvedValue({ task_id: "task_1", state: "ok", checked_at: "", checks: [] });
    const set = vi.spyOn(api, "setTaskRunLimit").mockResolvedValue(taskView({ task_id: "task_1", max_run_minutes: 30 }));
    const changed = vi.fn();
    render(RoutineCheck, { task: taskView({ task_id: "task_1", recurrence: "daily" }), onChanged: changed });
    await fireEvent.click(screen.getByRole("button", { name: "Will it run?" }));
    const input = await screen.findByLabelText("Run limit in minutes");
    expect(input).toHaveValue(60);

    await fireEvent.input(input, { target: { value: "900" } });
    // The browser's own constraint check stops the button; the form's guard is
    // what a submit that got past it meets.
    await fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(await screen.findByText(/from 1 to 720/)).toBeInTheDocument();
    expect(set).not.toHaveBeenCalled();

    await fireEvent.input(input, { target: { value: "30" } });
    await fireEvent.click(screen.getByRole("button", { name: "Save limit" }));
    await waitFor(() => expect(set).toHaveBeenCalledWith("task_1", 30));
    expect(await screen.findByText("Each run now stops after 30 minutes.")).toBeInTheDocument();
    expect(changed).toHaveBeenCalled();
  });
});
