/**
 * REM-CHAT-01 — the shared per-turn evidence inspector.
 *
 * The properties that matter are the ones that let it sit under every turn of a
 * long conversation: it reads nothing until it is opened, it says so when the
 * record cannot be read rather than showing an empty list, and it carries the
 * coordinate a link elsewhere can name.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TurnEvidence from "./TurnEvidence.svelte";
import type { ToolCallRow } from "../chatPresentation";
import { stubFetch } from "../test-helpers";

const ROWS: ToolCallRow[] = [
  {
    actionId: "act_7",
    toolName: "read_file",
    family: "file-read",
    label: "Read file",
    action: "README.md",
    state: "success",
    reasons: [],
  },
];

const TURN = {
  turn: {
    turn_id: "turn_9",
    session_id: "sess_1",
    turn_type: "prompt",
    status: "completed",
    prompt_text: "what changed",
    created_at: "2026-09-20T10:00:00Z",
    completed_at: "2026-09-20T10:00:05Z",
    summary: "Two lines changed.",
  },
  events: [
    {
      event_id: "evt_1",
      session_id: "sess_1",
      turn_id: "turn_9",
      event_type: "model_request_completed",
      actor: "runtime",
      timestamp: "2026-09-20T10:00:04Z",
      risk_level: "low",
      summary: "Answered in 1.2s",
      priority: null,
      scheduled_at: null,
      recurrence: null,
      reminder_at: null,
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

describe("TurnEvidence", () => {
  it("reads nothing until it is opened", async () => {
    const fetchMock = stubFetch({ "GET /api/turns/turn_9": TURN });
    render(TurnEvidence, { sessionId: "sess_1", turnId: "turn_9", rows: ROWS });

    expect(screen.getByText("Evidence")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reads the record once, on the first open", async () => {
    const fetchMock = stubFetch({ "GET /api/turns/turn_9": TURN });
    const { container } = render(TurnEvidence, {
      sessionId: "sess_1",
      turnId: "turn_9",
      rows: ROWS,
    });

    const details = container.querySelector("details") as HTMLDetailsElement;
    details.open = true;
    await fireEvent(details, new Event("toggle"));

    await waitFor(() => expect(screen.getByText("model request completed")).toBeInTheDocument());
    expect(screen.getByText("Answered in 1.2s")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    details.open = false;
    await fireEvent(details, new Event("toggle"));
    details.open = true;
    await fireEvent(details, new Event("toggle"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("pairs each call with the action id that identifies it", async () => {
    stubFetch({ "GET /api/turns/turn_9": TURN });
    render(TurnEvidence, { sessionId: "sess_1", turnId: "turn_9", rows: ROWS });

    expect(screen.getByText("act_7")).toBeInTheDocument();
  });

  it("links to the full record at this turn's coordinate", async () => {
    stubFetch({ "GET /api/turns/turn_9": TURN });
    render(TurnEvidence, { sessionId: "sess_1", turnId: "turn_9", rows: ROWS });

    expect(screen.getByRole("link", { name: "Open the full record" })).toHaveAttribute(
      "href",
      "#/sessions?session=sess_1&turn=turn_9",
    );
  });

  it("says the record could not be read rather than showing an empty one", async () => {
    stubFetch({ "GET /api/turns/turn_9": { __status: 404 } });
    const { container } = render(TurnEvidence, {
      sessionId: "sess_1",
      turnId: "turn_9",
      rows: ROWS,
    });

    const details = container.querySelector("details") as HTMLDetailsElement;
    details.open = true;
    await fireEvent(details, new Event("toggle"));

    await waitFor(() =>
      expect(screen.getByText(/The record for this turn could not be read/)).toBeInTheDocument(),
    );
  });

  it("serves a turn that is still running, from the phases it is producing now", async () => {
    const fetchMock = stubFetch({});
    render(TurnEvidence, {
      sessionId: "sess_1",
      turnId: null,
      rows: [],
      phases: [{ phase: "act", label: "Act", lines: ["Asked the model"] }],
      initiallyOpen: true,
    });

    expect(screen.getByText("Act")).toBeInTheDocument();
    expect(screen.getByText("Asked the model")).toBeInTheDocument();
    // No coordinate yet, so nothing to read and nothing claimed about it.
    expect(screen.queryByText("What the runtime recorded")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("shows the record rather than the phases once there is one to read", async () => {
    stubFetch({ "GET /api/turns/turn_9": TURN });
    const { container } = render(TurnEvidence, {
      sessionId: "sess_1",
      turnId: "turn_9",
      rows: ROWS,
      phases: [{ phase: "act", label: "Act", lines: ["Asked the model"] }],
    });

    const details = container.querySelector("details") as HTMLDetailsElement;
    details.open = true;
    await fireEvent(details, new Event("toggle"));

    await waitFor(() => expect(screen.getByText("model request completed")).toBeInTheDocument());
    // The phases and the record are two versions of the same thing.
    expect(screen.queryByText("How this turn was governed")).not.toBeInTheDocument();
  });

  it("falls back to the phases when the record cannot be read", async () => {
    stubFetch({ "GET /api/turns/turn_9": { __status: 500 } });
    const { container } = render(TurnEvidence, {
      sessionId: "sess_1",
      turnId: "turn_9",
      rows: ROWS,
      phases: [{ phase: "act", label: "Act", lines: ["Asked the model"] }],
    });

    const details = container.querySelector("details") as HTMLDetailsElement;
    details.open = true;
    await fireEvent(details, new Event("toggle"));

    await waitFor(() => expect(screen.getByText("Asked the model")).toBeInTheDocument());
  });
});
