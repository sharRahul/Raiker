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
import { remoteDestinations } from "./inferenceLocation";
import { isReachableProfile } from "./modelReadiness.svelte";

/**
 * The stages first launch actually shows, in order.
 *
 * DIST-05/06 add three, each a reading rather than a decision an owner must
 * understand infrastructure to make: **This device** (what the machine can
 * run, measured locally), **Permissions** (the governance posture setup leaves
 * in place — read-only, it grants nothing) and **Check** (each mandatory
 * component, verified from inside the running host, plus one real request to
 * the chosen model when there is one).
 */
export const SETUP_STAGES = ["welcome", "system", "model", "privacy", "permissions", "verify", "finish"] as const;

export type SetupStage = (typeof SETUP_STAGES)[number];

export const SETUP_STAGE_LABELS: Record<SetupStage, string> = {
  // QUI-W02 — the stored `welcome` stage is now the Hello step: "What should
  // I call you?". The progress line reads Name · Model · Privacy · Start.
  welcome: "Name",
  system: "This device",
  model: "Model",
  privacy: "Privacy",
  permissions: "Permissions",
  verify: "Check",
  finish: "Start",
};

/**
 * The stages the installer already covered.
 *
 * DIST-05 — a packaged desktop installation checks this computer during
 * installation (the Windows installer's own page, the Linux package's
 * pre-install check, and the Setup window every desktop build opens before
 * Raiker does) and verifies every component before the owner account exists.
 * Asking again after sign-in would repeat a check the owner has just watched
 * pass, so those installations skip **This device** and **Check**. A source
 * checkout or a server install has had no such step and keeps both.
 */
export const INSTALLER_STAGES: readonly SetupStage[] = ["system", "verify"];

/**
 * Stages no installation shows any more (Quiet UI).
 *
 * **Permissions** was a read-only summary of a page that exists (Permissions)
 * and changed nothing. It stays a valid stored value, and a row stored on it
 * opens on the stage that follows it. **Welcome** came back as the setup
 * conversation's Hello step (QUI-W02).
 */
export const RETIRED_STAGES: readonly SetupStage[] = ["permissions"];

/** The stages this installation shows, from its distribution (`installation.json`). */
export function stagesFor(distribution: string | null | undefined): readonly SetupStage[] {
  const skipped = distribution === "desktop" ? [...RETIRED_STAGES, ...INSTALLER_STAGES] : RETIRED_STAGES;
  return SETUP_STAGES.filter((stage) => !skipped.includes(stage));
}

/** The stage after `stage` on this rail; the last stage is its own next. */
export function nextStage(stages: readonly SetupStage[], stage: SetupStage): SetupStage {
  const index = stages.indexOf(stage);
  return stages[Math.min(index + 1, stages.length - 1)] ?? "finish";
}

/** The stage before `stage` on this rail; the first stage is its own previous. */
export function previousStage(stages: readonly SetupStage[], stage: SetupStage): SetupStage {
  const index = stages.indexOf(stage);
  return stages[Math.max(index - 1, 0)] ?? "welcome";
}

/**
 * Where a stored setup row lands on today's rail.
 *
 * `account` and `backup` are still valid stored values — an instance part-way
 * through the old wizard must not fail to render — so they resolve to the stage
 * that now carries their meaning rather than to a blank screen. A stage this
 * installation does not show (an installer-covered one) resolves to the stage
 * that follows it.
 */
export function visibleStage(stage: string | null | undefined, stages: readonly SetupStage[] = SETUP_STAGES): SetupStage {
  const shown: readonly string[] = stages;
  if (stage && shown.includes(stage) && stage !== "finish") return stage as SetupStage;
  if (stage === "backup" || stage === "finish") return "finish";
  if (stage && (SETUP_STAGES as readonly string[]).includes(stage)) {
    const full = SETUP_STAGES.indexOf(stage as SetupStage);
    return SETUP_STAGES.slice(full + 1).find((later) => stages.includes(later)) ?? "finish";
  }
  return stages[0] ?? "welcome"; // including the retired `account`
}

/**
 * Where model requests go, stated rather than asked (FIRST-07, BUG-345).
 *
 * Setup used to offer *Local only* beside this, and nothing enforced it: a turn
 * on a cloud model was sent exactly as under the other answer. The owner chose
 * to remove the choice, so the step now says what is true. Keeping requests on
 * this device is done by choosing a model that runs here.
 */
export const PRIVACY_STATEMENT = {
  mode: "balanced" as const,
  detail:
    "Requests go only to the model you choose and the providers you connect. Nothing reaches a provider you have not set up. To keep every request on this device, choose a model that runs here.",
};

/**
 * One sentence about permissions, instead of the matrix (FIRST-10).
 *
 * Sixty-six gates is a page an owner visits when they have a reason to. On
 * first run the useful fact is the posture, not the inventory.
 */
export const PERMISSIONS_NOTE =
  "Raiker starts conservatively and will ask you before it takes a governed action. You can review every permission later.";

