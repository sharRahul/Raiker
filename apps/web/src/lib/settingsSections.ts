import type { IconName } from "./icons";

export interface SettingsSection {
  id: string;
  label: string;
  icon: IconName;
  group: "Personal" | "System";
}

/**
 * The settings rail, in rail order — the one list, so nothing can drift from it.
 *
 * Only sections the runtime actually backs. Trusted-contact recovery,
 * data-export tooling, and cloud/cache controls have no backend consumer, so
 * they are not presented as settings at all. Voice joined the list when it
 * gained one: a speech runtime on this machine (BUG-256).
 *
 * It lives here rather than inside `SettingsView` because `HUB_TABS.settings`
 * has to agree with it, and BUG-215's guard for that held a hand-copied third
 * list. The copy drifted: `updates` shipped with a deep link that silently
 * opened General, and the guard could not see it because it had the same
 * omission. Two lists can disagree; a list and a reference to it cannot.
 */
export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  { id: "general", label: "General", icon: "settings", group: "Personal" },
  { id: "notification", label: "Notifications", icon: "bell", group: "Personal" },
  { id: "voice", label: "Voice", icon: "mic", group: "Personal" },
  { id: "personalisation", label: "Personalisation", icon: "spark", group: "Personal" },
  { id: "security", label: "Security & sign-in", icon: "lock", group: "Personal" },
  { id: "privacy", label: "Privacy", icon: "shield", group: "Personal" },
  { id: "account", label: "Account", icon: "user", group: "Personal" },
  { id: "web-access", label: "Web access", icon: "connections", group: "System" },
  { id: "git-credential", label: "Git credential", icon: "branch", group: "System" },
  { id: "runtime", label: "Runtime configuration", icon: "system", group: "System" },
  { id: "updates", label: "Updates", icon: "refresh", group: "System" },
];
