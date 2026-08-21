/**
 * Build-workspace composer modes: Plan, Edit, Auto.
 *
 * The three modes are not a mood the interface sets on itself — each one is a
 * concrete, server-enforced posture. What changed in BUG-70 is *whose* posture
 * it is.
 *
 * These chips used to POST four `/api/capability-modes/<cap>/<mode>` changes,
 * which rewrote the owner's **standing** permissions: globally, permanently, and
 * without the step-up — a recorded reason, and a threat-model acknowledgement
 * where the capability demands one — that the Permissions page requires for the
 * identical transition. Pressing **Auto** in a composer is not consent to change
 * what every future Chat, Task and Build session may do.
 *
 * So a mode is now built from two per-turn controls only:
 *
 *  1. the `planning_mode` sent with the prompt, and
 *  2. a `capability_modes` map sent with the same prompt, which the runtime
 *     applies to *that turn* and to nothing else.
 *
 * That map may only ever tighten — `ask` and `deny` are the only values the
 * envelope accepts — so a chip can never grant the turn authority the owner has
 * not already given it. **Auto** therefore sends no override at all: it defers
 * to the owner's standing permissions, and the composer says so rather than
 * quietly widening them. Changing standing permissions stays where the ceremony
 * lives, on the Permissions page.
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

/**
 * The modes a *turn* may name for itself. Both tighten; `allow` and `auto` are
 * absent by construction, because loosening is a change to standing authority.
 * `null` means "send no override" — the turn runs under whatever the owner set.
 */
export type BuildTurnMode = "ask" | "deny" | null;

export interface BuildModeSpec {
  id: BuildMode;
  label: string;
  /**
   * One line under the mode name in the picker. It is the only prose a mode
   * carries: the picker's own note states that a mode is turn-scoped and can
   * only tighten, so repeating that per mode was three paragraphs saying the
   * same thing above a composer that has to stay small.
   */
  summary: string;
  /**
   * Turn-scoped decision mode applied to every capability in
   * BUILD_WRITE_CAPABILITIES, or null to send no override and run under the
   * owner's standing permissions.
   */
  turnMode: BuildTurnMode;
  /** Per-turn planning option, or null to leave the backend default alone. */
  planningMode: "always" | "never_safe_only" | null;
}

export const BUILD_MODES: readonly BuildModeSpec[] = [
  {
    id: "plan",
    label: "Plan",
    summary: "Research and propose. No changes.",
    turnMode: "deny",
    planningMode: "always",
  },
  {
    id: "edit",
    label: "Edit",
    summary: "Propose each change and wait for you.",
    turnMode: "ask",
    planningMode: null,
  },
  {
    id: "auto",
    label: "Auto",
    summary: "Follow your standing permissions.",
    turnMode: null,
    planningMode: null,
  },
];

/**
 * Build opens in **Auto**, matching the mode a coding agent is expected to start
 * in. Auto is safe to default to *here* precisely because of BUG-70: it sends no
 * override and therefore adds no authority. A turn in Auto can only do what the
 * owner already allowed on the Permissions page, so opening in it widens
 * nothing — it stops Build from silently tightening below the owner's own
 * settings on every new conversation, which is what defaulting to Edit did.
 */
export const DEFAULT_BUILD_MODE: BuildMode = "auto";

export function buildMode(id: string): BuildModeSpec {
  return (
    BUILD_MODES.find((mode) => mode.id === id) ??
    BUILD_MODES.find((mode) => mode.id === DEFAULT_BUILD_MODE) ??
    BUILD_MODES[0]
  );
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
 * The `capability_modes` map to send with a prompt in this mode. Empty for Auto,
 * which deliberately sends no override.
 */
export function turnCapabilityModes(id: BuildMode): Record<string, string> {
  const mode = buildMode(id).turnMode;
  if (mode === null) return {};
  return Object.fromEntries(BUILD_WRITE_CAPABILITIES.map((capability) => [capability, mode]));
}

/**
 * What the owner's standing permissions mean for the mode they just picked, in
 * one sentence — or null when there is nothing worth saying.
 *
 * This is the honesty half of BUG-70's fix. The chips no longer edit standing
 * permissions, which means **Auto** does exactly as much as the owner already
 * allowed and no more. Saying "low-risk changes run unprompted" over a set of
 * capabilities still at Ask would be the same lie the old chip told, just in the
 * other direction, so the composer reports what it actually found.
 */
export function standingPostureNote(
  id: BuildMode,
  modes: Record<string, string> | null,
): string | null {
  if (id !== "auto") return null;
  if (modes === null) return "Raiker could not read your standing permissions for this turn.";
  const observed = BUILD_WRITE_CAPABILITIES.map((capability) => modes[capability]).filter(
    (mode): mode is string => mode !== undefined,
  );
  if (observed.length !== BUILD_WRITE_CAPABILITIES.length) {
    return "Raiker could not read your standing permissions for this turn.";
  }
  const asking = observed.filter((mode) => mode === "ask").length;
  const denied = observed.filter((mode) => mode === "deny").length;
  if (denied === observed.length) {
    return "Every write capability is set to Deny, so this turn will change nothing.";
  }
  if (asking === observed.length) {
    return "Every write capability is set to Ask, so every change will still be proposed to you.";
  }
  if (asking > 0 || denied > 0) {
    return `${asking + denied} of ${observed.length} write capabilities are still set to Ask or Deny, so some changes will be proposed rather than run.`;
  }
  return "Your standing permissions let low-risk changes run unprompted; medium and higher still ask.";
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
