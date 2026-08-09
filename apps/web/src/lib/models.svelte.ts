// The single source of truth for model profiles across the workspace shell.
//
// Chat, Build, and Workbench previously each kept their own snapshot of
// /api/models fetched once in onMount, so connecting a provider on the Models
// page never reached either composer until a full page reload. This module
// holds one reactive snapshot: the Models view writes to it after every change
// (`setModels`), and the composers read the exported accessors so a newly
// connected provider — and its available models — appear in every picker the
// moment that fetch returns, including in the persistently-mounted Chat and
// Build surfaces that stay alive across route visits.
import { api } from "./api";
import type { ModelProfile, ModelsView } from "./apiTypes";

const store = $state<{ data: ModelsView | null }>({ data: null });

// Chat and Build composers are limited to concrete, configured profiles. Newer
// servers expose `chat_profiles` (already filtered); older ones fall back to the
// configured subset of the full profile list. Svelte does not allow exporting
// `$derived` from a module, so these are functions; callers wrap them in a local
// `$derived` (one line) to stay reactive.
export function chatProfiles(): ModelProfile[] {
  return (
    store.data?.chat_profiles ??
    (store.data ? store.data.profiles.filter((profile) => profile.configured) : [])
  );
}

// Workbench's model summary covers every profile, configured or not.
export function allProfiles(): ModelProfile[] {
  return store.data ? store.data.profiles : [];
}

/** Exact profiles currently proven reachable; unknown is deliberately not ready. */
export function readyProfiles(): ModelProfile[] {
  return chatProfiles().filter((profile) => profile.ready === true);
}

export function selectedModelReadiness(): ModelProfile | null {
  return allProfiles().find((profile) => profile.selected) ?? null;
}

/** Fetch /api/models and update the shared store. Safe to call from onMount. */
export async function refreshModels(): Promise<void> {
  try {
    store.data = await api.models();
  } catch {
    // A transient read failure leaves the previous snapshot in place so the
    // picker the user is looking at does not blank out mid-action.
  }
}

/** Share the result of the Models view's own fetch without a second read. */
export function setModels(data: ModelsView): void {
  store.data = data;
}

/** Clear the shared snapshot. Intended for test isolation between cases. */
export function resetModels(): void {
  store.data = null;
}
