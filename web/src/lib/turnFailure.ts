/**
 * BUG-285 — what a turn says when it did not finish.
 *
 * Chat and Build each ended a failed turn the same two ways: an `ApiError`
 * became its HTTP status and nothing else, and anything else became
 * **"Could not reach the local runtime."**
 *
 * Both throw away the only part an owner can act on. The runtime names every
 * provider refusal — a rejected key, an exhausted quota, a model the runtime
 * does not hold — and carries that name on the error as a `reason_code`; the
 * status number cannot tell any of them apart. And the blanket sentence is
 * often simply false: a turn that had already streamed tool rows plainly
 * reached the runtime, so telling the owner it could not be reached sends them
 * to check a service that is running.
 *
 * This is the one answer both surfaces use. It says what the runtime said when
 * the runtime said anything, and when it did not, it says what is actually
 * known — that the connection to Raiker ended — without claiming to know why.
 */
import { ApiError } from "./api";
import { explainReasonCode } from "./reasonCodes";

export interface TurnFailureContext {
  /**
   * Whether this turn had already shown the owner something — an answer, a
   * tool row, reasoning. A turn that had cannot honestly be reported as one
   * that never reached anything.
   */
  produced?: boolean;
}

export function turnFailureMessage(
  error: unknown,
  context: TurnFailureContext = {},
): string {
  if (error instanceof ApiError) {
    const explained = explainReasonCode(error.reasonCode);
    if (explained !== null) {
      // The code stays in the sentence. It is what an owner quotes when they
      // ask for help, and what the audit record is searchable by.
      const remediation = explained.remediation ? ` ${explained.remediation}` : "";
      return `${explained.plain}${remediation} (${explained.code})`;
    }
    return `Raiker refused the turn and gave no reason code (HTTP ${error.status}).`;
  }
  if (context.produced === true) {
    return "The connection to Raiker ended before this turn finished. What it had already sent is above.";
  }
  return "The connection to Raiker ended before this turn produced anything. Raiker itself may still be running — check Observability, or send it again.";
}
