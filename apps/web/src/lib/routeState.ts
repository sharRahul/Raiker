/**
 * Non-secret, shareable route state for the workbench shell.  This deliberately
 * rejects unknown keys: credentials, request payloads, and policy decisions
 * belong to the governed API, never a browser URL.
 */
export interface RouteState {
  projectId: string | null;
  sessionId: string | null;
  /**
   * MEM-08 — the exchange inside `sessionId` a link is pointing at. A
   * coordinate, exactly like the session id beside it: it names a turn the
   * reader may already open, and grants nothing that opening the conversation
   * did not already grant.
   */
  turnId: string | null;
  recordId: string | null;
  filter: string | null;
  tab: string | null;
}

const ROUTE_STATE_KEYS = ["project", "session", "turn", "record", "filter", "tab"] as const;

function safeValue(value: string | null): string | null {
  if (value === null || value.length === 0 || value.length > 256) return null;
  return value;
}

export function routeStateFromHash(hash: string): RouteState {
  const query = hash.split("?", 2)[1] ?? "";
  const params = new URLSearchParams(query);
  const values = Object.fromEntries(
    ROUTE_STATE_KEYS.map((key) => [key, safeValue(params.get(key))]),
  ) as Record<(typeof ROUTE_STATE_KEYS)[number], string | null>;
  return {
    projectId: values.project,
    sessionId: values.session,
    turnId: values.turn,
    recordId: values.record,
    filter: values.filter,
    tab: values.tab,
  };
}
