import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tasks = vi.fn();
const interrupt = vi.fn();
const events = vi.fn();

vi.mock("./api", () => ({
  api: { tasks: (...a: unknown[]) => tasks(...a), interrupt: (...a: unknown[]) => interrupt(...a), events: (...a: unknown[]) => events(...a) },
  ApiError: class ApiError extends Error {
    constructor(readonly status: number) {
      super("err");
    }
  },
}));

describe("StopSwitch", () => {
  beforeEach(() => {
    tasks.mockReset();
    interrupt.mockReset();
    events.mockReset();
  });

  it("issues a governed safe-boundary cancel-all for active tasks and renders the events", async () => {
    tasks.mockResolvedValue([
      { task_id: "task_1", session_id: "sess_1", status: "running" },
      { task_id: "task_2", session_id: "sess_1", status: "queued" },
    ]);
    interrupt.mockResolvedValue({ applied: [{ task_id: "task_1", result: "ok" }, { task_id: "task_2", result: "ok" }], safe_boundary: true });
    events.mockResolvedValue([
      { event_id: "e1", session_id: "sess_1", turn_id: "turn_1", event_type: "interrupt_received", actor: "x", timestamp: "t", risk_level: null, summary: null },
      { event_id: "e2", session_id: "sess_1", turn_id: "turn_1", event_type: "safe_boundary_reached", actor: "x", timestamp: "t", risk_level: null, summary: null },
      { event_id: "e3", session_id: "sess_1", turn_id: "turn_1", event_type: "task_cancelled", actor: "x", timestamp: "t", risk_level: null, summary: null },
    ]);

    const { default: StopSwitch } = await import("./StopSwitch.svelte");
    render(StopSwitch);

    await fireEvent.click(screen.getByRole("button", { name: /stop all tasks/i }));
    await fireEvent.click(screen.getByRole("button", { name: /stop at safe boundary/i }));

    // One interrupt call for the single affected session, cancel-all at safe boundary.
    expect(interrupt).toHaveBeenCalledTimes(1);
    expect(interrupt).toHaveBeenCalledWith(
      expect.objectContaining({ session_id: "sess_1", all: true, action_type: "cancel" }),
    );

    expect(await screen.findByText(/Requested cancellation of 2 active tasks/i)).toBeInTheDocument();
    expect(await screen.findByText("interrupt_received")).toBeInTheDocument();
    expect(await screen.findByText("task_cancelled")).toBeInTheDocument();
  });

  it("reports when there are no active tasks to stop", async () => {
    tasks.mockResolvedValue([{ task_id: "t", session_id: "s", status: "completed" }]);
    const { default: StopSwitch } = await import("./StopSwitch.svelte");
    render(StopSwitch);
    await fireEvent.click(screen.getByRole("button", { name: /stop all tasks/i }));
    await fireEvent.click(screen.getByRole("button", { name: /stop at safe boundary/i }));
    expect(await screen.findByText(/No active tasks to stop/i)).toBeInTheDocument();
    expect(interrupt).not.toHaveBeenCalled();
  });
});
