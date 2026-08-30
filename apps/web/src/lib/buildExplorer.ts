/**
 * How wide Build's file explorer is, and whether it was left open (B13).
 *
 * Presentation only — nothing here grants, reaches or changes anything. It is
 * stored rather than derived because a file explorer whose width resets on every
 * navigation is one an owner stops resizing, and one that closes itself every
 * time is one they stop opening.
 *
 * The width is clamped on read as well as on write. A stored value is the one
 * input here that a person can edit by hand, and a panel that has taken the
 * whole window because localStorage said `99999` is not a preference anyone set.
 */
const WIDTH_KEY = "raiker.build.explorerWidth";
const OPEN_KEY = "raiker.build.explorerOpen";

/** Narrow enough to still show a tree; wide enough to read a file beside it. */
export const MIN_EXPLORER_WIDTH = 200;
export const MAX_EXPLORER_WIDTH = 640;
export const DEFAULT_EXPLORER_WIDTH = 280;

export function clampExplorerWidth(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_EXPLORER_WIDTH;
  return Math.min(MAX_EXPLORER_WIDTH, Math.max(MIN_EXPLORER_WIDTH, Math.round(value)));
}

export function readExplorerWidth(): number {
  try {
    const stored = window.localStorage.getItem(WIDTH_KEY);
    if (stored === null) return DEFAULT_EXPLORER_WIDTH;
    return clampExplorerWidth(Number.parseInt(stored, 10));
  } catch {
    return DEFAULT_EXPLORER_WIDTH;
  }
}

export function rememberExplorerWidth(width: number): void {
  try {
    window.localStorage.setItem(WIDTH_KEY, String(clampExplorerWidth(width)));
  } catch {
    // A blocked storage is a lost preference, never a blocked panel.
  }
}

export function readExplorerOpen(): boolean {
  try {
    return window.localStorage.getItem(OPEN_KEY) === "1";
  } catch {
    return false;
  }
}

export function rememberExplorerOpen(open: boolean): void {
  try {
    if (open) window.localStorage.setItem(OPEN_KEY, "1");
    else window.localStorage.removeItem(OPEN_KEY);
  } catch {
    // As above.
  }
}
