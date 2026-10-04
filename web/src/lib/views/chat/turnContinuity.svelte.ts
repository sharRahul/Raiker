/**
 * UX-CHAT-01 — the Continuity actions, out of ChatView.
 *
 * UX-CHAT-05 grouped a turn's actions as Conversation, Evidence and
 * Continuity; this is the third group's state machine, with one owner:
 *
 * * **Branch from here** (C14) opens a second conversation from a turn's
 *   checkpoint, so two lines of thought exist side by side. This conversation
 *   keeps every turn it had, and the branch says where it grew from.
 * * **Rewind to before this turn** (B18) resolves the turn's checkpoint and
 *   opens the shared rewind funnel. It performs nothing itself.
 * * **Summarise up to here** (backlog #9) shortens what the *model* is sent and
 *   removes nothing from the transcript, which is why the notice says so
 *   rather than asking for a confirmation.
 *
 * Moved, not changed: every message and refusal is the one the view printed.
 */
import { api, ApiError } from "../../api";
import type { ConversationBranchOrigin } from "../../apiTypes";

export class TurnContinuity {
  branchingTurn = $state<string | null>(null);
  /** Where this conversation came from, when it is itself a branch. */
  branchOrigin = $state<ConversationBranchOrigin | null>(null);
  rewindingTurn = $state<string | null>(null);
  /** The checkpoint the rewind panel is open on; null when it is closed. */
  rewindCheckpointId = $state<string | null>(null);
  compactingTurn = $state<string | null>(null);

  constructor(
    private readonly session: () => string | null,
    /** No continuity action starts while a turn is streaming. */
    private readonly streaming: () => boolean,
    /** The conversation's one notice line. */
    private readonly notify: (text: string | null) => void,
    /** The rewind panel and the file pane share the right-hand column. */
    private readonly closeSidePanel: () => void,
  ) {}

  loadBranchOrigin = async (id: string | null) => {
    if (id === null) {
      this.branchOrigin = null;
      return;
    }
    try {
      const origin = await api.conversationBranchOrigin(id);
      this.branchOrigin = origin.source_session_id ? origin : null;
    } catch {
      // Lineage is context, not content: a failed read leaves the banner off
      // rather than claiming the conversation is a root when that is unknown.
      this.branchOrigin = null;
    }
  };

  branchFromTurn = async (turnId: string) => {
    const session = this.session();
    if (session === null || this.streaming()) return;
    this.branchingTurn = turnId;
    this.notify(null);
    try {
      const checkpoints = await api.checkpoints(session);
      const point = checkpoints.find((checkpoint) => checkpoint.turn_id === turnId);
      if (point === undefined) {
        // No checkpoint means no state to seed a branch from. Saying so is the
        // honest answer; inventing a seed from the transcript is not.
        this.notify("No checkpoint was written for that turn, so there is no point to branch from.");
        return;
      }
      const branch = await api.branchConversation(point.checkpoint_id);
      window.location.hash = `#/new-chat?session=${encodeURIComponent(branch.session_id)}`;
    } catch (error) {
      this.notify(
        error instanceof ApiError
          ? `That conversation could not be branched (${error.reasonCode ?? error.status}).`
          : "That conversation could not be branched.",
      );
    } finally {
      this.branchingTurn = null;
    }
  };

  rewindFromTurn = async (turnId: string) => {
    const session = this.session();
    if (session === null || this.streaming()) return;
    this.rewindingTurn = turnId;
    this.notify(null);
    try {
      const checkpoints = await api.checkpoints(session);
      const point = checkpoints.find((checkpoint) => checkpoint.turn_id === turnId);
      if (point === undefined) {
        this.notify("No checkpoint was written for that turn, so there is nothing to rewind to.");
        return;
      }
      this.closeSidePanel();
      this.rewindCheckpointId = point.checkpoint_id;
    } catch (error) {
      this.notify(
        error instanceof ApiError
          ? `Could not read this conversation's checkpoints (${error.reasonCode ?? error.status}).`
          : "Could not read this conversation's checkpoints.",
      );
    } finally {
      this.rewindingTurn = null;
    }
  };

  compactThroughTurn = async (turnId: string) => {
    const session = this.session();
    if (session === null || this.streaming()) return;
    this.compactingTurn = turnId;
    this.notify(null);
    try {
      const result = await api.compactConversation(session, turnId);
      this.notify(
        result.compacted
          ? `Summarised ${result.source_turn_count} earlier ${
              result.source_turn_count === 1 ? "exchange" : "exchanges"
            } for the model. Nothing was removed from this transcript.`
          : result.reason_code === "nothing_to_summarise"
            ? "Everything up to that point is already summarised."
            : `That range could not be summarised (${result.reason_code}).`,
      );
    } catch (error) {
      this.notify(
        error instanceof ApiError
          ? `That range could not be summarised (${error.reasonCode ?? error.status}).`
          : "That range could not be summarised.",
      );
    } finally {
      this.compactingTurn = null;
    }
  };
}
