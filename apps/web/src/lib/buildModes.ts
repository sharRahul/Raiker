/**
 * Build-workspace composer modes: Plan, Edit, Auto.
 *
 * The three modes are not a mood the interface sets on itself — each one is a
 * concrete, server-enforced posture built from two existing governed controls:
 *
 *  1. the per-turn `planning_mode` sent with the prompt, and
 *  2. the standing per-capability **decision mode** for the capabilities that a
 *     coding turn actually acts through (`ask` | `auto` | `deny`).
 *
 * That means a mode is honest by construction: switching to Plan does not merely
 * ask the model to behave, it sets the write capabilities to `deny`, so a write
 * proposed anyway is blocked by the runtime rather than by good intentions.
 * Nothing here grants authority — `ask` and `deny` only ever tighten behaviour,
 * and `auto` still refuses anything above the low-risk floor (medium/high ask,
 * critical always requires a human).
 */

export type BuildMode = "plan" | "edit" | "auto";

/**
 * The capabilities a coding turn changes the workspace through. Read-only work
 * (searching, reading files, reading a connected GitHub repository) is deliberately
 * absent: Plan mode has to stay *useful*, so it tightens only the acting
 * capabilities and leaves reads alone.
 */
export const BUILD_WRITE_CAPABILITIES = [
  "file_write_execution",
  "patch_apply_execution",
  "shell_execution",
  "process_execution",
] as const;

export type BuildDecisionMode = "ask" | "auto" | "deny";

export interface BuildModeSpec {
  id: BuildMode;
  label: string;
  /** One line under the mode name in the picker. */
  summary: string;
  /** What the runtime will actually do — shown as the composer's hint line. */
  detail: string;
  /** Standing decision mode applied to every capability in BUILD_WRITE_CAPABILITIES. */
  decisionMode: BuildDecisionMode;
  /** Per-turn planning option, or null to leave the backend default alone. */
  planningMode: "always" | "never_safe_only" | null;
}

export const BUILD_MODES: readonly BuildModeSpec[] = [
  {
    id: "plan",
    label: "Plan",
    summary: "Research and propose. No changes.",
    detail:
      "Raiker plans the work and writes nothing: file writes, patches, and commands are set to deny, so a change proposed anyway is blocked by the runtime.",
    decisionMode: "deny",
    planningMode: "always",
  },
  {
    id: "edit",
    label: "Edit",
    summary: "Propose each change and wait for you.",
    detail:
      "Every file write, patch, and command becomes a decision you accept or reject. Accepting records your decision — Raiker never treats a recorded decision as permission it already had.",
    decisionMode: "ask",
    planningMode: null,
  },
  {
    id: "auto",
    label: "Auto",
    summary: "Let Raiker decide, within the safe floor.",
    detail:
      "Low-risk changes run unprompted; medium and high risk still ask, and critical actions always require a human. The floor is enforced by the runtime, not by this page.",
    decisionMode: "auto",
    planningMode: null,
  },
];

export const DEFAULT_BUILD_MODE: BuildMode = "edit";

export function buildMode(id: string): BuildModeSpec {
  return BUILD_MODES.find((mode) => mode.id === id) ?? BUILD_MODES[1];
}

/**
 * The next mode when cycling. Shift+Tab walks Plan → Edit → Auto → Plan, so the
 * posture can be changed without leaving the prompt.
 */
export function nextBuildMode(current: BuildMode): BuildMode {
  const index = BUILD_MODES.findIndex((mode) => mode.id === current);
  return BUILD_MODES[(index + 1) % BUILD_MODES.length].id;
}

/**
 * The mode a set of live decision modes already represents, or null when the
 * capabilities disagree with each other (someone set them individually in
 * Permissions). Null is reported rather than guessed: showing "Edit" over a
 * half-denied posture would be a lie about what the runtime will do.
 */
export function modeFromDecisionModes(modes: Record<string, string>): BuildMode | null {
  const observed = BUILD_WRITE_CAPABILITIES.map((capability) => modes[capability]).filter(
    (mode): mode is string => mode !== undefined,
  );
  if (observed.length !== BUILD_WRITE_CAPABILITIES.length) return null;
  const unique = new Set(observed);
  if (unique.size !== 1) return null;
  const [only] = unique;
  return BUILD_MODES.find((mode) => mode.decisionMode === only)?.id ?? null;
}

/**
 * Prompt preamble for a connected repository, or "" when there is nothing to say.
 *
 * A local repository needs no preamble — its path rides the turn as a real
 * attachment through the governed attachment path. A GitHub repository has no
 * such handle, so the coordinate is stated in the prompt itself. It is returned
 * (rather than injected server-side) so the transcript shows the user the exact
 * text that was sent.
 */
export function repoPreamble(
  repo: { kind: string; github_owner?: string | null; github_repo?: string | null; branch?: string | null } | null,
): string {
  if (repo === null || repo.kind !== "github") return "";
  if (!repo.github_owner || !repo.github_repo) return "";
  const branch = repo.branch ? ` (branch ${repo.branch})` : "";
  return `Repository: ${repo.github_owner}/${repo.github_repo}${branch}.`;
}
