import type { StreamEvent } from "./apiTypes";
import type { IconName } from "./icons";

/**
 * The families the runtime sorts tools into (`raiker/tools/presentation.py`).
 * `tool` is the neutral fallback for anything it does not recognise.
 */
export type ToolFamily =
  | "file-read"
  | "file-write"
  | "shell"
  | "web"
  | "repository"
  | "connector"
  | "memory"
  | "subagent"
  | "plan"
  | "tool";

/** One glyph per family (BUG-206 slice C). An unknown family is still a tool. */
const FAMILY_ICON: Record<ToolFamily, IconName> = {
  "file-read": "file",
  "file-write": "file-edit",
  shell: "terminal",
  web: "globe",
  repository: "branch",
  connector: "connections",
  memory: "memory",
  subagent: "agent",
  plan: "tasks",
  tool: "tool",
};

export function familyIcon(family: string): IconName {
  return FAMILY_ICON[family as ToolFamily] ?? "tool";
}

/**
 * What happened to one call, in the order the transcript cares about: still
 * running, waiting on the owner, finished, or stopped before it ran.
 */
export type ToolCallState =
  | "running"
  | "waiting"
  | "success"
  | "failed"
  | "denied"
  | "refused";

export interface ToolCallRow {
  /** The action id, which is what pairs a `tool_started` with its outcome. */
  actionId: string;
  toolName: string;
  family: ToolFamily;
  /** The tool in the owner's language, resolved server-side. */
  label: string;
  /** What it acted on. Resolved and redacted server-side; never assembled here. */
  action: string;
  state: ToolCallState;
  /** Named reasons, present only for a refusal or a failure. */
  reasons: string[];
  remediationRoute?: string;
  /** TOOL-72 — a suggested connection: the card under the row, from the catalogue. */
  connection?: ConnectionSuggestion;
  /** A web read's alerts (owner's decision 2026-10-25: alert, never refuse). */
  alerts?: { kind: string; message: string }[];
}

function alertsFrom(raw: unknown): { kind: string; message: string }[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((entry): entry is Record<string, unknown> => typeof entry === "object" && entry !== null)
    .map((entry) => ({ kind: str(entry.kind), message: str(entry.message) }))
    .filter((entry) => entry.message !== "")
    .slice(0, 6);
}

export interface ConnectionSuggestion {
  connectorId: string;
  service: string;
  connected: boolean;
  /** Model-written; rendered as text. */
  reason: string;
  href: string;
}

function connectionFrom(raw: unknown): ConnectionSuggestion | null {
  if (typeof raw !== "object" || raw === null) return null;
  const entry = raw as Record<string, unknown>;
  const connectorId = str(entry.connector_id);
  const href = str(entry.href);
  // Only an address inside Raiker's own Connections page is drawn as a link.
  if (connectorId === "" || !href.startsWith("#/connections?add=")) return null;
  return {
    connectorId,
    service: str(entry.service) || connectorId,
    connected: entry.connected === true,
    reason: str(entry.reason),
    href,
  };
}

const STATES: Record<string, ToolCallState> = {
  running: "running",
  waiting: "waiting",
  success: "success",
  failed: "failed",
  denied: "denied",
  refused: "refused",
};

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/**
 * Every tool call this turn made, in call order (BUG-206 slices D and E).
 *
 * Built only from `kind: "tool"` events, which the runtime emits beside the
 * durable `tool_started` / `tool_completed` / `tool_failed` record. The client
 * never derives a row from raw arguments: the family, the label and the action
 * phrase are decided in `raiker/tools/presentation.py`, where the same redaction
 * the event log applies is applied first. A row here can therefore never say
 * more than the audit trail does.
 *
 * A call is keyed by its action id, so the settled event replaces the pending
 * one in place rather than adding a second line. A call that failed before it
 * ever started — an unperformable proposal, a contained capability — arrives as
 * one event and opens its row already settled.
 */
