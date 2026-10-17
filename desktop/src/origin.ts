// SPDX-License-Identifier: Apache-2.0
/**
 * Where the desktop window may go, decided in one place.
 *
 * The window shows one thing: the Raiker host this shell started or joined, on
 * a loopback address. Everything else a page could reach for — another site, a
 * local file, a `javascript:` URL, a second Raiker instance on another port —
 * is classified here, so the main process, the window-open handler and the
 * tests all read the same rule rather than three that can disagree.
 */

/** Hostnames that can only ever mean this machine. */
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);

/**
 * The origin of a loopback Raiker URL, or `null` for anything else.
 *
 * Only plain `http` on a loopback host qualifies. Raiker never serves the
 * desktop window over the network, and a shell that accepted a LAN address
 * would be a browser pointed wherever its argument said.
 */
export function loopbackOrigin(raw: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }
  if (parsed.protocol !== "http:") return null;
  if (!LOOPBACK_HOSTS.has(parsed.hostname)) return null;
  if (parsed.username !== "" || parsed.password !== "") return null;
  return parsed.origin;
}

/** What to do with a navigation or `window.open` from the Raiker page. */
export type NavigationDecision =
  /** The Raiker host this window shows: let it happen in place. */
  | "same-window"
  /** Another Raiker instance on this machine: a new desktop window. */
  | "app-window"
  /** A web page or mail link: the owner's own browser or mail client. */
  | "external"
  /** Anything else — files, scripts, data URLs, custom schemes. */
  | "deny";

const EXTERNAL_PROTOCOLS = new Set(["https:", "http:", "mailto:"]);

export function classifyNavigation(target: string, appOrigin: string): NavigationDecision {
  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return "deny";
  }
  const origin = loopbackOrigin(target);
  if (origin !== null) return origin === appOrigin ? "same-window" : "app-window";
  if (!EXTERNAL_PROTOCOLS.has(parsed.protocol)) return "deny";
  if (parsed.protocol === "mailto:") return "external";
  // A non-loopback http(s) address is a web page; credentials in it are a
  // phishing shape, not something to hand to the system browser.
  if (parsed.username !== "" || parsed.password !== "") return "deny";
  return "external";
}

/**
 * The permissions a Raiker page may be granted, and only from its own origin.
 *
 * Notifications back the owner's opt-in desktop notices; clipboard writes back
 * every Copy button; audio-only media backs voice input. Camera, screen
 * capture, geolocation, MIDI, HID, serial and the rest are refused because no
 * Raiker surface uses them.
 */
export function decidePermission(
  permission: string,
  requestingUrl: string,
  appOrigin: string,
  mediaTypes: readonly string[] = [],
): boolean {
  if (loopbackOrigin(requestingUrl) !== appOrigin) return false;
  if (permission === "notifications" || permission === "clipboard-sanitized-write") return true;
  if (permission === "media") return mediaTypes.length > 0 && mediaTypes.every((type) => type === "audio");
  return false;
}
