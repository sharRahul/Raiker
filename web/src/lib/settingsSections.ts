import type { IconName } from "./icons";

export interface SettingsSection {
  id: string;
  label: string;
  icon: IconName;
  group: "Experience" | "Security & data" | "Developer & runtime";
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
/**
 * Three groups, not two.
 *
 * "Personal" held six of the ten sections, which made it the list it was meant
 * to break up: appearance sat beside sign-in and beside the account itself, so
 * the grouping separated *whose* setting it was rather than what kind of
 * decision it is. Splitting the security and data half out gives each group one
 * subject, and the ten rows stop reading as a flat list with a divider in it.
 */
export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  // QUI-L09 — Account folds into General: the name you are greeted by and the
  // account it belongs to are one subject.
  { id: "general", label: "General", icon: "settings", group: "Experience" },
  { id: "personalisation", label: "Personalisation", icon: "spark", group: "Experience" },
  { id: "notification", label: "Notifications", icon: "bell", group: "Experience" },
  { id: "security", label: "Security", icon: "lock", group: "Security & data" },
  { id: "privacy", label: "Privacy", icon: "shield", group: "Security & data" },
  // PA-D02 — where a goal's work may run and what may leave with it. Settings
  // is the only place a profile is made, changed, activated or bound.
  { id: "execution-profiles", label: "Execution profiles", icon: "shield", group: "Security & data" },
  { id: "web-access", label: "Web access", icon: "connections", group: "Security & data" },
  // QUI-L09 — Runtime configuration, the memory engine, what serves models and
  // what they cost are one Advanced section with a segment each. GitHub is a
  // service you connect, so it is in Connections now.
  { id: "advanced", label: "Advanced", icon: "system", group: "Developer & runtime" },
  { id: "updates", label: "About & updates", icon: "refresh", group: "Developer & runtime" },
];

/** Sections that were renamed or folded: an old deep link opens the new one, never General. */
export const SECTION_ALIASES: Readonly<Record<string, string>> = {
  account: "general",
  runtime: "advanced",
  "memory-engine": "advanced",
};

/** Sections that left Settings for another page, and where they went. */
export const SECTIONS_MOVED: Readonly<Record<string, string>> = {
  github: "#/connections?tab=services&item=github-account",
  "git-credential": "#/connections?tab=services&item=github-account",
};

/**
 * Where a hash that names a moved Settings section should go now, or null.
 * The shell asks on every address change, so the forward works whether or
 * not Settings is already open.
 */
export function movedSettingsAddress(hash: string): string | null {
  if (!/^#\/?settings(?:[?/]|$)/.test(hash)) return null;
  const tab = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("tab");
  return tab === null ? null : (SECTIONS_MOVED[tab] ?? null);
}

/** QUI-L09 — the segments of Settings › Advanced, in order. */
export const ADVANCED_SETTINGS = [
  { id: "runtime", label: "Runtime" },
  { id: "memory-engine", label: "Memory engine" },
  { id: "models", label: "Model serving" },
  { id: "usage", label: "Usage and spending" },
] as const;
export type AdvancedSetting = (typeof ADVANCED_SETTINGS)[number]["id"];

/**
 * Which Advanced segment a hash names: `?kind=`, or the old section a link
 * still carries (`?tab=runtime`, `?tab=memory-engine`). Runtime otherwise.
 */
export function advancedSettingFromHash(hash: string): AdvancedSetting {
  const query = new URLSearchParams(hash.split("?", 2)[1] ?? "");
  for (const candidate of [query.get("kind"), query.get("tab")]) {
    const found = ADVANCED_SETTINGS.find((item) => item.id === candidate);
    if (found !== undefined) return found.id;
  }
  return "runtime";
}

const BY_ID = new Map(SETTINGS_SECTIONS.map((section) => [section.id, section]));

/**
 * One settings section by id, for the surfaces that list sections outside the
 * rail — the command palette and All pages. They each kept a label table of
 * their own, which had no row for Memory engine and named two sections
 * differently from the rail (OPT-20).
 */
export function settingsSection(id: string): SettingsSection | undefined {
  return BY_ID.get(SECTION_ALIASES[id] ?? id);
}
