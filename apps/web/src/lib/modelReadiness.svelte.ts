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

/**
 * Opportunistic background revalidation of the selected model (BUG-83).
 *
 * A readiness observation expires, and until this existed nothing re-checked
 * it: a model that was ready five minutes ago became `stale` and the owner had
 * to press a button before working again. That is the wrong trade in both
 * directions during a long editing session.
 *
 * So while a work surface is open — and only while the tab is actually visible,
 * because a background tab is not a session — Raiker re-confirms the selected
 * model as its observation approaches expiry. This never *grants* readiness: it
 * runs the same owner-triggered check the Models page runs, and the server's
 * invalidation hooks (connection, selection, pull, endpoint, credential change)
 * stay authoritative over any timer.
 */
const REVALIDATION_TICK_MS = 30_000;
// Re-confirm once an observation is inside the last quarter of its own window,
// so the check lands before the expiry rather than after it.
const REFRESH_WITHIN_FRACTION = 0.25;

let revalidationTimer: ReturnType<typeof setInterval> | undefined;
let revalidationInFlight = false;

function dueForRevalidation(profile: ModelProfile, now: number): boolean {
  if (profile.readiness_state === "stale") return true;
  if (profile.readiness_state !== "ready") return false;
  const checkedAt = profile.readiness_checked_at;
  const expiresAt = profile.readiness_expires_at;
  if (!checkedAt || !expiresAt) return false;
  const checked = Date.parse(checkedAt);
  const expires = Date.parse(expiresAt);
  if (Number.isNaN(checked) || Number.isNaN(expires) || expires <= checked) return false;
  return now >= expires - (expires - checked) * REFRESH_WITHIN_FRACTION;
}

export async function revalidateSelectedModel(): Promise<void> {
  if (revalidationInFlight) return;
  if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
  revalidationInFlight = true;
  try {
    const view = await api.models();
    const selected =
      view.profiles.find((profile) => profile.selected) ??
      view.profiles.find((profile) => profile.profile_id === view.current_profile_id) ??
      null;
    if (selected === null || !selected.model) return;
    if (!dueForRevalidation(selected, Date.now())) return;
    await api.checkModelReadiness(selected.profile_id, selected.model);
    await refreshModels();
  } catch {
    // A failed background check changes nothing: the stored observation and its
    // expiry remain exactly what the last real check found.
  } finally {
    revalidationInFlight = false;
  }
}

/** Start background revalidation; returns the stop function. */
export function startReadinessRevalidation(): () => void {
  if (revalidationTimer !== undefined) return stopReadinessRevalidation;
  revalidationTimer = setInterval(() => void revalidateSelectedModel(), REVALIDATION_TICK_MS);
  return stopReadinessRevalidation;
}

export function stopReadinessRevalidation(): void {
  if (revalidationTimer !== undefined) {
    clearInterval(revalidationTimer);
    revalidationTimer = undefined;
  }
}
