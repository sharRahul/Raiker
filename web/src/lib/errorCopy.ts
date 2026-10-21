/**
 * QUI-G06 — errors that say what to do.
 *
 * Every error an owner reads names three things, in this order: what failed,
 * what that affected, and one safe next step. A status code is evidence, not
 * an explanation, so it rides along in brackets after the first part rather
 * than standing in for it ("Stop failed (500).").
 */
import { ApiError } from "./api";

/** What an owner reads when Raiker itself did not answer. */
export const NOT_ANSWERING = "Raiker did not answer. Check that it is still running, then try again.";

/**
 * One sentence of each: `failure("Stop was not sent", "The turn is still
 * running.", "Try again.", error)` → "Stop was not sent (HTTP 500). The turn is
 * still running. Try again." An error that never reached Raiker says so in
 * place of the status and the step, because the step is then always the same.
 */
export function failure(what: string, affected: string, next: string, error?: unknown): string {
  if (error !== undefined && !(error instanceof ApiError)) return `${what}. ${affected} ${NOT_ANSWERING}`;
  const code = error instanceof ApiError ? ` (HTTP ${error.status}${error.reasonCode ? `, ${error.reasonCode}` : ""})` : "";
  return `${what}${code}. ${affected} ${next}`;
}
