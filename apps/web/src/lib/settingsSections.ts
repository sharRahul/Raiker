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
 * Only sections the runtime actually backs. Voice, trusted-contact recovery,
 * data-export tooling, and cloud/cache controls are not presented as settings at
 * all. Voice has a runtime now, but not a decision: dictation uses the local one
 * when it is there and the browser when it is not, so there is nothing here for
 * an owner to set. The runtime itself lives with the other local runtimes, on
 * Models -> Local.
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
  { id: "personalisation", label: "Personalisation", icon: "spark", group: "Personal" },
  { id: "security", label: "Security & sign-in", icon: "lock", group: "Personal" },
  { id: "privacy", label: "Privacy", icon: "shield", group: "Personal" },
  { id: "account", label: "Account", icon: "user", group: "Personal" },
  { id: "web-access", label: "Web access", icon: "connections", group: "System" },
  { id: "git-credential", label: "Git credential", icon: "branch", group: "System" },
  { id: "runtime", label: "Runtime configuration", icon: "system", group: "System" },
  { id: "updates", label: "Updates", icon: "refresh", group: "System" },
];
