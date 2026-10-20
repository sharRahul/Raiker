/**
 * PA-D06 — how a goal reads, in one place, so Home, Work → Goals and Settings
 * say the same thing about the same state.
 *
 * Every label here describes a fact the server sent. The actions a goal offers
 * come from its own `allowed_actions`; nothing here decides what may be done,
 * and no state is inferred from a step's prose.
 */
import type { BadgeVariant } from "./types";
import type { ExecutionProfileView, GoalView } from "./generated/apiContract";

export const GOAL_STATE_LABELS: Record<string, string> = {
  draft: "Draft",
  ready: "Ready to start",
  running: "Working",
  waiting: "Waiting",
  paused: "Paused",
  completed: "Completed",
  partial: "Partly done",
  failed: "Failed",
  stopped: "Stopped",
  archived: "Archived",
};

const STATE_BADGES: Record<string, BadgeVariant> = {
  draft: "idle",
  ready: "idle",
  running: "active",
  waiting: "needs-approval",
  paused: "stopped",
  completed: "done",
  partial: "metadata-only",
  failed: "blocked",
  stopped: "stopped",
  archived: "metadata-only",
};

export function goalBadge(status: string): { variant: BadgeVariant; label: string } {
  return { variant: STATE_BADGES[status] ?? "idle", label: GOAL_STATE_LABELS[status] ?? status };
}

export const STEP_STATE_LABELS: Record<string, string> = {
  pending: "Not started",
  running: "Working",
  waiting: "Waiting",
  done: "Finished",
  failed: "Failed",
  stopped: "Stopped",
  blocked: "Will not start",
};

export const STEP_REASONS: Record<string, string> = {
  needs_decision: "waiting for your decision",
  needs_answer: "waiting for your answer",
  waiting_on_delegated_work: "waiting on work it delegated",
  step_paused: "paused",
  dependency_not_finished: "a step it depends on did not finish",
  goal_stopped: "the goal was stopped",
  task_missing: "its task no longer exists",
  dispatch_interrupted: "Raiker stopped while starting it",
  dispatching: "starting",
};

export const VALIDATOR_LABELS: Record<string, string> = {
  steps_finish: "Met when its steps finish",
  owner_confirms: "You confirm it",
};

export function evidenceLabel(kind: string | null | undefined): string | null {
  if (kind === "steps_finished") return "Its steps finished";
  if (kind === "owner_confirmed") return "Confirmed by you";
  return null;
}

export const ACTION_LABELS: Record<string, string> = {
  accept: "Accept plan",
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  stop: "Stop goal",
  archive: "Archive",
};

/** The buttons a goal's state offers, in the order they are drawn. `edit` and `confirm` are drawn in place. */
export function goalButtons(goal: Pick<GoalView, "allowed_actions">): string[] {
  return ["accept", "start", "resume", "pause", "stop", "archive"].filter((a) => goal.allowed_actions.includes(a));
}

/** "1 of 2 steps finished" — counts, never a percentage the server did not measure. */
export function stepProgress(goal: Pick<GoalView, "steps">): string {
  const done = goal.steps.filter((s) => s.state === "done").length;
  return `${done} of ${goal.steps.length} step${goal.steps.length === 1 ? "" : "s"} finished`;
}

const NEEDS_YOU = new Set(["needs_decision", "needs_answer", "profile_blocks_model", "no_execution_profile", "budget_exhausted", "profile_changed"]);

/**
 * Home's three questions: what needs me, what is moving, what finished.
 *
 * A goal needs the owner when its state offers an owner-only next step
 * (accept, start, resume, confirm on a partial result) or when it waits on a
 * decision, an answer or a Settings change. Drafts the owner is still writing
 * are not listed on Home.
 */
export function homeGoalGroups(goals: GoalView[]): { needsYou: GoalView[]; moving: GoalView[]; finished: GoalView[] } {
  const needsYou: GoalView[] = [];
  const moving: GoalView[] = [];
  const finished: GoalView[] = [];
  for (const goal of goals) {
    if (goal.status === "draft" || goal.status === "archived") continue;
    if (goal.status === "ready" || goal.status === "paused" || goal.status === "partial" || NEEDS_YOU.has(goal.reason)) {
      needsYou.push(goal);
    } else if (goal.status === "running" || goal.status === "waiting") {
      moving.push(goal);
    } else {
      finished.push(goal);
    }
  }
  return { needsYou, moving, finished: finished.slice(0, 5) };
}

