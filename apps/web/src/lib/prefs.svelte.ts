// UI preferences applied from the per-account settings blob. These are
// presentation choices only — nothing here grants or changes authority.
import { NAV_ITEMS } from "./nav";

// Notification preferences read by NotificationCenter. Defaults match the
// settings defaults: in-app popups on, desktop alerts off.
export const uiPrefs = $state({ inApp: true, desktop: false });

/** Apply spacing/font to the shell and refresh notification preferences. */
export function applyUiPrefs(settings: Record<string, unknown>): void {
  const root = document.documentElement;
  const spacing = settings["personalisation.spacing"];
  if (spacing === "compact" || spacing === "spacious") root.dataset.spacing = String(spacing);
  else delete root.dataset.spacing;
  const font = settings["personalisation.font"];
  if (font === "mono" || font === "system") root.dataset.font = String(font);
  else delete root.dataset.font;
  uiPrefs.inApp = settings["notification.in_app"] !== false;
  uiPrefs.desktop = Boolean(settings["notification.desktop"]);
}

/** The saved startup route, if it names a real route. */
export function startupRoute(settings: Record<string, unknown>): string | null {
  const route = settings["general.startup_route"];
  return typeof route === "string" && NAV_ITEMS.some((item) => item.id === route) ? route : null;
}
