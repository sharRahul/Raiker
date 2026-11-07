/**
 * 03 Composer execution states (2026-11-07) — the composer's hold on a turn
 * that is already running, shared by Chat and Build.
 *
 * Stop is the same governed `POST /api/interrupts` (`cancel`) the top bar's
 * STOP uses. A follow-up is a `steer`: the owner's own words, read by the
 * runtime at its next safe boundary as a user message, granting nothing.
 *
 * Every state a follow-up shows is one the runtime reported. It is *pending*
 * while a brand-new chat waits for its session id, *queued*
 * once the host accepted it, *read* only when the turn's stream carries a
 * `turn_steered` lifecycle event for it (the runtime drains the queue in
 * order, so the n-th event is the n-th accepted follow-up), and *unread* when
 * the turn ended first — the runtime drops a leftover steer at the start of
 * the next turn, so it was not, and will not be, read.
 */
import { api, ApiError } from "./api";
import type { StreamEvent } from "./apiTypes";
import { failure } from "./errorCopy";

export type FollowUpState = "pending" | "queued" | "read" | "unread";

export interface FollowUp {
  readonly id: number;
  readonly text: string;
  state: FollowUpState;
}

/** How many `turn_steered` events a turn's stream has carried so far. */
export function steersRead(events: readonly StreamEvent[]): number {
  let read = 0;
  for (const event of events) {
    if (event.kind === "lifecycle" && event.event_type === "turn_steered") read += 1;
  }
  return read;
}

/** `m:ss`, or `h:mm:ss` past an hour. Elapsed time is the one figure a running turn can state truthfully. */
export function elapsedLabel(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
}

/** What a continuation sends, shown in the transcript as the owner's own message. */
export const CONTINUE_PROMPT =
  "Continue from where you stopped. Do not repeat steps that already finished; say which step you are picking up from.";

export class RunningTurn {
  sessionId = $state<string | null>(null);
  stopping = $state(false);
  busy = $state(false);
  error = $state<string | null>(null);
  followUps = $state<FollowUp[]>([]);
  startedAt = $state<number | null>(null);
  private nextId = 1;

  get ready(): boolean {
    return this.sessionId !== null && this.sessionId !== "";
  }

  /** A new turn: nothing queued, nothing stopping, the clock from now. */
  begin(now: number = Date.now()): void {
    this.followUps = [];
    this.stopping = false;
    this.error = null;
    this.startedAt = now;
  }

  /** The turn settled: what it read has done its job; anything still queued was never read. */
  end(): void {
    this.followUps = this.followUps
      .filter((item) => item.state !== "read")
      .map((item) => (item.state === "queued" || item.state === "pending" ? { ...item, state: "unread" as const } : item));
    this.startedAt = null;
    this.stopping = false;
  }

  /** Mark follow-ups read, oldest first, as far as the stream says. */
  observe(events: readonly StreamEvent[]): void {
    let read = steersRead(events);
    if (read === 0) return;
    let changed = false;
    const next = this.followUps.map((item) => {
      if (read === 0 || item.state === "unread" || item.state === "pending") return item;
      read -= 1;
      if (item.state === "read") return item;
      changed = true;
      return { ...item, state: "read" as const };
    });
    if (changed) this.followUps = next;
  }

  dismiss(id: number): void {
    this.followUps = this.followUps.filter((item) => item.id !== id);
  }

  async stop(reason = "user stopped this turn (composer)"): Promise<void> {
    if (!this.ready || this.busy || this.stopping) return;
    this.busy = true;
    this.error = null;
    try {
      await api.interrupt({ session_id: this.sessionId as string, all: true, action_type: "cancel", reason });
      this.stopping = true;
    } catch (e) {
      this.error = failure("Stop was not sent", "The turn is still running.", "Try Stop safely again, or use STOP in the top bar.", e);
    } finally {
      this.busy = false;
    }
  }

  /**
   * Queue `text` for the running turn. True when it was taken: accepted by the
   * host, or — before a brand-new chat has learned its session id from its
   * first streamed chunk — held as *pending* and sent by `flush()` the moment
   * the id arrives. A follow-up typed in that first second is never dropped.
   */
  async steer(text: string): Promise<boolean> {
    const words = text.trim();
    if (words === "") return false;
    if (!this.ready) {
      if (this.startedAt === null) return false;
      this.followUps = [...this.followUps, { id: this.nextId++, text: words, state: "pending" }];
      return true;
    }
    if (this.busy) return false;
    const item: FollowUp = { id: this.nextId++, text: words, state: "pending" };
    this.followUps = [...this.followUps, item];
    return this.send(item.id);
  }

  /** Send every pending follow-up, in order, once the turn has its id. */
  async flush(): Promise<void> {
    if (!this.ready || this.busy) return;
    for (const item of this.followUps.filter((held) => held.state === "pending")) {
      if (!(await this.send(item.id))) return;
    }
  }

  private async send(id: number): Promise<boolean> {
    const item = this.followUps.find((held) => held.id === id);
    if (!item) return false;
    this.busy = true;
    this.error = null;
    try {
      await api.interrupt({
        session_id: this.sessionId as string,
        all: true,
        action_type: "steer",
        reason: "user steered this turn (composer)",
        steer_text: item.text,
      });
      this.followUps = this.followUps.map((held) => (held.id === id ? { ...held, state: "queued" as const } : held));
      return true;
    } catch (e) {
      // Not taken: the pill says Not read, so its words can still be used.
      this.followUps = this.followUps.map((held) => (held.id === id ? { ...held, state: "unread" as const } : held));
      // DEC-22 step 2 — the instructions already waiting have not been read yet.
      this.error =
        e instanceof ApiError && e.reasonCode === "steer_queue_full"
          ? "Twenty instructions are already waiting. The turn reads them at its next safe boundary — send more after that."
          : failure("The instruction was not added", "The turn carries on without it.", "Send it again.", e);
      return false;
    } finally {
      this.busy = false;
    }
  }
}
