/**
 * BUG-242 — carry the open conversation in the URL so a reload comes back to it.
 *
 * Chat and Build both learn their session id from the stream, not from the
 * link that opened them, so until the URL is told, a reload mounted a fresh
 * conversation over a session that was still stored and still findable. The
 * turn was never lost; the owner's place in it was.
 *
 * This writes with `history.replaceState` rather than by assigning to
 * `location.hash`: assigning fires `hashchange`, which the shell reads as a
 * navigation and would reload the transcript that is already on screen. It
 * also deliberately does nothing unless the surface asking is the one the URL
 * currently names — Chat and Build stay mounted behind each other, and a hidden
 * view must not rewrite the visible view's address.
 *
 * Only the session id travels. Everything else about a conversation stays
 * behind the governed API, exactly as `routeState.ts` requires.
 */
import { routeFromHash } from "./nav";

/** The same hash with `session=` set, or removed when there is no session. */
export function hashWithSession(hash: string, sessionId: string | null): string {
  const withoutHash = hash.startsWith("#") ? hash.slice(1) : hash;
  const [path, query = ""] = withoutHash.split("?", 2);
  const params = new URLSearchParams(query);
  if (sessionId === null || sessionId === "") params.delete("session");
  else params.set("session", sessionId);
  const rest = params.toString();
  return rest === "" ? `#${path}` : `#${path}?${rest}`;
}

/**
 * Record `sessionId` in the address bar for `route`, or clear it when null.
 *
 * A no-op when the browser is somewhere else, so a background surface never
 * rewrites the foreground one's URL.
 */
export function rememberSessionInRoute(route: string, sessionId: string | null): void {
  if (typeof window === "undefined") return;
  const hash = window.location.hash;
  if (routeFromHash(hash) !== route) return;
  const next = hashWithSession(hash, sessionId);
  if (next === hash) return;
  const { pathname, search } = window.location;
  window.history.replaceState(window.history.state, "", `${pathname}${search}${next}`);
}