/** One sentence for what a profile admits, as Goals shows it read-only. */
export function profileSummary(profile: ExecutionProfileView | null | undefined): string {
  if (!profile) return "No execution profile is chosen.";
  const where =
    profile.allow_local && profile.allow_hosted
      ? "Local and hosted models"
      : profile.allow_local
        ? "Only models on this machine"
        : "Only hosted models";
  const providers = profile.allowed_providers.length ? ` (${profile.allowed_providers.join(", ")})` : "";
  const memory = profile.allow_hosted
    ? profile.memory_to_hosted
      ? "personal memory may go to the hosted model"
      : "personal memory stays off hosted models"
    : "nothing leaves this machine";
  const cost = profile.max_cost_usd != null ? `, at most $${profile.max_cost_usd.toFixed(2)}` : "";
  return `${where}${providers}; ${memory}; up to ${profile.max_step_runs} step runs${cost} per goal.`;
}

/** "$0.12 of $5.00 spent" or "$0.12 spent" — reconciled from the usage ledger. */
export function budgetLine(goal: Pick<GoalView, "budget">): string {
  const b = goal.budget;
  const runs = b.max_step_runs != null ? `${b.step_runs} of ${b.max_step_runs} step runs` : `${b.step_runs} step runs`;
  const spend = b.max_cost_usd != null ? `$${b.spent_usd.toFixed(2)} of $${b.max_cost_usd.toFixed(2)} spent` : `$${b.spent_usd.toFixed(2)} spent`;
  const unpriced = b.unpriced_models.length ? ` (not priced: ${b.unpriced_models.join(", ")})` : "";
  return `${runs} · ${spend}${unpriced}`;
}

const REFUSALS: Record<string, string> = {
  goal_revision_stale: "This goal changed since you opened it. It has been reloaded — check it and try again.",
  no_execution_profile: "Choose an execution profile in Settings → Execution profiles before accepting a goal.",
  profile_changed: "The execution profile changed. Resume rechecks the goal against the new one.",
  profile_blocks_model: "The execution profile does not allow a model this goal's work would use",
  budget_exhausted: "The goal's budget is used up",
  goal_needs_mandatory_criterion: "Add at least one required success criterion.",
  goal_needs_step: "Add at least one step.",
  goal_needs_model: "Choose the model the steps run on, then accept the plan.",
  goal_model_not_configured: "The model this goal names is no longer set up. Edit the plan and choose another.",
  goal_model_pair_required: "Choose both a provider and a model.",
  goal_criterion_has_no_step: "A criterion that is met when its steps finish needs at least one step counting toward it",
  goal_build_step_requires_project: "A Build step needs the goal to be filed in a project",
  goal_step_dependency_invalid: "A step can only run after steps listed before it",
  execution_profile_version_stale: "This profile changed since you opened it. It has been reloaded.",
  profile_allows_no_model: "A profile has to allow local models, hosted models, or both.",
  profile_providers_invalid: "Provider names are letters, numbers, dots, dashes and underscores, at most 20.",
  profile_budget_invalid: "Step runs are 1–100, and a cost limit is above $0 and at most $1,000.",
  human_principal_required: "Only you can do this, from your own signed-in session.",
};

/** The owner-facing sentence for a refused goal or profile change. */
export function goalRefusal(code: string | null | undefined, fallback = "That did not work."): string {
  if (!code) return fallback;
  const [head, ...rest] = code.split(":");
  const sentence = REFUSALS[code] ?? REFUSALS[head];
  if (!sentence) return `${fallback} (${code})`;
  const detail = rest.join(":");
  if (head === "profile_blocks_model" && detail) return `${sentence}: ${detail}. Change the profile in Settings or your models.`;
  if (head === "budget_exhausted" && detail) return `${sentence}: ${detail}.`;
  return sentence;
}
