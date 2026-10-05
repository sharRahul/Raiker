/**
 * What happened to a notice, in words, for the record (DEC-21a, DEC-21).
 *
 * The server decides when a notice is written whether it may interrupt, and
 * keeps that apart from whether it has been read. The record is where an owner
 * asks "why did I never see this?", so it answers: held for quiet hours (and
 * until when), not shown because its kind is turned off, let through as a
 * security exception — and how many more times the same notice was raised.
 * A notice written before any of this existed says nothing extra.
 */
import type { Notification as RaikerNotification } from "./apiTypes";

/** One short phrase, or `null` when the notice was simply shown. */
export function presentationPhrase(notification: RaikerNotification, localClock?: (instant: string) => string | null): string | null {
  const inApp = notification.in_app_presentation;
  if (inApp === "quiet_hours") {
    if (notification.summarised_at) return "held for quiet hours, then summarised";
    const until = notification.quiet_until && localClock ? localClock(notification.quiet_until) : null;
    return until ? `held for quiet hours until ${until}` : "held for quiet hours";
  }
  if (inApp === "muted") return "not shown — this kind is turned off in Notifications";
  if (inApp === "critical_exception") return "shown during quiet hours as a security exception";
  return null;
}

/** "raised 3 more times", or `null`. */
export function repeatPhrase(notification: RaikerNotification): string | null {
  const repeats = notification.repeat_count ?? 0;
  if (repeats <= 0) return null;
  return `raised ${repeats} more time${repeats === 1 ? "" : "s"}`;
}
