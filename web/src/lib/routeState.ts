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
  /**
   * NEW-PROJ-02 — the asset a link is pointing at, on a surface whose object is
   * an asset. A project's image strip could show eight pictures and offer no
   * way to open one of them: the only continuation was a bare `#/design`, so
   * finding the image you had just been looking at meant searching the whole
   * account's Design history for it.
   *
   * A coordinate, like the session and turn ids beside it. It names a
   * generation the reader may already open and grants nothing — the gallery it
   * resolves against is owner-scoped on the server, so an id belonging to
   * somebody else resolves to nothing at all.
   */
  assetId: string | null;
  /**
   * BUG-299 — the task a link is pointing at. The same kind of coordinate as
   * the session and asset ids beside it: it names a task the reader may already
   * open, and grants nothing, because the detail route is scoped to the
   * account's own visible tasks on the server. A task belonging to somebody
   * else resolves to nothing at all.
   */
  taskId: string | null;
  filter: string | null;
  tab: string | null;
}

const ROUTE_STATE_KEYS = [
  "project",
  "session",
  "turn",
  "record",
  "asset",
  "task",
  "filter",
  "tab",
] as const;

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
    assetId: values.asset,
    taskId: values.task,
    filter: values.filter,
    tab: values.tab,
  };
}
