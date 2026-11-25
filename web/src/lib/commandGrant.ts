/**
 * RU-07 — the per-conversation command grant, reachable from the approval card.
 *
 * `run_command` runs only under an owner-defined, expiring grant for one
 * conversation (`PUT /api/sessions/{id}/command-grant`); until now no screen
 * could make one. A command approval offers *Allow `python3 -m unittest` in this
 * conversation* when, and only when, the command it shows can be read back as
 * exact words: plain arguments with no quoting, shell operators, globbing,
 * variables or redaction, and not cut short. Anything else keeps Allow once.
 */
import type { ApprovalView } from "./apiTypes";

const COMMAND_TOOLS = new Set(["shell", "run_command", "shell_command"]);
/** A word with nothing a shell would reinterpret. */
const PLAIN_WORD = /^[A-Za-z0-9_./:=@%+,-]+$/;
const MAX_WORDS = 20;

/** Minutes a grant lasts, and the longest one command may run under it. */
export const GRANT_TTL_MINUTES = 480;
export const GRANT_TIMEOUT_SECONDS = 300;

/** The command as exact argument words, or null when it cannot be granted safely. */
export function grantableCommand(view: Pick<ApprovalView, "tool_name" | "target" | "session_id">): string[] | null {
  if (!COMMAND_TOOLS.has(view.tool_name) || !view.session_id) return null;
  const target = view.target.trim();
  if (!target || target.includes("…") || /\[redacted|\*\*\*/i.test(target)) return null;
  const words = target.split(" ");
  if (words.length > MAX_WORDS || words.some((word) => !PLAIN_WORD.test(word))) return null;
  return words;
}
