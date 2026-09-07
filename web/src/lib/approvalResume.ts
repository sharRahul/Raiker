/**
 * Cross-tab approval continuation (BUG-24).
 *
 * A conversation that parks on an approval is waiting on a decision the owner
 * may make anywhere — the Approvals inbox in another tab, the Build workspace,
 * a second window. Before this, only the tab that recorded the decision could
 * continue the turn; every other tab sat on **Waiting for approval** forever,
 * and the owner's only recovery was to re-prompt, which discards the model's
 * working state and pays for the whole context again.
 *
 * Two independent signals close that gap, and the design is deliberately
 * belt-and-braces because a stuck conversation is the worst outcome:
 *
 * 1. **A same-browser broadcast.** `BroadcastChannel` delivers a resolution to
 *    every other tab of the same origin, instantly and with no server round
 *    trip. It is a *hint*, not authority: the message carries ids only, and the
 *    receiving tab still asks the server what it may continue.
 * 2. **An authenticated server poll.** `GET /api/approvals/resumable` is the
 *    authority. It is principal-scoped, returns ids only, and lists a parked
 *    turn exactly while it is resolved-but-unclaimed. Polling covers the cases
 *    the broadcast cannot reach — a decision made in a different browser, on the
 *    phone, or by the CLI — and is the recoverable path when the live channel is
 *    unavailable.
 *
 * **Exactly once** is not enforced here and deliberately so. The client guards
 * against obvious double-starts, but the real guarantee is the server's atomic
 * `claim_suspended_turn` (suspended → resuming): two tabs that both react to the
 * same broadcast will both call resume, and exactly one will get the stream —
 * the other gets `suspended_turn_already_resumed`, which is a *success* from the
 * owner's point of view and is reported as "continued in another tab" rather
 * than as an error.
 */

import { api } from "./api";

export const RESUME_CHANNEL = "raiker:approvals";

/** The shape put on the wire. Ids only — never conversation content. */
export interface ApprovalResolvedMessage {
  type: "approval-resolved";
  approvalId: string;
  sessionId: string | null;
  turnId: string | null;
  approved: boolean;
}

export interface ResumableTurn {
  approval_id: string;
  session_id: string;
  turn_id: string;
  tool_name: string;
  outcome_status: string;
  created_at: string;
  // ADD-02 — which decision of its batch this turn parked on.
  queue_position?: number;
  queue_total?: number;
}

/** How often the fallback poll runs while a turn is parked. */
export const POLL_INTERVAL_MS = 5000;

function channel(): BroadcastChannel | null {
  // Absent in jsdom and in any browser old enough not to ship it. Its absence
  // costs latency, not correctness: the poll still finds the resolution.
  if (typeof BroadcastChannel === "undefined") return null;
  try {
    return new BroadcastChannel(RESUME_CHANNEL);
  } catch {
    return null;
  }
}

/**
 * Announce that an approval was resolved here, so other tabs can react.
 *
 * Best-effort by design: a browser that refuses the channel simply means other
 * tabs learn from their next poll instead of immediately.
 */
export function publishApprovalResolved(message: Omit<ApprovalResolvedMessage, "type">): void {
  const bus = channel();
  if (bus === null) return;
  try {
    bus.postMessage({ type: "approval-resolved", ...message } satisfies ApprovalResolvedMessage);
  } finally {
    bus.close();
  }
}

/**
 * Hear about a resolution made in another tab of this browser.
 *
 * A hint, exactly like the one the watcher acts on: the message carries ids
 * only, and a listener that acts on it must still ask the server what is true.
 * The prompt uses it to drop a decision the owner has already made elsewhere
 * rather than leaving a stale card on screen until the next poll.
 */
export function subscribeApprovalResolved(
  onResolved: (message: ApprovalResolvedMessage) => void,
): () => void {
  const bus = channel();
  if (bus === null) return () => {};
  const listener = (event: MessageEvent) => {
    const message = event.data as ApprovalResolvedMessage | null;
    if (message && message.type === "approval-resolved") onResolved(message);
  };
  bus.addEventListener("message", listener);
  return () => {
    bus.removeEventListener("message", listener);
    bus.close();
  };
}

export interface WatcherOptions {
  /** Which conversation this watcher speaks for. Read fresh on every check. */
  sessionId: () => string | null;
  /** Whether this surface currently has a turn parked on an approval. */
  hasParkedTurn: () => boolean;
  /** Continue the named turn. Called at most once per approval id per tab. */
  onResume: (turn: ResumableTurn) => void | Promise<void>;
  /** Told when the live channel could not be established, so the UI can offer
   *  a manual **Continue now** instead of implying continuation is automatic. */
  onChannelUnavailable?: (unavailable: boolean) => void;
}

