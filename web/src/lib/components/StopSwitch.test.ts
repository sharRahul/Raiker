// Found live 2026-09-05, walking every destination at four widths.
//
// The STOP switch was full-strength red on every page at every width, forever,
// and it could not say whether pressing it would do anything: the owner pressed
// it, confirmed a dialog about cancelling everything at a safe boundary, waited
// on two API calls, and was told "No active tasks to stop." On a 360px header
// the pill spent about a third of the width saying it.
//
// The two properties this file pins, because they pull against each other:
//
// * **The control never goes away.** The Security Philosophy's "instant stop"
//   is not conditional on Raiker believing something is running, and a stale
//   belief must never be able to remove a control. The button is in the bar and
//   opens the same dialog whether the count is zero or five.
// * **It is only loud when it has something to be loud about.** Colour, the
//   word, and the number are what a running queue earns.
//
// And one thing that follows from both: the count is the same count every other
// surface shows, because it is `isActiveTask` over the same `GET /api/tasks`.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ACTIVE_TASK_STATES } from "../statusMaps";
import { stubFetch } from "../test-helpers";
import StopSwitch from "./StopSwitch.svelte";

afterEach(() => vi.unstubAllGlobals());

const TASKS = "GET /api/tasks";
const IN_FLIGHT = "GET /api/work-in-flight";
const QUIET = { tasks: 0, turns: 0, commands: 0, turn_sessions: [] };

function task(status: string, sessionId = "sess_1"): Record<string, unknown> {
  return {
    task_id: `task_${status}_${sessionId}`,
    session_id: sessionId,
    status,
    title: status,
    created_at: "2026-09-05T00:00:00Z",
  };
}

const stopButton = () => screen.getByRole("button", { name: /Stop all work/ });

describe("the switch when nothing is running", () => {
  it("is quiet: no colour class, no word", async () => {
    stubFetch({ [TASKS]: [task("completed")], [IN_FLIGHT]: QUIET });

    render(StopSwitch);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /nothing is running/ })).toBeTruthy(),
    );
    expect(stopButton().classList.contains("live")).toBe(false);
    expect(stopButton().textContent).not.toContain("STOP");
  });

  it("is still there, and still opens the dialog", async () => {
    stubFetch({ [TASKS]: [], [IN_FLIGHT]: QUIET });

    render(StopSwitch);
    await waitFor(() => expect(stopButton()).toBeTruthy());
    await fireEvent.click(stopButton());

    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
  });

  it("says so immediately, without spending an interrupt to find out", async () => {
    const fetchMock = stubFetch({ [TASKS]: [], [IN_FLIGHT]: QUIET });

    render(StopSwitch);
    await waitFor(() => expect(stopButton()).toBeTruthy());
    await fireEvent.click(stopButton());

    await waitFor(() => expect(screen.getByText("Nothing is running")).toBeTruthy());
    const interrupts = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes("/api/interrupts"),
    );
    expect(interrupts).toHaveLength(0);
  });

  it("offers a re-check rather than making the owner close and reopen", async () => {
    stubFetch({ [TASKS]: [], [IN_FLIGHT]: QUIET });

    render(StopSwitch);
    await waitFor(() => expect(stopButton()).toBeTruthy());
    await fireEvent.click(stopButton());

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Check again" })).toBeTruthy(),
    );
  });
});

describe("the switch when work is running", () => {
  it("turns red and states the count", async () => {
    stubFetch({ [TASKS]: [task("running"), task("queued", "sess_2")], [IN_FLIGHT]: QUIET });

    render(StopSwitch);

    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
    expect(stopButton().textContent).toContain("STOP");
    expect(stopButton().textContent).toContain("2");
  });

  it("names the count in the confirm, so the decision is made against a number", async () => {
    stubFetch({ [TASKS]: [task("running"), task("paused", "sess_2")], [IN_FLIGHT]: QUIET });

    render(StopSwitch);
    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
    await fireEvent.click(stopButton());

    await waitFor(() => expect(screen.getByRole("button", { name: "Stop all" })).toBeTruthy());
    expect(screen.getByRole("dialog").textContent).toContain("2 tasks");
    expect(screen.getByRole("dialog").textContent).toContain("safe boundary");
  });

  it("announces the count politely, outside the button's own label", async () => {
    stubFetch({ [TASKS]: [task("running")], [IN_FLIGHT]: QUIET });

    const { container } = render(StopSwitch);

    await waitFor(() => {
      const region = container.querySelector('[aria-live="polite"]');
      expect(region?.textContent?.trim()).toBe("1 active");
    });
  });

  it("sends one stop for everything, not one interrupt per session", async () => {
    const fetchMock = stubFetch({
      [TASKS]: [task("running", "sess_1"), task("queued", "sess_2")],
      [IN_FLIGHT]: QUIET,
      "POST /api/stop-all": { tasks: [], turns: [], commands: [], failed: [], safe_boundary: true },
      "GET /api/events": [],
    });

    render(StopSwitch);
    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
    await fireEvent.click(stopButton());
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop all" })).toBeTruthy());
    await fireEvent.click(screen.getByRole("button", { name: "Stop all" }));

    await waitFor(() => {
      const stops = fetchMock.mock.calls.filter((call) => String(call[0]).includes("/api/stop-all"));
      expect(stops).toHaveLength(1);
    });
    const interrupts = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes("/api/interrupts"),
    );
    expect(interrupts).toHaveLength(0);
  });
});

