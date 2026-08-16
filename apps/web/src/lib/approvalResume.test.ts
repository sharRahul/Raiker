import { afterEach, describe, expect, it, vi } from "vitest";
import {
  alreadyResumedElsewhere,
  classifyResumeFailure,
  POLL_INTERVAL_MS,
  publishApprovalResolved,
  watchForResumableTurns,
} from "./approvalResume";
import { stubFetch } from "./test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const TURN = {
  approval_id: "apv_1",
  session_id: "sess_1",
  turn_id: "turn_1",
  tool_name: "write_file",
  outcome_status: "success",
  created_at: "2026-07-31T10:00:00Z",
};

function routes(turns: unknown[] = [TURN]) {
  return { "GET /api/approvals/resumable": { session_id: "sess_1", turns } };
}

describe("approvalResume — BUG-24", () => {
  it("resumes a parked turn the server reports as resolved", async () => {
    stubFetch(routes());
    const onResume = vi.fn();
    const { stop } = watchForResumableTurns({
      sessionId: () => "sess_1",
      hasParkedTurn: () => true,
      onResume,
    });
    await vi.waitFor(() => expect(onResume).toHaveBeenCalledWith(TURN));
    stop();
  });

  it("starts each approval at most once, however often it is reported", async () => {
    vi.useFakeTimers();
    stubFetch(routes());
    const onResume = vi.fn();
    const { stop } = watchForResumableTurns({
      sessionId: () => "sess_1",
      hasParkedTurn: () => true,
      onResume,
    });
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 4);
    expect(onResume).toHaveBeenCalledTimes(1);
    stop();
  });

  it("does not poll while nothing is parked", async () => {
    const fetchMock = stubFetch(routes());
    const { stop } = watchForResumableTurns({
      sessionId: () => "sess_1",
      hasParkedTurn: () => false,
      onResume: vi.fn(),
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(fetchMock).not.toHaveBeenCalled();
    stop();
  });

  it("does not poll before the conversation has a session", async () => {
    const fetchMock = stubFetch(routes());
    const { stop } = watchForResumableTurns({
      sessionId: () => null,
      hasParkedTurn: () => true,
      onResume: vi.fn(),
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(fetchMock).not.toHaveBeenCalled();
    stop();
  });

  it("reports the channel as unavailable when the runtime cannot be reached", async () => {
    stubFetch({});
    const onChannelUnavailable = vi.fn();
    const { stop } = watchForResumableTurns({
      sessionId: () => "sess_1",
      hasParkedTurn: () => true,
      onResume: vi.fn(),
      onChannelUnavailable,
    });
    await vi.waitFor(() => expect(onChannelUnavailable).toHaveBeenCalledWith(true));
    stop();
  });

  it("stops watching once disposed", async () => {
    vi.useFakeTimers();
    const fetchMock = stubFetch(routes([]));
    const { stop } = watchForResumableTurns({
      sessionId: () => "sess_1",
      hasParkedTurn: () => true,
      onResume: vi.fn(),
    });
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
    const before = fetchMock.mock.calls.length;
    stop();
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3);
    expect(fetchMock.mock.calls.length).toBe(before);
  });

  it("treats a turn another tab already claimed as a success, not an error", () => {
    expect(alreadyResumedElsewhere("suspended_turn_already_resumed")).toBe(true);
    // BUG-196 — a parked row that is gone is not a turn this surface failed to
    // continue. It ran and its state was reaped; there is nothing here to
    // report as broken.
    expect(alreadyResumedElsewhere("suspended_turn_not_found")).toBe(true);
    expect(alreadyResumedElsewhere("suspended_turn_unreadable")).toBe(false);
    expect(alreadyResumedElsewhere(null)).toBe(false);
  });

  it("tells a lost race, a decision not yet recorded, and a real failure apart", () => {
    // BUG-196 — the three facts a 409 can carry. Before this, every one of them
    // rendered as "The turn could not continue (409)." beneath a finished answer,
    // because the streaming path threw the reason code away and the classifier
    // knew one code.
    expect(classifyResumeFailure("suspended_turn_already_resumed")).toBe("continued-elsewhere");
    expect(classifyResumeFailure("suspended_turn_not_found")).toBe("continued-elsewhere");
    // No decision has reached the runtime yet: the turn is genuinely still
    // parked, so waiting is the truthful surface, not an error.
    expect(classifyResumeFailure("approval_not_resolved")).toBe("not-yet-resolved");
    // A parked state that cannot be read is a real failure and must still say so.
    expect(classifyResumeFailure("suspended_turn_unreadable")).toBe("failed");
    expect(classifyResumeFailure(null)).toBe("failed");
  });

  it("does not start a continuation the surface already claimed", async () => {
    // BUG-196 — the owner's own Approve click resumes directly. Without the
    // claim the poll saw the same resolved-and-unclaimed row and raced its own
    // surface: one attempt streamed the answer, the other got a 409, and only
    // the 409 was on screen.
    vi.useFakeTimers();
    const fetchMock = stubFetch({
      "GET /api/approvals/resumable": {
        turns: [
          {
            approval_id: "apv_1",
            session_id: "sess_1",
            turn_id: "turn_1",
            tool_name: "shell",
            outcome_status: "approved",
            created_at: "2026-08-16T00:00:00Z",
          },
        ],
      },
    });
    const resumed: string[] = [];
    const watcher = watchForResumableTurns({
      sessionId: () => "sess_1",
      hasParkedTurn: () => true,
      onResume: (turn) => void resumed.push(turn.approval_id),
    });
    watcher.claim("apv_1");

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2);
    watcher.stop();

    expect(resumed).toEqual([]);
    expect(fetchMock.mock.calls.length).toBeGreaterThan(0);
  });

  it("publishing never throws when the browser has no BroadcastChannel", () => {
    // jsdom in this suite has none; the watcher must degrade to polling only.
    expect(() =>
      publishApprovalResolved({
        approvalId: "apv_1",
        sessionId: "sess_1",
        turnId: "turn_1",
        approved: true,
      }),
    ).not.toThrow();
  });
});
