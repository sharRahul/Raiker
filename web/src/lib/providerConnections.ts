/**
 * BUG-319 — one owner of a provider connection's lifecycle.
 *
 * The Models page and first-run setup each implemented storing a credential,
 * adding a workspace to it, removing it and reading what the provider serves,
 * and each read the provider's refusal its own way. A code either surface
 * learned to explain had to be taught to the other by hand. Both now call
 * these operations, which hold the request and its interpretation; the pages
 * keep only what is theirs to draw (a dialog, a row, a note).
 *
 * Nothing here holds a credential after the call: the key goes to the server
 * and the outcome says only whether it was accepted and why not.
 */
import { api, ApiError } from "./api";
import type { ProviderModelList } from "./apiTypes";
import { providerErrorGuidance, type ProviderErrorGuidance } from "./providerErrors";

export interface ConnectionRefusal {
  ok: false;
  /** The governed reason, when the server gave one. */
  reasonCode: string | null;
  status: number | null;
  /** The shared, plain-language explanation for `reasonCode`, when there is one. */
  guidance: ProviderErrorGuidance | null;
  /** BUG-274 — the key is fine and the provider wants its workspace named. */
  workspaceRefused: boolean;
}

export type ConnectionOutcome = { ok: true } | ConnectionRefusal;

export type CatalogueOutcome = { ok: true; list: ProviderModelList } | ConnectionRefusal;

/** Whether a governed reason code is the provider asking for a workspace. */
export function refusedForWorkspace(reasonCode: string | null | undefined): boolean {
  return (reasonCode ?? "").startsWith("provider_workspace");
}

/** What a failed call said, in the one vocabulary both surfaces use. */
export function connectionRefusal(error: unknown): ConnectionRefusal {
  const reasonCode = error instanceof ApiError ? (error.reasonCode ?? null) : null;
  return {
    ok: false,
    reasonCode,
    status: error instanceof ApiError ? error.status : null,
    guidance: providerErrorGuidance(reasonCode),
    workspaceRefused: refusedForWorkspace(reasonCode),
  };
}

export interface ConnectionFields {
  endpoint?: string;
  apiKey?: string;
  adminApiKey?: string;
  workspaceId?: string;
  /** The owner's name for a custom endpoint. Display text only. */
  label?: string;
}

/** Store (or replace) a provider's credential and endpoint. */
export async function saveConnection(
  profileId: string,
  fields: ConnectionFields,
): Promise<ConnectionOutcome> {
  try {
    await api.saveModelConnection(
      profileId,
      (fields.endpoint ?? "").trim(),
      (fields.apiKey ?? "").trim(),
      (fields.adminApiKey ?? "").trim(),
      (fields.workspaceId ?? "").trim(),
      (fields.label ?? "").trim(),
    );
    return { ok: true };
  } catch (error) {
    return connectionRefusal(error);
  }
}

/**
 * Add a workspace to a stored connection without re-pasting the key.
 *
 * A workspace on its own merges into the saved connection server-side, which
 * is the one shape that does: anything else replaces.
 */
export async function saveWorkspace(profileId: string, workspaceId: string): Promise<ConnectionOutcome> {
  return saveConnection(profileId, { workspaceId });
}

/** Remove the stored credential and endpoint; nothing at the provider changes. */
export async function removeConnection(profileId: string): Promise<ConnectionOutcome> {
  return saveConnection(profileId, {});
}

/**
 * Ask the provider what it serves.
 *
 * A refusal can arrive as a 200 whose body says `unavailable` — the provider
 * answered, and what it said was no — so the list is returned as it came and
 * the caller reads `status` and `reason_code`; only a request that failed is a
 * refusal here.
 */
export async function listCatalogue(profileId: string): Promise<CatalogueOutcome> {
  try {
    return { ok: true, list: await api.providerModels(profileId) };
  } catch (error) {
    return connectionRefusal(error);
  }
}
