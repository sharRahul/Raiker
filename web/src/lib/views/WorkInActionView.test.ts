import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkInActionView from "./WorkInActionView.svelte";
import { stubFetch, stubFetchPending } from "../test-helpers";

/**
 * REM-LIVE — the animated floor is a choice now, and the list is the default.
 *
 * It was the only way to read this page, it duplicated what Tasks and Threads
 * already show, and it honoured no reduced-motion preference. The records it
 * draws are real, so it is kept rather than deleted — behind a press.
 */
async function showWorkstations(): Promise<void> {
  await fireEvent.click(await screen.findByRole("button", { name: "Workstations" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  // The view choice is remembered per browser, which is right in the product
  // and wrong between two tests: without this, a test that opened the floor
  // decides what the next one renders.
  try {
    window.localStorage.clear();
  } catch {
    // A jsdom without storage is fine; nothing here depends on it.
  }
});

describe("WorkInActionView", () => {
  it("shows a route-level loading state while live work is fetched", async () => {
    stubFetchPending();
    render(WorkInActionView);
    const statuses = await screen.findAllByRole("status");
    expect(statuses.some((el) => /loading live work/i.test(el.textContent ?? ""))).toBe(true);
  });

  it("shows a route-level error state when live work cannot load", async () => {
    stubFetch({});
    render(WorkInActionView);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't load live work/i);
    expect(alert).toHaveTextContent(/unavailable \(404\)/i);
  });

  it("shows real subagent assignment, task progress, and waiting schedules", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-15T00:00:00Z",
        illustrative_motion_notice: "Animated pulses indicate visual activity only.",
        nodes: [
          { node_id: "agent:a", node_type: "agent", label: "Researcher", status: "idle", detail: "Draft a plan", progress_percent: null, is_real: true },
          { node_id: "task:t", node_type: "task", label: "Draft a plan", status: "running", detail: "Outline", progress_percent: 40, is_real: true },
          { node_id: "schedule:t", node_type: "schedule", label: "Scheduled work", status: "waiting", detail: "2026-07-16T09:00:00Z", progress_percent: null, is_real: true },
        ],
        edges: [],
      },
    });
    render(WorkInActionView);

    // The same records read as a list, which is what the page opens on.
    const table = await screen.findByRole("table", { name: "Live work" });
    expect(within(table).getByText("Researcher")).toBeInTheDocument();
    expect(within(table).getByText("Scheduled work")).toBeInTheDocument();
    // Twice, and correctly: the subagent's current detail and the task's own
    // label. The list does not merge the two rows, because they are two
    // records.
    expect(within(table).getAllByText("Draft a plan")).toHaveLength(2);
    expect(within(table).getByText("40%")).toBeInTheDocument();
    // A direct link to the task's own detail, from the coordinate `brain`
    // already returns.
    expect(within(table).getByRole("link", { name: "Open task" }).getAttribute("href")).toBe(
      "#/tasks?task=t",
    );
    // Nothing moves, so nothing has to disclaim that the movement means work.
    expect(screen.queryByText(/visual-only/i)).toBeNull();

    await showWorkstations();
    await waitFor(() => expect(screen.getByText(/Idle · Draft a plan/i)).toBeInTheDocument());
    expect(screen.getByText(/Working · 40% · Outline/i)).toBeInTheDocument();
    expect(screen.getByText(/waiting · 2026-07-16/i)).toBeInTheDocument();
    expect(screen.getByText(/visual-only/i)).toBeInTheDocument();
  });

  // A percentage the runtime did not record is not zero. Drawing it at zero
  // would read as "started and got nowhere".
  it("says a missing progress figure is not recorded rather than drawing it at zero", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-09-18T00:00:00Z",
        illustrative_motion_notice: "",
        nodes: [
          { node_id: "task:t", node_type: "task", label: "Draft a plan", status: "running", detail: null, progress_percent: null, is_real: true },
        ],
        edges: [],
      },
    });
    render(WorkInActionView);

    const table = await screen.findByRole("table", { name: "Live work" });
    expect(within(table).getByText("Not recorded")).toBeInTheDocument();
    expect(within(table).queryByRole("progressbar")).toBeNull();
  });

  // BUG-09 — a run that ended dropped off this page entirely, so the reason it
  // ended was visible nowhere. A blocked run is live work, not a finished one.
  it("says how the last runs ended and keeps approval-blocked work in the active list", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-07-27T00:00:00Z",
        illustrative_motion_notice: "Animated pulses indicate visual activity only.",
        nodes: [
          { node_id: "task:blocked", node_type: "task", label: "Publish the note", status: "waiting_for_approval", detail: "Waiting for your approval before this run can continue.", progress_percent: null, is_real: true },
          { node_id: "task:failed", node_type: "task", label: "Background agent", status: "failed", detail: "The model was unreachable.", progress_percent: null, is_real: true },
          { node_id: "task:silent", node_type: "task", label: "Nightly sweep", status: "completed", detail: null, progress_percent: null, is_real: true },
        ],
        edges: [],
      },
    });
    render(WorkInActionView);

    await waitFor(() => expect(screen.getByText("Publish the note")).toBeInTheDocument());
    await showWorkstations();
    expect(screen.getByText(/Waiting for approval · Waiting for your approval/i)).toBeInTheDocument();
    expect(screen.getByText("How the last runs ended")).toBeInTheDocument();
    expect(screen.getByText(/Failed · The model was unreachable\./i)).toBeInTheDocument();
    expect(screen.getByText(/Done · No reason was recorded for this outcome\./i)).toBeInTheDocument();
  });

  // REM-LIVE — the choice is a viewing preference, so it is remembered in this
  // browser and nowhere else. It never reaches the workspace or the record.
  it("remembers the chosen view for this browser only", async () => {
    stubFetch({
      "GET /api/brain": {
        generated_at: "2026-09-18T00:00:00Z",
        illustrative_motion_notice: "",
        nodes: [],
        edges: [],
      },
    });
    const { unmount } = render(WorkInActionView);
    await showWorkstations();
    expect(window.localStorage.getItem("raiker.work-in-action.view")).toBe("floor");
    unmount();

    render(WorkInActionView);
    expect(
      await screen.findByRole("region", { name: "Agent workstations" }),
    ).toBeInTheDocument();
  });
});
