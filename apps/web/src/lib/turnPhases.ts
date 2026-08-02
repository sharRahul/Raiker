// Maps the lifecycle event_types streamed by the runtime (raiker/runtime/orchestrator.py,
// surfaced via StreamEvent) into the four governed turn phases shown in the timeline:
// gather → plan → act → verify.
import type { StreamEvent } from "./apiTypes";

export type PhaseId = "gather" | "plan" | "act" | "verify";

export const PHASE_ORDER: readonly PhaseId[] = ["gather", "plan", "act", "verify"];

export const PHASE_LABELS: Record<PhaseId, string> = {
  gather: "Gather",
  plan: "Plan",
  act: "Act",
  verify: "Verify",
};

// event_type → phase. Only events the runtime actually streams (via Orchestrator._event)
// appear here; durable-only events (e.g. policy_decision written by the broker) are not streamed.
const EVENT_PHASE: Record<string, PhaseId> = {
  prompt_normalised: "gather",
  intent_classified: "gather",
  risk_classified: "gather",
  context_gathered: "gather",
  plan_created: "plan",
  plan_skipped: "plan",
  // B6 — the agent's own checklist. It belongs in the plan phase whether it was
  // written this turn or carried in from the last one.
  agent_plan_updated: "plan",
  agent_plan_replayed: "plan",
  model_request_started: "act",
  model_request_completed: "act",
  model_request_failed: "act",
  model_tool_call_rejected: "act",
  model_tool_calls_dropped: "act",
  // B7 — a delegated read-only investigation. Metadata only: the findings go to
  // the model, never to the transcript.
  subagent_completed: "act",
  verification_started: "verify",
  verification_completed: "verify",
};

export function phaseForEvent(eventType: string): PhaseId | null {
  return EVENT_PHASE[eventType] ?? null;
}

export interface PhaseRow {
  phase: PhaseId;
  label: string;
  events: StreamEvent[];
}

/** Group streamed lifecycle events into ordered phase rows (empty phases are omitted). */
export function groupPhases(events: StreamEvent[]): PhaseRow[] {
  const byPhase = new Map<PhaseId, StreamEvent[]>();
  for (const ev of events) {
    if (ev.kind !== "lifecycle") continue;
    const phase = phaseForEvent(ev.event_type);
    if (phase === null) continue;
    const bucket = byPhase.get(phase) ?? [];
    bucket.push(ev);
    byPhase.set(phase, bucket);
  }
  const rows: PhaseRow[] = [];
  for (const phase of PHASE_ORDER) {
    const evs = byPhase.get(phase);
    if (evs && evs.length > 0) {
      rows.push({ phase, label: PHASE_LABELS[phase], events: evs });
    }
  }
  return rows;
}

/** Concatenate streamed answer text deltas in arrival order. */
export function collectText(events: StreamEvent[]): string {
  return events
    .filter((ev) => ev.kind === "text_delta")
    .map((ev) => ev.text)
    .join("");
}

/** A short, plain-English summary of a single lifecycle event for the timeline. */
export function summarizeEvent(ev: StreamEvent): string {
  const p = ev.payload ?? {};
  switch (ev.event_type) {
    case "prompt_normalised":
      return "Prompt normalised.";
    case "intent_classified":
      return `Intent: ${str(p.intent)}${p.confidence !== undefined ? ` (confidence ${p.confidence})` : ""}.`;
    case "risk_classified":
      return `Risk: ${str(p.risk_level)}${p.requires_approval ? " — approval required" : ""}.`;
    case "context_gathered":
      return "Workspace context gathered (bounded local metadata only).";
    case "plan_created":
      return "Plan created.";
    case "plan_skipped":
      return "No plan required for this turn.";
    case "agent_plan_updated":
      return `Plan updated: ${str(p.completed)} of ${str(p.total)} step(s) done${p.current_step ? ` — now ${str(p.current_step)}` : ""}.`;
    case "agent_plan_replayed":
      return "The standing plan for this conversation was carried into the turn.";
    case "subagent_completed": {
      const tools = Array.isArray(p.tools_used) ? p.tools_used.join(", ") : "";
      return `Subagent ${str(p.name) || "run"} finished ${str(p.steps_executed)} read-only step(s)${tools ? ` (${tools})` : ""}.`;
    }
    case "model_tool_calls_dropped":
      return `${str(p.accepted)} of ${str(p.proposed)} tool call(s) accepted — ${str(p.reason)}.`;
    case "model_request_started":
      return `Model request started (${str(p.provider)} / ${str(p.model)}).`;
    case "model_request_completed":
      return `Model responded (finish: ${str(p.finish_reason)}${p.tool_call_count !== undefined ? `, ${p.tool_call_count} tool call(s)` : ""}).`;
    case "model_request_failed":
      return `Model request failed safely: ${str(p.safe_error_code) || str(p.finish_reason)}.`;
    case "model_tool_call_rejected":
      return `Tool call rejected: ${str(p.tool_name)} — ${str(p.reason)}.`;
    case "verification_started":
      return "Verification started.";
    case "verification_completed":
      return verificationSummary(p);
    default:
      return ev.event_type;
  }
}

function verificationSummary(p: Record<string, unknown>): string {
  const status = str(p.status) || str(p.result);
  return status ? `Verification completed: ${status}.` : "Verification completed.";
}

function str(v: unknown): string {
  return v === undefined || v === null ? "" : String(v);
}
