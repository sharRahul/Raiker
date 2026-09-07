/**
 * Cadences a scheduled agent can run on.
 *
 * These mirror the server's accepted `recurrence` values exactly — an unknown
 * cadence is refused there rather than quietly stored as a one-shot, so the list
 * here is a presentation of what the runtime will honour, not a superset of it.
 *
 * Every cadence describes the same unit of work: one discrete governed turn per
 * cycle. A "continuous" agent is not a loop the runtime cannot see into; it is a
 * task that re-arms itself after each cycle, so policy, capability gates, and
 * approvals apply to cycle 40 exactly as they did to cycle 1.
 */

export interface AgentCadence {
  id: string;
  label: string;
  detail: string;
}

export const AGENT_CADENCES: readonly AgentCadence[] = [
  {
    id: "continuous",
    label: "Keep going",
    detail:
      "Runs a cycle roughly every 20 minutes and re-arms itself, so the work keeps moving until you stop it.",
  },
  {
    id: "hourly",
    label: "Hourly",
    detail: "One cycle an hour — enough to watch something without crowding the queue.",
  },
  {
    id: "daily",
    label: "Daily",
    detail: "One cycle a day, anchored to the time of its first run.",
  },
  {
    id: "weekly",
    label: "Weekly",
    detail: "One cycle a week, for slow-moving work you still want to keep an eye on.",
  },
  {
    id: "background",
    label: "Once, in the background",
    detail: "A single governed cycle that starts now and finishes on its own. It does not repeat.",
  },
];

const CADENCE_RUNNING_LABELS: Record<string, string> = {
  continuous: "Keeps going until stopped",
  hourly: "Runs hourly",
  daily: "Runs daily",
  weekly: "Runs weekly",
  background: "One background run",
};

/**
 * How a running task's cadence should read in a list. An unrecognised value is
 * shown verbatim rather than dropped, so a schedule created by another client is
 * never silently mislabelled as a one-shot.
 */
export function cadenceLabel(recurrence: string): string {
  return CADENCE_RUNNING_LABELS[recurrence] ?? `Repeats (${recurrence})`;
}