// GEP-02 — the owner's decision: Stop reaches everything being performed, not
// only the task list. A chat turn is not a task, and it is the thing an owner
// watching an answer most wants to stop.
describe("the switch reaches work that is not a task", () => {
  it("turns red for an answer being written when no task is running", async () => {
    stubFetch({
      [TASKS]: [],
      [IN_FLIGHT]: { tasks: 0, turns: 1, commands: 0, turn_sessions: ["sess_chat"] },
    });

    render(StopSwitch);

    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
    expect(stopButton().textContent).toContain("1");
  });

  it("names every kind of work in the confirm", async () => {
    stubFetch({
      [TASKS]: [task("running")],
      [IN_FLIGHT]: { tasks: 1, turns: 1, commands: 2, turn_sessions: ["sess_chat"] },
    });

    render(StopSwitch);
    await waitFor(() => expect(stopButton().textContent).toContain("4"));
    await fireEvent.click(stopButton());

    await waitFor(() => expect(screen.getByRole("button", { name: "Stop all" })).toBeTruthy());
    const text = screen.getByRole("dialog").textContent ?? "";
    expect(text).toContain("1 answer being written, 1 task and 2 commands");
    expect(text).toContain("whether or not it reaches outside this machine");
  });

  it("reports what the stop reached, and what it could not", async () => {
    stubFetch({
      [TASKS]: [],
      [IN_FLIGHT]: { tasks: 0, turns: 1, commands: 1, turn_sessions: ["sess_chat"] },
      "POST /api/stop-all": {
        tasks: [],
        turns: [{ session_id: "sess_chat", turn_id: "turn_1" }],
        commands: [],
        failed: [{ kind: "command", run_id: "run_1", reason_code: "command_store_unreadable" }],
        safe_boundary: true,
      },
      "GET /api/events": [],
    });

    render(StopSwitch);
    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
    await fireEvent.click(stopButton());
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop all" })).toBeTruthy());
    await fireEvent.click(screen.getByRole("button", { name: "Stop all" }));

    await waitFor(() =>
      expect(screen.getByText(/Stop applied at the safe boundary to 1 answer being written/)).toBeTruthy(),
    );
    expect(screen.getByRole("alert").textContent).toContain("1 item could not be stopped");
  });

  it("keeps the last known turn count when the in-flight read fails", async () => {
    let calls = 0;
    const mock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/tasks")) {
        return { ok: true, status: 200, json: async () => [] } as Response;
      }
      calls += 1;
      if (calls > 1) return { ok: false, status: 503, json: async () => ({}) } as Response;
      return {
        ok: true,
        status: 200,
        json: async () => ({ tasks: 0, turns: 1, commands: 0, turn_sessions: ["s"] }),
      } as Response;
    });
    vi.stubGlobal("fetch", mock);

    render(StopSwitch);
    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
    await fireEvent.click(stopButton());
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
    expect(stopButton().classList.contains("live")).toBe(true);
  });
});

describe("the count is the product's count", () => {
  it("counts every state the runtime calls unfinished", async () => {
    stubFetch({
      [TASKS]: ACTIVE_TASK_STATES.map((status, index) => task(status, `sess_${index}`)),
    });

    render(StopSwitch);

    await waitFor(() =>
      expect(stopButton().textContent).toContain(String(ACTIVE_TASK_STATES.length)),
    );
  });

  it("counts nothing a finished task contributes", async () => {
    stubFetch({ [TASKS]: [task("completed"), task("failed"), task("cancelled")], [IN_FLIGHT]: QUIET });

    render(StopSwitch);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /nothing is running/ })).toBeTruthy(),
    );
  });

  it("keeps the last known count when a read fails, rather than claiming quiet", async () => {
    // A network hiccup must not be able to say "nothing is running": that is
    // the one thing this control must never get wrong.
    let answered = false;
    const mock = vi.fn(async () => {
      if (answered) return { ok: false, status: 503, json: async () => ({}) } as Response;
      answered = true;
      return {
        ok: true,
        status: 200,
        json: async () => [task("running")],
      } as Response;
    });
    vi.stubGlobal("fetch", mock);

    render(StopSwitch);
    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));

    await fireEvent.click(stopButton());

    // The dialog's own read failed; the button did not quietly go grey.
    await waitFor(() => expect(stopButton().classList.contains("live")).toBe(true));
  });
});
