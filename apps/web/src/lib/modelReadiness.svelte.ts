import { api } from "./api";
import type { ModelProfile, ModelReadinessView } from "./apiTypes";
import { refreshModels } from "./models.svelte";

export const setupDialog = $state<{
  open: boolean;
  profile: ModelProfile | null;
  readiness: ModelReadinessView | null;
  returnFocus: HTMLElement | null;
}>({ open: false, profile: null, readiness: null, returnFocus: null });

export function readinessForProfile(profile: ModelProfile): ModelReadinessView {
  return {
    owner_principal_id: "",
    profile_id: profile.profile_id,
    model: profile.model,
    endpoint_fingerprint: "",
    state: profile.readiness_state ?? "not_configured",
    checked_at: profile.readiness_checked_at ?? null,
    expires_at: profile.readiness_expires_at ?? null,
    summary: profile.readiness_summary ?? "This model has not passed a reachability check.",
    reason_code: profile.readiness_reason_code ?? "model_not_checked",
    remediation: profile.readiness_remediation ?? "Set up or check this model before sending.",
    evidence: { provider: profile.provider },
    ready: profile.ready === true,
  };
}

export function readinessForSelection(profile: ModelProfile | null): ModelReadinessView {
  if (profile) return readinessForProfile(profile);
  return {
    owner_principal_id: "", profile_id: "", model: "", endpoint_fingerprint: "",
    state: "not_configured", checked_at: null, expires_at: null,
    summary: "No model is set up.", reason_code: "model_not_configured",
    remediation: "Open Models to connect a provider or set up a local model.",
    evidence: {}, ready: false,
  };
}

export function openModelSetup(
  profile: ModelProfile | null,
  readiness: ModelReadinessView | null = null,
): void {
  setupDialog.returnFocus = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null;
  setupDialog.profile = profile;
  setupDialog.readiness = readiness ?? (profile ? readinessForProfile(profile) : null);
  setupDialog.open = true;
}

export function closeModelSetup(): void {
  const returnFocus = setupDialog.returnFocus;
  setupDialog.open = false;
  setupDialog.profile = null;
  setupDialog.readiness = null;
  setupDialog.returnFocus = null;
  queueMicrotask(() => returnFocus?.focus());
}

export function resetModelSetup(): void {
  setupDialog.open = false;
  setupDialog.profile = null;
  setupDialog.readiness = null;
  setupDialog.returnFocus = null;
}

export async function refreshModelReadiness(
  profile: ModelProfile | null = setupDialog.profile,
): Promise<ModelReadinessView | null> {
  const current = setupDialog.readiness;
  const profileId = profile?.profile_id ?? current?.profile_id;
  const model = profile?.model ?? current?.model;
  if (!profileId || !model) return null;
  const readiness = await api.checkModelReadiness(profileId, model);
  setupDialog.readiness = readiness;
  await refreshModels();
  return readiness;
}
