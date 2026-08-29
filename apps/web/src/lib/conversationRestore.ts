/**
 * BUG-242 — rebuilding a stored conversation into transcript rows.
 *
 * Chat and Build show the same governed turn, so they restore it the same way.
 * The pieces here are the parts that carry no view state: what a stored turn
 * becomes, and which composer chips belong to which turn. Each surface keeps
 * its own row identity and its own extras (Build carries the mode it ran in),
 * so nothing here invents a field a surface does not have.
 *
 * Restored turns carry only what is persisted: the prompt, the answer, the
 * status, the turn's tool rows and its retained working. The live per-event
 * timeline is not replayed — new turns stream as usual.
 */
import type { ComposerAttachment } from "./composerAttachments.svelte";
import type {
  AgentResponse,
  SessionAttachment,
  SessionDetail,
  StreamEvent,
  TurnSummary,
} from "./apiTypes";
import { humanize } from "./format";

export type ParkedApproval = NonNullable<SessionDetail["parked_approvals"]>[number];

/** Everything a restored turn holds that both surfaces share. */
export interface RestoredTurnCore {
  prompt: string;
  attachments: ComposerAttachment[];
  events: StreamEvent[];
  response: AgentResponse;
  streaming: false;
  error: null;
  resumeState: "waiting" | null;
  resumeNote: null;
  retainedReasoning: string | null;
  reasoningChars: number;
}

export function restoredTurnCore(
  turn: TurnSummary,
  sessionId: string,
  parked?: ParkedApproval,
): RestoredTurnCore {
  return {
    prompt: turn.prompt_text ?? "",
    attachments: [],
    // Backlog #25 — a reopened turn used to show the answer and nothing about
    // how it was reached, because the tool rows only ever existed on the stream
    // it was watched on. The server rebuilds them from the durable record in
    // the same payload shape a live event carries, so they enter here as events
    // and `toolActivity` assembles them exactly as it does live — including
    // merging with a later live event for the same call, which is what a parked
    // turn resumed in this tab produces.
    events: (turn.tool_rows ?? []).map((payload) => ({
      kind: "tool" as const,
      text: "",
      event_type: "tool_restored",
      payload,
      response: null,
    })),
    response: {
      request_id: "",
      session_id: sessionId,
      turn_id: turn.turn_id,
      status: turn.status,
      message: turn.summary ?? "",
      events_path: null,
      checkpoint_path: null,
      approval: parked
        ? {
            action_id: "",
            approval_id: parked.approval_id,
            tool_name: parked.tool_name,
            arguments: {},
            risk_level: "governed",
            reasons: [],
            message: `${humanize(parked.tool_name)} is waiting for your approval.`,
            expected_effect: "The same parked turn continues after your decision.",
            resumable: true,
          }
        : null,
      last_event_id: null,
    },
    streaming: false,
    error: null,
    resumeState: parked ? "waiting" : null,
    resumeNote: null,
    retainedReasoning: turn.reasoning ?? null,
    reasoningChars: turn.reasoning_chars ?? 0,
  };
}

/** The parked approval for each turn that has one, keyed by turn id. */
export function parkedByTurn(detail: SessionDetail): Map<string, ParkedApproval> {
  return new Map((detail.parked_approvals ?? []).map((approval) => [approval.turn_id, approval]));
}

/**
 * A transcript persists prompt text, not the files that rode with it, so a
 * reloaded conversation asks the server which attachments belong to which turn
 * and redraws the chips. Metadata only — no file content is fetched until a
 * chip is actually clicked.
 */
export function attachmentChipsByTurn(
  files: SessionAttachment[],
): Map<string, ComposerAttachment[]> {
  const byTurn = new Map<string, ComposerAttachment[]>();
  for (const file of files) {
    const chips = byTurn.get(file.turn_id) ?? [];
    chips.push({
      kind: file.kind === "image" ? "image" : "document",
      label: file.filename,
      detail: `${file.filename} (${file.media_type}, ${file.byte_size} bytes)`,
      attachmentId: file.attachment_id,
      source: file.source,
      createdAt: file.created_at,
      mediaType: file.media_type,
      byteSize: file.byte_size,
    });
    byTurn.set(file.turn_id, chips);
  }
  return byTurn;
}

/**
 * Merge restored chips into turns that already have some. A generated file is
 * replaced by its stored twin rather than duplicated; anything the composer
 * uploaded and still holds is kept as it is.
 */
export function mergeRestoredChips<
  T extends { response: { turn_id: string } | null; attachments: ComposerAttachment[] },
>(turns: T[], byTurn: Map<string, ComposerAttachment[]>): T[] {
  return turns.map((turn) => {
    const chips = byTurn.get(turn.response?.turn_id ?? "");
    if (chips === undefined) return turn;
    const existing = turn.attachments.filter(
      (a) => a.source !== "generated" || a.attachmentId === undefined,
    );
    const merged = [
      ...existing,
      ...chips.filter((c) => !existing.some((e) => e.attachmentId === c.attachmentId)),
    ];
    return { ...turn, attachments: merged };
  });
}
