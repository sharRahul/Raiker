import type { IconName } from "./icons";

export interface NavItem { id: string; label: string; icon: IconName; hint: string; }
export type NavGroupId = "core" | "knowledge" | "manage" | "observe" | "support";
export interface NavGroup { id: NavGroupId; label: string; collapsible: boolean; items: NavItem[]; }

// Stable workbench navigation: work objects stay together, governance lives in
// one place, and read-first operational evidence is one destination rather than
// three competing pages.
export const NAV_GROUPS: NavGroup[] = [
  { id: "core", label: "Core", collapsible: false, items: [
    { id: "home", label: "Workbench", icon: "spark", hint: "Resume governed work and see what needs attention" },
    { id: "new-chat", label: "Chat", icon: "chat", hint: "Start or continue a governed conversation" },
    { id: "build", label: "Build", icon: "code", hint: "Code against a repository with Plan, Edit, and Auto" },
    { id: "search-chat", label: "Search chats", icon: "search", hint: "Browse or search your chat history" },
    { id: "tasks", label: "Tasks", icon: "tasks", hint: "Agent tasks and progress" },
    { id: "projects", label: "Projects", icon: "projects", hint: "Named scopes for ongoing work" },
  ] },
  { id: "knowledge", label: "Knowledge", collapsible: true, items: [
    { id: "memory", label: "Memory", icon: "activity", hint: "Approved memories the agent can recall" },
    { id: "brain", label: "Knowledge Map", icon: "spark", hint: "Governed workspace relationships and sources" },
  ] },
  { id: "manage", label: "Manage", collapsible: true, items: [
    { id: "approvals", label: "Approvals", icon: "approvals", hint: "Decisions waiting on you" },
    { id: "capabilities", label: "Permissions", icon: "capabilities", hint: "What the agent may do, and how it must ask" },
    { id: "models", label: "Models", icon: "models", hint: "Model profiles and provider gates" },
    { id: "extensions", label: "Extensions", icon: "connections", hint: "Connectors, MCP servers, skills, hooks and plugins" },
  ] },
  { id: "observe", label: "Observe", collapsible: true, items: [
    { id: "observe", label: "Observability", icon: "diagnostics", hint: "Readiness, audit log, checkpoints, live work, and notifications" },
  ] },
  { id: "support", label: "Support", collapsible: true, items: [
    { id: "guide", label: "Guide", icon: "info", hint: "How Raiker works, in the product" },
    { id: "settings", label: "Settings", icon: "settings", hint: "Runtime, security posture, appearance" },
  ] },
];
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
export const DEFAULT_ROUTE = "home";

/**
 * Tabs inside a consolidated destination. The hub owns the tab list so a deep
 * link, the sidebar, and the hub's own tab strip all resolve to the same panel.
 */
export const HUB_TABS: Record<string, string[]> = {
  // Models is organised by what you came to do, not by which table the data
  // lives in: obtain a model that runs on this machine, sign in to somebody
  // else's, fetch or convert one from the Hub, watch that work, decide what
  // serves a turn when the first choice cannot, see what it costs, or read the
  // off-machine posture.
  models: [
    "local",
    "hosted",
    "huggingface",
    "activity",
    "routing",
    "pricing",
    "posture",
  ],
  extensions: ["connectors", "mcp", "skills", "hooks", "plugins", "channels"],
  observe: ["overview", "sessions", "activity", "checkpoints", "diagnostics", "work", "notifications"],
  // Every section the settings rail renders, in rail order. The two lists have
  // to agree: a section the rail shows but this list omits is a deep link that
  // silently opens General instead, which reads as a working link to the wrong
  // page. `web-access` and `git-credential` were in exactly that state before
  // `privacy` joined them.
  settings: [
    "general",
    "notification",
    "personalisation",
    "security",
    "privacy",
    "account",
    "web-access",
    "git-credential",
    "runtime",
  ],
};

/**
 * Routes that were their own destination before the hubs existed. Existing
 * deep links (and the cross-links session detail already emits) must keep
 * working, so each one resolves to its hub and opens the matching tab rather
 * than silently falling back to the Workbench.
 */
const ROUTE_ALIASES: Record<string, { route: string; tab: string }> = {
  connections: { route: "extensions", tab: "connectors" },
  mcp: { route: "extensions", tab: "mcp" },
  activity: { route: "observe", tab: "activity" },
  checkpoints: { route: "observe", tab: "checkpoints" },
  diagnostics: { route: "observe", tab: "diagnostics" },
  work: { route: "observe", tab: "work" },
  notifications: { route: "observe", tab: "notifications" },
  sessions: { route: "observe", tab: "sessions" },
};

/**
 * Tab ids a hub used to have, mapped to the panel that now owns their content.
 *
 * A tab id travels: it sits in bookmarks, in links other views emit, and in
 * e2e specs. Renaming one without a mapping does not fail loudly — the request
 * simply misses `HUB_TABS` and falls through to the hub's first panel, which
 * looks like a working link to the wrong place.
 */
const HUB_TAB_ALIASES: Record<string, Record<string, string>> = {
  // The single "Providers" scroll became Local and Hosted; "Library" was the
  // local GGUF index, now part of Local; "Discover" was the Hub search.
  models: {
    providers: "local",
    library: "local",
    discover: "huggingface",
    downloads: "activity",
  },
};

function rawRoute(hash: string): string {
  return hash.replace(/^#\/?/, "").split("?")[0];
}

export function routeFromHash(hash: string): string {
  const raw = rawRoute(hash);
  if (raw === "model-setup") return raw;
  if (NAV_ITEMS.some((item) => item.id === raw)) return raw;
  return ROUTE_ALIASES[raw]?.route ?? DEFAULT_ROUTE;
}

/**
 * The tab a hash selects, or null when the route has no tabs or the request
 * names a tab the hub does not have. An unknown tab falls back to the hub's
 * first panel rather than rendering nothing.
 */
/**
 * The `?section=` a guide deep link names, or null.
 *
 * Guide pages are not hub tabs — the set is whatever the install shipped, so it
 * cannot be validated against a constant here. The view resolves it against the
 * sections the API actually returned and falls back to the first one.
 */
export function sectionFromHash(hash: string): string | null {
  const requested = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("section");
  return requested !== null && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requested) ? requested : null;
}

export function tabFromHash(hash: string): string | null {
  const raw = rawRoute(hash);
  const route = routeFromHash(hash);
  const tabs = HUB_TABS[route];
  if (tabs === undefined) return null;
  const requested = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("tab");
  if (requested !== null && tabs.includes(requested)) return requested;
  const supersededBy = requested === null ? undefined : HUB_TAB_ALIASES[route]?.[requested];
  if (supersededBy !== undefined && tabs.includes(supersededBy)) return supersededBy;
  const aliased = ROUTE_ALIASES[raw];
  if (aliased !== undefined && aliased.route === route) return aliased.tab;
  return tabs[0];
}

// Routes that own a page but deliberately have no sidebar entry. Without them
// `navItem` falls back to the first nav item for anything it does not know, so
// the first-run model setup screen was titled "Workbench" and carried the
// Workbench hint — the other half of FIXED-144.
const OFF_NAV_ITEMS: NavItem[] = [
  {
    id: "model-setup",
    label: "Finish setup",
    icon: "models",
    hint: "Confirm model, privacy and backup choices before your first turn",
  },
];

export function navItem(id: string): NavItem {
  return (
    NAV_ITEMS.find((item) => item.id === id) ??
    OFF_NAV_ITEMS.find((item) => item.id === id) ??
    NAV_ITEMS[0]
  );
}