export interface ResumeWatcher {
  /** Check right now — used the moment a turn parks, so a decision already
   *  recorded elsewhere is acted on immediately rather than up to a poll late. */
  checkNow: () => void;
  /**
   * Record that this surface has already started continuing `approvalId`, so
   * the poll does not start it a second time.
   *
   * BUG-196 — the owner's own **Approve** click continues the turn directly,
   * without going through the watcher. The poll knew nothing about that, saw the
   * same resolved-and-unclaimed row, and raced its own surface: one attempt got
   * the stream, the other got a 409, and the 409 was the only thing on screen.
   * Claiming the id closes the race rather than reporting it politely.
   */
  claim: (approvalId: string) => void;
  stop: () => void;
}

/**
 * Watch for a resolution that unblocks this surface's parked turn.
 *
 * The watcher polls only while a turn is actually parked, so an idle
 * conversation costs nothing.
 */
export function watchForResumableTurns(options: WatcherOptions): ResumeWatcher {
  const started = new Set<string>();
  let disposed = false;

  async function check(): Promise<void> {
    if (disposed || !options.hasParkedTurn()) return;
    const sessionId = options.sessionId();
    if (sessionId === null) return;
    let turns: ResumableTurn[];
    try {
      turns = (await api.resumableTurns(sessionId)).turns;
      options.onChannelUnavailable?.(false);
    } catch {
      // The runtime is unreachable. Say so through the callback rather than
      // silently stopping: the owner needs the manual action offered.
      options.onChannelUnavailable?.(true);
      return;
    }
    for (const turn of turns) {
      if (started.has(turn.approval_id)) continue;
      started.add(turn.approval_id);
      void options.onResume(turn);
    }
  }

  const bus = channel();
  if (bus !== null) {
    bus.onmessage = (event: MessageEvent<ApprovalResolvedMessage>) => {
      if (event.data?.type !== "approval-resolved") return;
      // The broadcast is only a nudge to check; the server decides.
      void check();
    };
  } else {
    options.onChannelUnavailable?.(true);
  }

  const timer = setInterval(() => void check(), POLL_INTERVAL_MS);
  void check();

  return {
    checkNow: () => void check(),
    claim: (approvalId: string) => started.add(approvalId),
    stop: () => {
      disposed = true;
      clearInterval(timer);
      bus?.close();
    },
  };
}

/**
 * Was this resume refused because another tab already ran it?
 *
 * That is a success, not a failure: the turn continued, just not here. It is
 * reported to the owner as such so a race never reads as a broken conversation.
 *
 * BUG-196 widened this beyond the single code it started with. A parked turn is
 * claimed atomically (`suspended → resuming`) and finalised to `resumed`, so a
 * losing client sees whichever of those two states it happened to read; and a
 * row that has been reaped altogether is not a turn this surface can continue
 * either. All three mean the same thing to the owner: this decision was already
 * acted on.
 */
const CONTINUED_ELSEWHERE = new Set([
  // The claim was lost, or the row had already moved past `suspended`.
  "suspended_turn_already_resumed",
  // The parked row is gone. Nothing here can continue it, and nothing here
  // failed to: it ran, and its state was cleaned up.
  "suspended_turn_not_found",
]);

export function alreadyResumedElsewhere(reasonCode: string | null | undefined): boolean {
  return reasonCode !== null && reasonCode !== undefined && CONTINUED_ELSEWHERE.has(reasonCode);
}

/**
 * What a refused resume means for the surface that asked.
 *
 * Three outcomes, because a 409 is three different facts (BUG-196):
 *
 * - `continued-elsewhere` — the decision was already acted on. Say so, quietly.
 * - `not-yet-resolved` — the approval has no recorded outcome *yet*. The turn is
 *   genuinely still parked, so the honest surface is the waiting state it was
 *   already in. The watcher will come back when there is something to continue;
 *   an error line here would be a lie about a turn that is fine.
 * - `failed` — everything else, including an unreadable parked state. This is a
 *   real failure and must still say so, with its reason.
 */
export type ResumeFailure = "continued-elsewhere" | "not-yet-resolved" | "failed";

export function classifyResumeFailure(reasonCode: string | null | undefined): ResumeFailure {
  if (alreadyResumedElsewhere(reasonCode)) return "continued-elsewhere";
  if (reasonCode === "approval_not_resolved") return "not-yet-resolved";
  return "failed";
}
