/**
 * What first launch asks, in what order, and what it recommends.
 *
 * The secure opening boundary — runtime reachability, encrypted-store
 * availability, owner registration versus unlock, bootstrap verification before
 * the workspace mounts — is not in this file and is not changed by it. What is
 * here is the part that came after: a five-stage configuration wizard
 * (`Account → Model → Privacy → Backup → Finish`) that asked an owner to
 * understand infrastructure before they had used the product once.
 *
 * Four things move, and each is a separate decision:
 *
 * * **Account leaves.** The owner account is created on the first screen. A
 *   stage called Account after that implied a second account to configure.
 * * **Welcome arrives.** Chat, Build and Design are the product; an owner
 *   should meet them before a provider matrix.
 * * **Backup leaves the stages.** It is important and it is not a gate. Asking
 *   for a NAS path before first use is friction in front of the work; it is
 *   offered at the end and recommended on Home instead.
 * * **Privacy becomes a question about data travel**, not a second authority
 *   system standing beside Permissions.
 */
import type { ModelProfile } from "./apiTypes";
import { providerName } from "./format";
import { isReachableProfile } from "./modelReadiness.svelte";

/** The stages first launch actually shows, in order. */
export const SETUP_STAGES = ["welcome", "model", "privacy", "finish"] as const;

export type SetupStage = (typeof SETUP_STAGES)[number];

export const SETUP_STAGE_LABELS: Record<SetupStage, string> = {
  welcome: "Welcome",
  model: "Model",
  privacy: "Privacy",
  finish: "Ready",
};

/**
 * Where a stored setup row lands on today's rail.
 *
 * `account` and `backup` are still valid stored values — an instance part-way
 * through the old wizard must not fail to render — so they resolve to the stage
 * that now carries their meaning rather than to a blank screen.
 */
export function visibleStage(stage: string | null | undefined): SetupStage {
  if (stage === "model" || stage === "privacy" || stage === "welcome") return stage;
  if (stage === "backup" || stage === "finish") return "finish";
  return "welcome"; // including the retired `account`
}

/** The two answers to "where may Raiker send model requests?" (FIRST-07). */
export const PRIVACY_CHOICES = [
  {
    mode: "local_first" as const,
    label: "Local only",
    detail:
      "Model requests stay on this device. Nothing is sent to a provider until you connect one and change this.",
  },
  {
    mode: "balanced" as const,
    label: "Local, and the providers I connect",
    detail:
      "Requests may go to providers you have connected. Nothing reaches a provider you have not set up.",
  },
];

/**
 * One sentence about permissions, instead of the matrix (FIRST-10).
 *
 * Sixty-six gates is a page an owner visits when they have a reason to. On
 * first run the useful fact is the posture, not the inventory.
 */
export const PERMISSIONS_NOTE =
  "Raiker starts conservatively and will ask you before it takes a governed action. You can review every permission later.";

export interface RecommendedPath {
  /** "" when nothing is detected or connected and the owner must choose. */
  profileId: string;
  provider: string;
  label: string;
  detail: string;
}

/**
 * The easiest path to a working model, or none.
 *
 * FIRST-05 — the first screen should not be the full provider matrix. A runtime
 * already running on this machine needs no account and no key, so it is the
 * cheapest true answer to "where should Raiker think"; a provider already
 * connected is next. When neither holds there is no recommendation to make, and
 * inventing one would be a screen guessing on the owner's behalf.
 */
export function recommendedPath(profiles: ModelProfile[]): RecommendedPath | null {
  // REM-MODEL-01 — the recommendation passes through the one reachability
  // answer, so a runtime this machine is running but whose last check found no
  // model, or a connected account whose key was rejected, is not offered as the
  // cheapest path to a working model.
  const detected = profiles.find(
    (profile) =>
      profile.local_only && profile.provider_detected === true && isReachableProfile(profile),
  );
  if (detected) {
    return {
      profileId: detected.profile_id,
      provider: detected.provider,
      label: `${providerName(detected.provider)} is already running here`,
      detail:
        "It needs no account and no API key, and its models never leave this device.",
    };
  }
  const connected = profiles.find(
    (profile) => profile.connection_configured === true && isReachableProfile(profile),
  );
  if (connected) {
    return {
      profileId: connected.profile_id,
      provider: connected.provider,
      label: `${providerName(connected.provider)} is connected`,
      detail: "Choose one of its models as your default, or connect another provider.",
    };
  }
  return null;
}
