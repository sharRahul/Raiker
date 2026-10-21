/**
 * QUI-H04 — one dismissible line on Home after Raiker is updated.
 *
 * The version this browser last acknowledged is kept in local storage: it is a
 * per-viewer convenience, not a record. The first version a browser ever sees
 * is stored silently, so a fresh install never opens with "Updated". A changed
 * version shows the line until it is dismissed or followed. Never a modal.
 */
export const SEEN_VERSION_KEY = "raiker.whats-new.seen-version";

function readSeen(): string | null {
  try {
    return localStorage.getItem(SEEN_VERSION_KEY);
  } catch {
    return null;
  }
}

/** Record `version` as seen. Storage that refuses the write leaves the line up. */
export function markVersionSeen(version: string): void {
  try {
    localStorage.setItem(SEEN_VERSION_KEY, version);
  } catch {
    // A private window or blocked storage: the line simply stays offered.
  }
}

/**
 * The version to announce, or `null`.
 *
 * Remembers a first sighting rather than announcing it, and ignores an empty or
 * unknown version so a failed read never shows "Updated to ".
 */
export function versionToAnnounce(current: string | null | undefined): string | null {
  const version = (current ?? "").trim();
  if (version === "" || version === "unknown") return null;
  const seen = readSeen();
  if (seen === null) {
    markVersionSeen(version);
    return null;
  }
  return seen === version ? null : version;
}
