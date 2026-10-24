// UI preferences applied from the per-account settings blob. These are
// presentation choices only — nothing here grants or changes authority.
import { setDisplayLocale } from "./format";
import { NAV_ITEMS } from "./nav";
import { desktopBridge } from "./desktopShell";

// Notification preferences read by NotificationCenter. Defaults match the
// settings defaults: in-app popups on, desktop alerts off.
export const uiPrefs = $state({ inApp: true, desktop: false, responses: true });

/**
 * Apply density and typeface to the shell — nothing else.
 *
 * DEC-21 Personalisation — Settings calls this with its *draft* so a choice is
 * seen before it is saved, and again with the confirmed values when the draft
 * is discarded or left. A value this build does not know falls back to the
 * default rather than being applied. Notification and date preferences are not
 * here: those must not take effect until they are saved.
 */
export function applyAppearance(settings: Record<string, unknown>): void {
  const root = document.documentElement;
  const spacing = settings["personalisation.spacing"];
  if (spacing === "compact" || spacing === "spacious") root.dataset.spacing = String(spacing);
  else delete root.dataset.spacing;
  const font = settings["personalisation.font"];
  if (font === "mono" || font === "system") root.dataset.font = String(font);
  else delete root.dataset.font;
  // QUI-F12 — conversation text has its own size, 110% unless chosen.
  root.style.setProperty("--chat-text-scale", String(chatTextScale(settings)));
}

/** QUI-F12 — the chat text size as a multiplier; 1.1 when nothing valid is stored. */
export const CHAT_TEXT_SIZES = ["100", "110", "125", "140"] as const;
export function chatTextScale(settings: Record<string, unknown>): number {
  const stored = settings["personalisation.chat_text_size"];
  const size = (CHAT_TEXT_SIZES as readonly unknown[]).includes(stored) ? Number(stored) : 110;
  return size / 100;
}

/** Apply spacing/font and the date format to the shell, and refresh notification preferences. */
export function applyUiPrefs(settings: Record<string, unknown>): void {
  applyAppearance(settings);
  // DEC-21 General — every date and time in the interface follows this.
  setDisplayLocale(settings["general.language"]);
  uiPrefs.inApp = settings["notification.in_app"] !== false;
  uiPrefs.desktop = Boolean(settings["notification.desktop"]);
  // QUI-F05 — *Response ready*: on unless the owner turned it off.
  uiPrefs.responses = settings["notification.interrupt.responses"] !== false;
  // QUI-F11 — the desktop window keeps the account's tray choice.
  desktopBridge()?.setMinimizeToTray?.(settings["desktop.minimize_to_tray"] === true);
}

/** The saved startup route, if it names a real route. */
export function startupRoute(settings: Record<string, unknown>): string | null {
  const route = settings["general.startup_route"];
  return typeof route === "string" && NAV_ITEMS.some((item) => item.id === route) ? route : null;
}
