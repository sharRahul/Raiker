// B17 / C13, 03 Composer execution states — the row over a turn that is
// already running, and the state behind Stop and follow-ups.
//
// What matters is honesty: Stop is a request applied at a safe boundary and
// never reported as done; a follow-up is Queued until the runtime's own
// `turn_steered` event says it was read; nothing can act before the
// conversation has an id; and a step's state is said in words.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TurnControl from "./TurnControl.svelte";
import RunSendButton from "./RunSendButton.svelte";
import FollowUpPills from "./FollowUpPills.svelte";
import { CONTINUE_PROMPT, RunningTurn, elapsedLabel, steersRead } from "../runningTurn.svelte";
import type { StreamEvent } from "../apiTypes";
import type { ToolCallRow } from "../chatPresentation";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function steered(): StreamEvent {
  return { kind: "lifecycle", text: "", event_type: "turn_steered", payload: {}, response: null };
}

function turnFor(sessionId: string | null): RunningTurn {
  const control = new RunningTurn();
  control.sessionId = sessionId;
  control.begin();
  return control;
}

describe("RunningTurn", () => {
  it("cannot stop until the conversation has an id, and holds a follow-up until then", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "steer", queued: 1 } },
    });
    const control = turnFor(null);
    expect(control.ready).toBe(false);
    await control.stop();
    expect(await control.steer("typed in the first second")).toBe(true);
    expect(control.followUps.map((item) => item.state)).toEqual(["pending"]);
    expect(fetchMock).not.toHaveBeenCalled();
    // The id arrives with the first streamed chunk; the held follow-up goes then.
    control.sessionId = "sess_1";
    await control.flush();
    expect(control.followUps.map((item) => item.state)).toEqual(["queued"]);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({
      session_id: "sess_1",
      action_type: "steer",
      steer_text: "typed in the first second",
    });
  });

  it("takes nothing when no turn is running", async () => {
    const control = new RunningTurn();
    expect(await control.steer("hello")).toBe(false);
    expect(control.followUps).toEqual([]);
  });

  it("asks for a safe-boundary stop and reports it as requested", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "stop", queued: 0 } },
    });
    const control = turnFor("sess_1");
    await control.stop();
    expect(control.stopping).toBe(true);
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toMatchObject({ session_id: "sess_1", action_type: "cancel", all: true });
  });

  it("says when the stop itself failed", async () => {
    stubFetch({});
    const control = turnFor("sess_1");
    await control.stop();
    expect(control.stopping).toBe(false);
    expect(control.error).toMatch(/Stop was not sent/);
  });

  it("queues a follow-up only once the host accepts it", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "steer", queued: 1 } },
    });
    const control = turnFor("sess_1");
    expect(await control.steer("  use the changelog instead ")).toBe(true);
    expect(control.followUps).toEqual([{ id: 1, text: "use the changelog instead", state: "queued" }]);
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toMatchObject({ action_type: "steer", steer_text: "use the changelog instead" });
  });

  // DEC-22 step 2 — the queue of waiting instructions is bounded.
  it("says the waiting instructions are unread when the queue is full", async () => {
    stubFetch({
      "POST /api/interrupts": { __status: 429, detail: { ok: false, reason_code: "steer_queue_full" } },
    });
    const control = turnFor("sess_1");
    expect(await control.steer("and this")).toBe(false);
    // Its words are kept as Not read, so they can still be used.
    expect(control.followUps).toEqual([{ id: 1, text: "and this", state: "unread" }]);
    expect(control.error).toMatch(/already waiting.*next safe boundary/);
  });

  it("marks follow-ups read in order, only from turn_steered events", async () => {
    stubFetch({ "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { queued: 1 } } });
    const control = turnFor("sess_1");
    await control.steer("first");
    await control.steer("second");
    control.observe([{ kind: "text_delta", text: "hi", event_type: "", payload: {}, response: null }]);
    expect(control.followUps.map((item) => item.state)).toEqual(["queued", "queued"]);
    control.observe([steered()]);
    expect(control.followUps.map((item) => item.state)).toEqual(["read", "queued"]);
  });

  it("when the turn ends, drops what was read and says what was not", async () => {
    stubFetch({ "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { queued: 1 } } });
    const control = turnFor("sess_1");
    await control.steer("first");
    await control.steer("second");
    control.observe([steered()]);
    control.end();
    expect(control.followUps).toEqual([{ id: 2, text: "second", state: "unread" }]);
    expect(control.startedAt).toBeNull();
    control.begin();
    expect(control.followUps).toEqual([]);
  });

  it("counts steers and formats elapsed time", () => {
    expect(steersRead([steered(), steered()])).toBe(2);
    expect(elapsedLabel(0)).toBe("0:00");
    expect(elapsedLabel(65_400)).toBe("1:05");
    expect(elapsedLabel(3_723_000)).toBe("1:02:03");
    expect(CONTINUE_PROMPT).toMatch(/^Continue from where you stopped/);
  });
});

describe("TurnControl", () => {
  const steps: ToolCallRow[] = [
    { actionId: "a1", toolName: "read_file", family: "file-read", label: "Read file", action: "notes.md", state: "success", reasons: [] },
    { actionId: "a2", toolName: "web_search", family: "web", label: "Search the web", action: "", state: "running", reasons: [] },
  ];

  it("shows what the turn is doing now and how long it has run", () => {
    vi.useFakeTimers();
    const control = turnFor("sess_1");
    control.startedAt = Date.now() - 42_000;
    render(TurnControl, { control, activity: "Read file · proposal.pdf" });
    const line = screen.getByRole("status");
    expect(line).toHaveTextContent("Read file · proposal.pdf…");
    expect(line).toHaveTextContent("0:42");
  });

  it("says it is writing the answer when no step is in flight", () => {
    render(TurnControl, { control: turnFor("sess_1") });
    expect(screen.getByRole("status")).toHaveTextContent("Writing the answer…");
    expect(screen.queryByRole("button", { name: /step/ })).toBeNull();
  });

  it("opens a step drawer that says each state in words", async () => {
    render(TurnControl, { control: turnFor("sess_1"), steps });
    const toggle = screen.getByRole("button", { name: /2 steps/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const drawer = screen.getByRole("list", { name: "Steps in this turn" });
    expect(drawer).toHaveTextContent("Read file · notes.md");
    expect(drawer).toHaveTextContent("Done");
    expect(drawer).toHaveTextContent("Running");
  });

  it("reports a requested stop and its failure", async () => {
    const control = turnFor("sess_1");
    control.stopping = true;
    render(TurnControl, { control });
    expect(screen.getByText(/Stop requested/)).toBeInTheDocument();
  });
});

describe("RunSendButton", () => {
  it("is Send at rest, Stop safely while running and Queue once something is typed", async () => {
    const control = turnFor("sess_1");
    const view = render(RunSendButton, { streaming: false, hasText: true, control });
    expect(screen.getByRole("button", { name: "Send" })).toHaveAttribute("type", "submit");
    await view.rerender({ streaming: true, hasText: false, control });
    expect(screen.getByRole("button", { name: "Stop safely" })).toHaveAttribute("type", "button");
    await view.rerender({ streaming: true, hasText: true, control });
    expect(screen.getByRole("button", { name: "Queue" })).toHaveAttribute("type", "submit");
    expect(screen.queryByRole("button", { name: "Stop safely" })).toBeNull();
  });

  it("stops through the governed interrupt", async () => {
    const fetchMock = stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: { action: "stop", queued: 0 } },
    });
    render(RunSendButton, { streaming: true, hasText: false, control: turnFor("sess_1") });
    await fireEvent.click(screen.getByRole("button", { name: "Stop safely" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Stopping…" })).toBeDisabled());
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({ action_type: "cancel" });
  });

  it("cannot stop before the conversation has an id", () => {
    render(RunSendButton, { streaming: true, hasText: false, control: turnFor(null) });
    expect(screen.getByRole("button", { name: "Stop safely" })).toBeDisabled();
  });
});

describe("FollowUpPills", () => {
  it("shows each follow-up with its state, and offers an unread one as the next message", async () => {
    const control = turnFor("sess_1");
    control.followUps = [
      { id: 1, text: "use the changelog", state: "read" },
      { id: 2, text: "and cite it", state: "unread" },
    ];
    const onuse = vi.fn();
    render(FollowUpPills, { control, onuse });
    const list = screen.getByRole("list", { name: "Follow-ups for the running turn" });
    expect(list).toHaveTextContent("use the changelog");
    expect(list).toHaveTextContent("Read");
    expect(list).toHaveTextContent("Not read");
    await fireEvent.click(screen.getByRole("button", { name: "Use as next message" }));
    expect(onuse).toHaveBeenCalledWith("and cite it");
    expect(control.followUps.map((item) => item.id)).toEqual([1]);
  });
});
