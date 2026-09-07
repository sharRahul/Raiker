/**
 * The one way Raiker reaches the owner when its window is not the one they are
 * looking at (BUG-255).
 *
 * The approval prompt puts a pending decision in front of the owner wherever
 * they are *in Raiker*. The case it could not cover is the one it exists for: a
 * background task or a standing agent raises a decision while the owner is in
 * another window, and the work parks unnoticed.
 *
 * Deliberately the smallest thing that closes it. No email, no third-party
 * push, no new egress — the browser's own notification, which the owner has
 * already had to permit, and which never leaves the machine. Three rules hold
 * everywhere it is used:
 *
 * * **The preference decides.** `notification.desktop` is off by default and is
 *   the owner's switch; permission being granted is not consent on its own.
 * * **Only when Raiker is not visible.** A notice about something already on
 *   screen is noise, so a visible tab raises nothing.
 * * **The in-app record is the truth.** Every notice mirrors something that
 *   already exists in Raiker; if this fails for any reason, nothing is lost.
 */
import { uiPrefs } from "./prefs.svelte";

/** True when a notice would actually be shown, so callers can skip the work. */
export function canRaiseDesktopNotice(): boolean {
  return (
    uiPrefs.desktop &&
    typeof Notification !== "undefined" &&
    Notification.permission === "granted"
  );
}

/** True when Raiker is not the window the owner is looking at. */
export function raikerIsHidden(): boolean {
  return typeof document !== "undefined" && document.hidden;
}

export interface DesktopNotice {
  title: string;
  body: string;
  /**
   * Collapses repeats of the same subject into one notice rather than stacking
   * a new banner every poll. Use a stable id, not a timestamp.
   */
  tag: string;
  /** Where clicking the notice should take the owner, as a route hash. */
  route?: string;
}

/** Raise one notice. Returns whether it was actually shown. */
export function raiseDesktopNotice(notice: DesktopNotice): boolean {
  if (!canRaiseDesktopNotice()) return false;
  try {
    const shown = new Notification(notice.title, { body: notice.body, tag: notice.tag });
    shown.onclick = () => {
      // Bring Raiker forward and land on the surface that can answer. `focus`
      // is a request, not a guarantee — a platform that refuses it still leaves
      // the owner with the route set for when they do switch back.
      if (notice.route !== undefined) window.location.hash = notice.route;
      window.focus();
      shown.close();
    };
    return true;
  } catch {
    // Constructor unavailable (headless, or a platform that only supports
    // notifications through a service worker). In-app only, which is where the
    // record lives anyway.
    return false;
  }
}
