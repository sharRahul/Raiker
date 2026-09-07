import { api, hasToken } from "./api";
import type { ModelProfile, ModelReadinessView } from "./apiTypes";
import { refreshModels, setModels } from "./models.svelte";

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
    // The composer needs to know whether the owner has connected this provider,
    // because that is exactly what decides whether the server will take the
    // first readiness check itself. `evidence` is the view's free-form half and
    // is where a fact like this belongs rather than in a new contract field.
    evidence: {
      provider: profile.provider,
      connection_configured: profile.connection_configured === true || !profile.off_machine,
    },
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

/**
 * BUG-238 — a stale observation is not an unset-up model.
 *
 * A readiness observation expires so that no turn runs on a claim older than
 * the owner's window. It was also deciding whether the model was *configured*:
 * once the window passed, the composer disabled **Send** and offered
 * **Set up model** — for a model the owner had already set up, after every
 * restart and after any five idle minutes.
 *
 * The server now re-takes a stale observation before admitting the turn
 * (`require_ready_async`), so the browser has nothing to block on: `stale`
 * means "Raiker is confirming this", not "you have work to do". Every other
 * not-ready state is a real answer about the model and still blocks, because
 * those are the ones the owner can actually fix.
 */
export function isRevalidating(readiness: ModelReadinessView | null): boolean {
  return readiness !== null && !readiness.ready && readiness.state === "stale";
}

/**
 * Whether this model may be offered as a choice.
 *
 * Every picker in the app answers the same question — "can the owner pick
 * this?" — so they answer it here rather than each inventing a rule. A model
 * with a failing check is not a choice: offering it only produces a selection
 * the next turn refuses. A model whose observation has merely aged out *is* a
 * choice, for the same reason `isRevalidating` does not block sending: nothing
 * is known to be wrong, and the server re-takes the observation before the turn
 * runs. A model nobody has checked yet is not known to be broken either.
 */
const MEASURED_UNAVAILABLE = new Set([
  "runtime_missing",
  "runtime_stopped",
  "model_missing",
  "policy_blocked",
  "authentication_failed",
  "quota_exhausted",
  "unreachable",
  "unsupported",
]);

export function isChoosableModel(profile: {
  readiness_state?: string | null;
  connection_configured?: boolean;
  off_machine?: boolean;
}): boolean {
  // `ready === false` is not the test: it is also false for a model nobody has
  // checked, and excluding those emptied every picker on a fresh instance. What
  // disqualifies a model is a check that *answered badly*.
  if (profile.readiness_state && MEASURED_UNAVAILABLE.has(profile.readiness_state)) return false;
  // A provider the owner holds an account with is only reachable once they have
  // connected it. Listing "Anthropic — Sonnet 5" on an instance with no
  // Anthropic credential offered a model that cannot answer, which is the same
  // mistake as listing a llama.cpp slot with nothing served.
  return profile.connection_configured === true || profile.off_machine !== true;
}

/**
 * True when the owner has something to fix before a turn can run.
 *
 * A model nobody has checked yet is not one of those things. The server takes
 * that check itself before it admits the turn, exactly as it does for an
 * observation that aged out, so blocking here asked the owner to press **Test**
 * on a provider they had just connected and a model they had just selected.
 * "No model at all" still blocks: that readiness names no model, and there is
 * nothing to look at.
 */
export function blocksSending(readiness: ModelReadinessView | null): boolean {
  if (readiness === null) return false;
  if (readiness.ready) return false;
  if (isRevalidating(readiness)) return false;
  // Only a provider the owner has connected gets its first check taken for
  // them, so only that case may skip the block. Everything else still asks.
  const unmeasured =
    readiness.state === "not_configured" &&
    readiness.model !== "" &&
    !readiness.model.includes("<") &&
    readiness.evidence?.connection_configured === true;
  return !unmeasured;
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
  // Nothing to revalidate before the owner has a session, and asking anyway
  // costs a 401 on the lock screen — which is a console error on every load.
  if (!hasToken()) return;
  if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
  revalidationInFlight = true;
  try {
    const view = await api.models();
    // BUG-238 — publish what this read already learned, even when no check is
    // due. The server re-checks a stale model when it admits a turn, so the
    // stored observation can become `ready` without the browser asking; without
    // this the tick returned early and the composer kept saying "Re-checking
    // this model" long after the turn it was re-checked by had finished.
    setModels(view);
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
  // BUG-238 — run once immediately. A restart is exactly the moment an
  // observation is most likely to have aged out, and waiting a full tick before
  // the first check is what made "set up your model" the first thing an owner
  // saw after reopening Raiker.
  void revalidateSelectedModel();
  revalidationTimer = setInterval(() => void revalidateSelectedModel(), REVALIDATION_TICK_MS);
  return stopReadinessRevalidation;
}

export function stopReadinessRevalidation(): void {
  if (revalidationTimer !== undefined) {
    clearInterval(revalidationTimer);
    revalidationTimer = undefined;
  }
}