export function toolActivity(events: StreamEvent[]): ToolCallRow[] {
  const rows: ToolCallRow[] = [];
  const byAction = new Map<string, number>();
  for (const event of events) {
    if (event.kind !== "tool") continue;
    const payload = event.payload ?? {};
    const toolName = str(payload.tool_name);
    if (toolName === "") continue;
    const actionId = str(payload.action_id) || `${toolName}:${rows.length}`;
    const reasons = Array.isArray(payload.reasons)
      ? payload.reasons.filter((reason): reason is string => typeof reason === "string")
      : [];
    const reason = str(payload.reason);
    const remediationRoute = str(payload.remediation_route);
    const connection = connectionFrom(payload.connection);
    const alerts = alertsFrom(payload.alerts);
    const row: ToolCallRow = {
      actionId,
      toolName,
      family: (str(payload.family) || "tool") as ToolFamily,
      label: str(payload.label) || toolName,
      action: str(payload.action),
      state: STATES[str(payload.status)] ?? "running",
      reasons: reasons.length > 0 ? reasons : reason ? [reason] : [],
      ...(remediationRoute ? { remediationRoute } : {}),
      ...(connection ? { connection } : {}),
      ...(alerts.length > 0 ? { alerts } : {}),
    };
    const existing = byAction.get(actionId);
    if (existing === undefined) {
      byAction.set(actionId, rows.length);
      rows.push(row);
      continue;
    }
    // Merge, never replace. A later event can legitimately carry less than the
    // one that opened the row — the event that settles a call after an approval
    // names the action and its outcome and nothing else, because the row it is
    // settling already knows the rest. Replacing would blank the label and the
    // action phrase at the exact moment the owner looks to see what happened.
    const before = rows[existing];
    rows[existing] = {
      ...before,
      ...row,
      family: row.family !== "tool" ? row.family : before.family,
      label: str(payload.label) || before.label,
      action: row.action || before.action,
      reasons: row.reasons.length > 0 ? row.reasons : before.reasons,
      ...(row.remediationRoute || before.remediationRoute
        ? { remediationRoute: row.remediationRoute ?? before.remediationRoute }
        : {}),
      ...(row.connection || before.connection ? { connection: row.connection ?? before.connection } : {}),
      ...(row.alerts || before.alerts ? { alerts: row.alerts ?? before.alerts } : {}),
    };
  }
  return rows;
}

/** True while at least one call on this turn has not settled. */
export function hasRunningTool(rows: ToolCallRow[]): boolean {
  return rows.some((row) => row.state === "running");
}

/**
 * The model's own reasoning for this turn, in arrival order (BUG-207 slice C).
 *
 * Empty means the turn produced none — reasoning was off, the model did not
 * think, or the provider does not return it. Nothing stands in for absent
 * reasoning.
 */
export function collectReasoning(events: StreamEvent[]): string {
  let text = "";
  for (const event of events) {
    if (event.kind !== "reasoning_delta" || event.text.length === 0) continue;
    text += event.text;
  }
  return text;
}

/**
 * QUI-C03 — the one line above the running turn's controls that says what it
 * is doing now.
 *
 * Read from the turn's own events, never invented: a call waiting on the owner
 * wins, then the call in flight (its label and what it acts on, both resolved
 * server-side). Otherwise it says nothing: before the first token the
 * transcript already shows its own "Working…", and an answer being written is
 * on screen as it arrives. No percentages and no "thinking".
 */
export function workingLine(rows: readonly ToolCallRow[]): string {
  const waiting = rows.find((row) => row.state === "waiting");
  // QUI-F02 — a question is not a decision: the turn waits for an answer.
  if (waiting) return waiting.toolName === "ask_owner_question" ? "Waiting for your answer" : "Waiting for your decision";
  const inFlight = [...rows].reverse().find((row) => row.state === "running");
  if (inFlight) return inFlight.action ? `${inFlight.label} · ${inFlight.action}` : inFlight.label;
  return "";
}

export interface TurnOutcome {
  readonly label: "Completed" | "Partially completed" | "Not done" | "Outcome unknown";
  readonly detail: string;
  readonly tone: "done" | "partial" | "not-done" | "unknown";
}

/**
 * QUI-C03 — one line under a settled turn that did something, saying how it
 * ended.
 *
 * Only for turns that used tools: a plain answer needs no "Completed" under it.
 * Stopped and parked turns already say so in their own words. A call that
 * never reported an outcome makes the whole turn's outcome unknown, because
 * Raiker cannot say whether it happened; a refused or failed call among
 * successful ones makes it partial.
 */
export function turnOutcome(status: string | null | undefined, rows: readonly ToolCallRow[]): TurnOutcome | null {
  if (!status || status === "stopped" || status === "needs_approval") return null;
  if (status === "failed") return { label: "Not done", detail: "The turn failed before it finished.", tone: "not-done" };
  if (status === "denied") return { label: "Not done", detail: "An action it needed was not allowed.", tone: "not-done" };
  if (rows.length === 0) return null;
  const unsettled = rows.filter((row) => row.state === "running" || row.state === "waiting").length;
  const stopped = rows.filter((row) => row.state === "failed" || row.state === "denied" || row.state === "refused").length;
  const steps = `${rows.length} step${rows.length === 1 ? "" : "s"}`;
  if (unsettled > 0) {
    return { label: "Outcome unknown", detail: `${unsettled} of ${steps} did not report how it ended.`, tone: "unknown" };
  }
  if (stopped > 0) {
    return { label: "Partially completed", detail: `${stopped} of ${steps} did not go through.`, tone: "partial" };
  }
  return { label: "Completed", detail: steps, tone: "done" };
}
