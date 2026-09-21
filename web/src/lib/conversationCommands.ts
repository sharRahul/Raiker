/**
 * BUG-306 / REM-CHAT-02 — one command set behind every conversation menu.
 *
 * Rename, archive, pin, move and retry are reachable from more than one place —
 * Chat's own header, Threads' Organise control, the session detail — and each
 * place used to own its own copy: its own API call, its own decision about
 * whether to confirm, and its own sentence when it failed. Nothing made them
 * disagree today, which is exactly the condition under which the next change
 * makes one of them disagree quietly.
 *
 * Two things live here rather than in a view.
 *
 * **What each command is.** A command names itself, says whether it is
 * destructive, and carries the sentence to show when it fails. A surface
 * renders the label and calls `run`; it does not decide what "archive" means.
 *
 * **Whether a retry is safe to offer.** This is the part that is not
 * bookkeeping. Retrying re-sends a prompt, and a turn that already ran a tool
 * with an effect outside Raiker — a file written, a command run, a message sent
 * — will run it again. The owner is entitled to be told that before they press
 * it, and only the transcript knows: the answer comes from the turn's own
 * settled calls, not from a guess about the prompt.
 */
import type { ToolCallRow } from "./chatPresentation";

export type CommandId =
  | "rename"
  | "archive"
  | "restore"
  | "pin"
  | "unpin"
  | "move"
  | "tag"
  | "untag";

export interface ConversationCommand {
  id: CommandId;
  /** The owner's word for it, on whichever surface offers it. */
  label: string;
  /**
   * What the failure sentence says this was: "Could not <gerund>."
   * One phrasing, so two surfaces cannot report the same failure differently.
   */
  gerund: string;
  /**
   * Whether the command changes what the owner can find, rather than only what
   * it is called. An archive takes a conversation off the board it is resumed
   * from, so it is confirmed; a rename is not.
   */
  confirms: boolean;
}

const COMMANDS: Record<CommandId, ConversationCommand> = {
  rename: { id: "rename", label: "Rename", gerund: "rename this thread", confirms: false },
  archive: { id: "archive", label: "Archive", gerund: "archive this thread", confirms: true },
  restore: { id: "restore", label: "Restore", gerund: "restore this thread", confirms: false },
  pin: { id: "pin", label: "Pin", gerund: "pin this thread", confirms: false },
  unpin: { id: "unpin", label: "Unpin", gerund: "unpin this thread", confirms: false },
  move: { id: "move", label: "Move to project", gerund: "move this thread", confirms: false },
  tag: { id: "tag", label: "Add tag", gerund: "add the tag", confirms: false },
  untag: { id: "untag", label: "Remove tag", gerund: "remove the tag", confirms: false },
};

export function command(id: CommandId): ConversationCommand {
  return COMMANDS[id];
}

/** The sentence a surface shows when a command did not take. */
export function commandFailure(id: CommandId, status?: number): string {
  const what = COMMANDS[id].gerund;
  return status === undefined ? `Could not ${what}.` : `Could not ${what} (${status}).`;
}

/** What archiving takes away, said before it is done rather than after. */
export function archiveConfirmation(title: string): string {
  return (
    `Archive “${title}”? It leaves the board and keeps everything it holds — ` +
    `its turns, its evidence and its tags. Archived threads are listed under ` +
    `Archived on this page, and Restore brings it back.`
  );
}

/**
 * Tool families whose calls reach outside Raiker, or change something that
 * outlives the turn.
 *
 * A read is safe to repeat: the second read answers the same question. Anything
 * here is not, and the unknown family is treated as an effect rather than as a
 * read — a tool Raiker has no family for is a tool nobody has decided is safe
 * to run twice.
 */
const EFFECTFUL_FAMILIES = new Set(["file-write", "shell", "repository", "connector", "tool"]);

export interface RetryConsequence {
  /** True when re-sending would repeat something that already happened. */
  repeats: boolean;
  /** The calls it would repeat, in the owner's language, for the question. */
  effects: string[];
}

/**
 * Whether retrying this turn would do again what it already did.
 *
 * Only *settled, successful* calls count. A refused call did not happen; a
 * failed one did not complete; a running one belongs to a turn that has not
 * finished, and Retry is not offered there anyway. This is deliberately the
 * narrow reading: warning about a call that never ran would teach an owner to
 * dismiss the warning.
 */
export function retryConsequence(rows: ToolCallRow[]): RetryConsequence {
  const effects = rows
    .filter((row) => row.state === "success" && EFFECTFUL_FAMILIES.has(row.family))
    .map((row) => (row.action ? `${row.label} — ${row.action}` : row.label));
  return { repeats: effects.length > 0, effects };
}

/** The question asked before a retry that would repeat an effect. */
export function retryConfirmation(consequence: RetryConsequence): string {
  const listed = consequence.effects.slice(0, 5).join("\n• ");
  const more =
    consequence.effects.length > 5 ? `\n…and ${consequence.effects.length - 5} more` : "";
  return (
    "Send this again? The first attempt already did these, and Raiker may do them " +
    `a second time:\n\n• ${listed}${more}\n\n` +
    "Raiker cannot tell whether repeating them is safe — that is yours to decide."
  );
}
