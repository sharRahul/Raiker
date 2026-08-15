import type { StreamEvent } from "./apiTypes";

export interface RefusedCall {
  toolName: string;
  reasons: string[];
  remediationRoute?: string;
}

/**
 * The calls policy refused during a turn, in the order they were refused (BUG-52).
 *
 * A refusal used to end the turn, so "denied" plus a reason was the whole story
 * Chat had to tell. Now that a refusal ends only its own call and the batch
 * carries on, the turn finishes normally — and without this the transcript would
 * show a call proposed and simply never answered.
 */
export function refusedCalls(events: StreamEvent[]): RefusedCall[] {
  const calls: RefusedCall[] = [];
  for (const event of events) {
    if (event.kind !== "lifecycle" || event.event_type !== "model_tool_call_refused") continue;
    const payload = event.payload ?? {};
    const toolName = typeof payload.tool_name === "string" ? payload.tool_name : "";
    if (toolName === "") continue;
    const reasons = Array.isArray(payload.reasons)
      ? payload.reasons.filter((reason): reason is string => typeof reason === "string")
      : [];
    const remediationRoute =
      typeof payload.remediation_route === "string" && payload.remediation_route !== ""
        ? payload.remediation_route
        : undefined;
    calls.push({ toolName, reasons, ...(remediationRoute ? { remediationRoute } : {}) });
  }
  return calls;
}

