/**
 * One vocabulary for "can this model answer", shared by every surface that says so.
 *
 * It lived inside `ModelsView` while the first-run wizard invented its own
 * answer from a different field — `configured`, which means "this profile names
 * a concrete model string" and was rendered as `Connected`. On a host with no
 * llama.cpp binary and no Ollama process that made the first screen an owner
 * ever sees call five unreachable backends connected, while the providers that
 * work as soon as a key is entered read `Connection required` (BUG-198).
 *
 * The rule these labels keep: **a surface names what was measured.** `Ready` is
 * the only label that claims a backend can answer, and only a readiness check
 * produces it. Every other state names itself, and a profile nothing is known
 * about says so rather than borrowing a neighbouring fact.
 */
import type { ModelProfile, ModelReadinessState } from "./apiTypes";

/** The placeholder a registry profile carries when no model has been chosen. */
export const UNPINNED_MODEL = "<model>";

const READINESS_LABEL: Record<ModelReadinessState, string> = {
  ready: "Ready",
  checking: "Checking…",
  not_configured: "Not checked",
  stale: "Check expired",
  runtime_missing: "Runtime missing",
  runtime_stopped: "Runtime stopped",
  model_missing: "Model missing",
  policy_blocked: "Policy blocked",
  authentication_failed: "Key rejected",
  quota_exhausted: "No credit",
  unreachable: "Unreachable",
  unsupported: "Unsupported",
};

/** The label for a readiness state, or null when the backend sent none. */
export function readinessLabel(state: ModelReadinessState | undefined): string | null {
  if (!state) return null;
  return READINESS_LABEL[state] ?? null;
}

/**
 * What a setup choice may claim about a backend before anything has been checked.
 *
 * Deliberately never returns "Connected": nothing on this screen has contacted a
 * provider or found a runtime. A profile still carrying the `<model>` placeholder
 * needs a model chosen before it can be checked at all, which is a different
 * thing from one that names a model nobody has verified.
 */
export function setupChoiceLabel(profile: ModelProfile): string {
  const measured = readinessLabel(profile.readiness_state);
  if (profile.ready === true) return measured ?? "Ready";
  if (measured && profile.readiness_state !== "not_configured") return measured;
  if (!profile.model || profile.model === UNPINNED_MODEL) return "Choose a model first";
  return "Not checked yet";
}
