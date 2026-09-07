/**
 * WEB-01 / WEB-07 — one snapshot of the global read catalogue, shared by every
 * mounted composer.
 *
 * The catalogue and its readiness are owner-level facts, so a page must not
 * hold a private copy of them. That is not a tidiness argument: Chat and Build
 * stay mounted across route visits, so an owner who configures a search provider
 * on Settings and returns to a still-mounted Chat would, with per-view state,
 * see `Needs provider` on a capability that is now ready — until they reloaded
 * the whole app. The plan calls that out by name: *when provider configuration
 * or readiness changes, all mounted agentic surfaces update without reload or
 * page-specific state.*
 *
 * So one module holds the snapshot, the surfaces read it, and whoever changes
 * the underlying configuration calls {@link refreshReadCapabilities} — the same
 * shape `models.svelte.ts` uses next door, for the same reason.
 *
 * Nothing here grants anything. A readiness row says a request *would reach
 * something*; the capability gate, the decision mode, the policy engine and the
 * egress guard still judge the call when it is made.
 */
import { api } from "./api";
import type { ReadCapabilities, ToolReadiness } from "./apiTypes";

const store = $state<{ data: ReadCapabilities | null }>({ data: null });

/**
 * Typed readiness for the external read capabilities, or an empty list.
 *
 * Empty rather than invented: a host that has not answered yet, or one older
 * than this build, says nothing about whether search has a provider, and a
 * composer that guessed would print a state it does not know. Svelte cannot
 * export `$derived` from a module, so callers wrap this in a one-line
 * `$derived` to stay reactive.
 */
export function readReadiness(): ToolReadiness[] {
  return store.data?.readiness ?? [];
}

/** The whole global read catalogue, or an empty list before the first read. */
export function readCatalogue(): string[] {
  return store.data?.capabilities ?? [];
}

/** What one agentic surface may see, by the backend's own parity contract. */
export function readCapabilitiesFor(surface: string): string[] {
  return store.data?.surfaces?.[surface] ?? [];
}

/** Fetch the catalogue and update the shared snapshot. Safe from `onMount`. */
export async function refreshReadCapabilities(): Promise<void> {
  try {
    store.data = await api.readCapabilities();
  } catch {
    // A transient read failure leaves the previous snapshot in place. A composer
    // blanking its Tools menu because one poll failed would be a worse answer
    // than a slightly old one, and the runtime judges every call regardless.
  }
}

/** Share a snapshot another view already fetched, without a second read. */
export function setReadCapabilities(data: ReadCapabilities): void {
  store.data = data;
}

/** Clear the snapshot. For test isolation between cases. */
export function resetReadCapabilities(): void {
  store.data = null;
}
