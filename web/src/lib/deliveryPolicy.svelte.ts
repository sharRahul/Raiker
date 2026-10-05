/**
 * Whether a notice may interrupt the owner, as the server decided it (DEC-21a).
 *
 * Quiet hours used to be impossible to implement honestly in the browser: the
 * dock kept an in-memory set of what it had shown, so a second tab, a reload or
 * a restart would replay the night's toasts at 07:01. The decision is now made
 * on the server when a notice is written and stored on its row
 * (`in_app_presentation`, `desktop_presentation`), and the live state — is it
 * quiet now, may a decision interrupt — is one read every surface shares.
 *
 * This module is that read, plus the rule for a stored decision. It decides
 * nothing itself: a failed read keeps the last answer, and with no answer at
 * all the shell behaves as it did before quiet hours existed (everything
 * interrupts), because a preference nobody could read must never hide a notice.
 */
import { api, hasToken } from "./api";
import type { NotificationDelivery } from "./generated/apiContract";

/** How often the policy is re-read. Quiet hours change on the minute at most. */
const POLL_MS = 30000;

export const delivery = $state<{ current: NotificationDelivery | null }>({ current: null });

/** Raised on `window` when the owner changed the policy on this page. */
export const DELIVERY_CHANGED = "raiker:delivery-changed";

/** True when a stored presentation lets a notice interrupt. `null` predates the policy. */
export function interrupts(presentation: string | null | undefined): boolean {
  return presentation == null || presentation === "interrupt" || presentation === "critical_exception";
}

/** May a decision (an approval) be put in front of the owner right now? */
export function decisionsInterrupt(): boolean {
  return delivery.current?.decisions_interrupt ?? true;
}

export async function refreshDelivery(): Promise<NotificationDelivery | null> {
  if (!hasToken()) return delivery.current;
  try {
    delivery.current = await api.notificationDelivery();
  } catch {
    // Keep the last answer; the next tick tries again.
  }
  return delivery.current;
}

let subscribers = 0;
let timer: ReturnType<typeof setInterval> | null = null;
const reread = () => void refreshDelivery();

/**
 * Keep the policy fresh while at least one surface is watching it. Returns the
 * unsubscribe, for an `$effect` to hand back.
 */
export function watchDelivery(): () => void {
  subscribers += 1;
  if (subscribers === 1) {
    void refreshDelivery();
    timer = setInterval(reread, POLL_MS);
    window.addEventListener(DELIVERY_CHANGED, reread);
  }
  return () => {
    subscribers -= 1;
    if (subscribers === 0) {
      if (timer !== null) clearInterval(timer);
      timer = null;
      window.removeEventListener(DELIVERY_CHANGED, reread);
    }
  };
}

/** Tell every surface on this page that the owner changed the policy. */
export function announceDeliveryChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(DELIVERY_CHANGED));
}

/** `"22:00"` and an IANA zone → a short sentence fragment, e.g. `22:00 (Europe/London)`. */
export function clockIn(time: string, zone: string): string {
  return `${time} (${zone})`;
}

/** A UTC instant shown on the owner's clock in the quiet-hours zone, e.g. `07:00`. */
export function localClock(instant: string | null | undefined, zone: string): string | null {
  if (!instant) return null;
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone: zone,
    }).format(Date.parse(instant));
  } catch {
    return null;
  }
}
