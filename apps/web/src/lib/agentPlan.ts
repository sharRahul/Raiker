// B6 — reading the agent's plan out of a live turn.
//
// The runtime emits `agent_plan_updated` as a lifecycle event carrying the whole
// plan, so a checklist can update while the turn runs rather than only when it
// ends. The payload crosses the wire as `Record<string, unknown>`, so it is
// validated here — once, in one place, shared by Chat and Build — instead of
// being cast at each call site and trusted.
import type { AgentPlan, AgentPlanStep, StreamEvent } from "./apiTypes";

export const PLAN_EVENT = "agent_plan_updated";

const STATUSES: readonly AgentPlanStep["status"][] = [
  "pending",
  "in_progress",
  "completed",
  "blocked",
];

function toStep(raw: unknown): AgentPlanStep | null {
  if (typeof raw !== "object" || raw === null) return null;
  const entry = raw as Record<string, unknown>;
  const title = typeof entry.title === "string" ? entry.title.trim() : "";
  if (title === "") return null;
  const status = STATUSES.find((candidate) => candidate === entry.status) ?? "pending";
  const note = typeof entry.note === "string" ? entry.note : undefined;
  return note ? { title, status, note } : { title, status };
}

/** A validated plan, or null when the payload carries no usable steps. */
export function planFromPayload(payload: Record<string, unknown>): AgentPlan | null {
  const rawSteps = payload.steps;
  if (!Array.isArray(rawSteps)) return null;
  const steps = rawSteps.map(toStep).filter((step): step is AgentPlanStep => step !== null);
  if (steps.length === 0) return null;
  return {
    session_id: typeof payload.session_id === "string" ? payload.session_id : "",
    steps,
    updated_at: typeof payload.updated_at === "string" ? payload.updated_at : undefined,
  };
}

/** The plan carried by one streamed event, or null when it is not a plan event. */
export function planFromEvent(event: StreamEvent): AgentPlan | null {
  if (event.kind !== "lifecycle" || event.event_type !== PLAN_EVENT) return null;
  return planFromPayload(event.payload ?? {});
}

/** True when a fetched plan has anything worth showing. */
export function hasSteps(plan: AgentPlan | null): plan is AgentPlan {
  return plan !== null && Array.isArray(plan.steps) && plan.steps.length > 0;
}