/**
 * The four ways a permission can be decided (capabilityModel's decision
 * modes), in the owner's words. Shown on the Permissions stage as an
 * explanation, not a control: finishing setup never changes a mode, and
 * nothing here is a blanket authorisation for autonomous work.
 */
export const DECISION_MODE_COPY = [
  { mode: "ask", label: "Ask before acting", detail: "Raiker stops and asks you each time. The default for anything that changes something." },
  { mode: "allow", label: "Allow within a scope you approve", detail: "Raiker may act inside the folders, services or limits you set for that permission." },
  { mode: "auto", label: "Act automatically within policy", detail: "Raiker acts without asking, still inside every policy limit and audited." },
  { mode: "deny", label: "Never", detail: "Raiker cannot do it at all, and does not ask." },
] as const;

/** A check row's state, said in words as well as colour (never colour alone). */
export const CHECK_STATE_LABELS: Record<"pass" | "warn" | "fail" | "info", string> = {
  pass: "Ready",
  warn: "Works, with a limit",
  fail: "Needs attention",
  info: "Note",
};

export interface RecommendedPath {
  /** "" when nothing is detected or connected and the owner must choose. */
  profileId: string;
  provider: string;
  label: string;
  detail: string;
  /**
   * BUG-332 — what the recommendation asks for. ``choose`` is a model from a
   * provider that works; ``workspace`` is the one field an identity-linked key
   * still needs before its provider can list anything.
   */
  action: "choose" | "workspace";
}

/**
 * BUG-340 — what a runtime on this machine promises about where prompts go.
 *
 * A running Ollama can serve cloud models beside local ones, so "never leave
 * this device" is said only when the service described every model it serves
 * as running here. A runtime that described none earns no device claim at all.
 */
function runtimeDetail(profile: ModelProfile): string {
  const locations = Object.values(profile.model_locations ?? {});
  const remote = remoteDestinations(profile);
  if (remote.length > 0) {
    return (
      "It needs no account and no API key. Models it runs here stay on this device; " +
      `models marked Cloud send your prompts to ${remote.join(" and ")}.`
    );
  }
  if (locations.length > 0) {
    return "It needs no account and no API key, and its models never leave this device.";
  }
  return "It needs no account and no API key.";
}

/** True when a provider's last answer was that the key needs its workspace named. */
function needsWorkspace(profile: ModelProfile, refusals: Readonly<Record<string, string | null>>): boolean {
  const code = refusals[profile.profile_id] ?? profile.readiness_reason_code ?? "";
  return code.startsWith("provider_workspace");
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
export function recommendedPath(
  profiles: ModelProfile[],
  /**
   * BUG-332 — what each provider said when its models were last listed on this
   * screen (`null` when it listed them). A stored key is not a working
   * connection: an identity-linked Anthropic key is stored, and lists nothing
   * until its workspace is named.
   */
  refusals: Readonly<Record<string, string | null>> = {},
): RecommendedPath | null {
  // REM-MODEL-01 — the recommendation passes through the one reachability
  // answer, so a runtime this machine is running but whose last check found no
  // model, or a connected account whose key was rejected, is not offered as the
  // cheapest path to a working model.
  //
  // Detection is a PATH lookup: it proves the runtime is installed, not that it
  // serves anything. So the runtime must also name a model it has — a managed
  // llama.cpp slot does not until one is deployed into it.
  const detected = profiles.find(
    (profile) =>
      profile.local_only &&
      profile.provider_detected === true &&
      profile.configured === true &&
      isReachableProfile(profile),
  );
  if (detected) {
    return {
      profileId: detected.profile_id,
      provider: detected.provider,
      // A service Raiker asked over loopback is said to be running — the
      // stronger, measured fact — rather than merely installed.
      label: `${providerName(detected.provider)} is ${
        detected.provider_running === true ? "running" : "installed"
      } here`,
      detail: runtimeDetail(detected),
      action: "choose",
    };
  }
  const connected = profiles.find(
    (profile) =>
      profile.connection_configured === true &&
      isReachableProfile(profile) &&
      !needsWorkspace(profile, refusals) &&
      // A provider that refused its listing for any other reason is not the
      // easiest path either; its row says why.
      !refusals[profile.profile_id],
  );
  if (connected) {
    return {
      profileId: connected.profile_id,
      provider: connected.provider,
      label: `${providerName(connected.provider)} is connected`,
      detail: "Choose one of its models as your default, or connect another provider.",
      action: "choose",
    };
  }
  const waiting = profiles.find(
    (profile) => profile.connection_configured === true && needsWorkspace(profile, refusals),
  );
  if (waiting) {
    const name = providerName(waiting.provider);
    return {
      profileId: waiting.profile_id,
      provider: waiting.provider,
      label: `${name} needs its workspace ID`,
      detail:
        `This key is identity-linked, so it acts inside one ${name} workspace. Add that ` +
        "workspace ID — it is in the console beside the key — and its models are listed. " +
        "Or connect another provider.",
      action: "workspace",
    };
  }
  return null;
}
