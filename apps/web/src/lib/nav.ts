import type { IconName } from "./icons";

export interface NavItem { id: string; label: string; icon: IconName; hint: string; }
export interface NavGroup { label: string; items: NavItem[]; }

// Stable workbench navigation: work objects stay together, governance lives in
// one place, and read-first operational evidence is one destination rather than
// three competing pages.
export const NAV_GROUPS: NavGroup[] = [
  { label: "Home", items: [{ id: "home", label: "Workbench", icon: "spark", hint: "Resume governed work and see what needs attention" }] },
  { label: "Work", items: [
    { id: "new-chat", label: "Chat", icon: "chat", hint: "Start or continue a governed conversation" },
    { id: "search-chat", label: "Search Chat", icon: "search", hint: "Search your chat history" },
    { id: "tasks", label: "Tasks", icon: "tasks", hint: "Agent tasks and progress" },
    { id: "projects", label: "Projects", icon: "projects", hint: "Named scopes for ongoing work" },
    { id: "sessions", label: "Sessions", icon: "sessions", hint: "Past conversations and turns" },
  ] },
  { label: "Knowledge", items: [
    { id: "memory", label: "Memory", icon: "activity", hint: "Approved memories the agent can recall" },
    { id: "brain", label: "Brain", icon: "spark", hint: "Workspace relationships and sources" },
  ] },
  { label: "Control", items: [
    { id: "approvals", label: "Approvals", icon: "approvals", hint: "Decisions waiting on you" },
    { id: "capabilities", label: "Permissions", icon: "capabilities", hint: "What the agent may do, and how it must ask" },
    { id: "models", label: "Models", icon: "models", hint: "Model profiles and provider gates" },
    { id: "extensions", label: "Extensions", icon: "connections", hint: "Connectors, MCP servers, and what is not yet available" },
  ] },
  { label: "Observe", items: [
    { id: "observe", label: "Observability", icon: "diagnostics", hint: "Readiness, audit log, checkpoints, live work, and notifications" },
  ] },
  { label: "Utilities", items: [{ id: "settings", label: "Settings", icon: "settings", hint: "Runtime mode, security posture, appearance" }] },
];
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
export const DEFAULT_ROUTE = "home";

/**
 * Tabs inside a consolidated destination. The hub owns the tab list so a deep
 * link, the sidebar, and the hub's own tab strip all resolve to the same panel.
 */
export const HUB_TABS: Record<string, string[]> = {
  extensions: ["connectors", "mcp", "plugins", "channels"],
  observe: ["overview", "activity", "checkpoints", "diagnostics", "work", "notifications"],
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
};

function rawRoute(hash: string): string {
  return hash.replace(/^#\/?/, "").split("?")[0];
}

export function routeFromHash(hash: string): string {
  const raw = rawRoute(hash);
  if (NAV_ITEMS.some((item) => item.id === raw)) return raw;
  return ROUTE_ALIASES[raw]?.route ?? DEFAULT_ROUTE;
}

/**
 * The tab a hash selects, or null when the route has no tabs or the request
 * names a tab the hub does not have. An unknown tab falls back to the hub's
 * first panel rather than rendering nothing.
 */
export function tabFromHash(hash: string): string | null {
  const raw = rawRoute(hash);
  const route = routeFromHash(hash);
  const tabs = HUB_TABS[route];
  if (tabs === undefined) return null;
  const requested = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("tab");
  if (requested !== null && tabs.includes(requested)) return requested;
  const aliased = ROUTE_ALIASES[raw];
  if (aliased !== undefined && aliased.route === route) return aliased.tab;
  return tabs[0];
}

export function navItem(id: string): NavItem { return NAV_ITEMS.find((item) => item.id === id) ?? NAV_ITEMS[0]; }
