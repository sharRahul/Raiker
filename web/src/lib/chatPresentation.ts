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
    const row: ToolCallRow = {
      actionId,
      toolName,
      family: (str(payload.family) || "tool") as ToolFamily,
      label: str(payload.label) || toolName,
      action: str(payload.action),
      state: STATES[str(payload.status)] ?? "running",
      reasons: reasons.length > 0 ? reasons : reason ? [reason] : [],
      ...(remediationRoute ? { remediationRoute } : {}),
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
 * think, or the provider does not return it. It never means reasoning was
 * replaced with something else: the three canned sentences this used to show
 * are gone, and nothing stands in for absent reasoning.
 */
export function collectReasoning(events: StreamEvent[]): string {
  let text = "";
  for (const event of events) {
    if (event.kind !== "reasoning_delta" || event.text.length === 0) continue;
    text += event.text;
  }
  return text;
}
