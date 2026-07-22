import type { IconName } from "./icons";

export interface NavItem { id: string; label: string; icon: IconName; hint: string; }
export interface NavGroup { label: string; items: NavItem[]; }

// Stable workbench navigation: work objects remain together while governance
// and read-first operational evidence stay easy to find.
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
    { id: "checkpoints", label: "Checkpoints", icon: "checkpoints", hint: "Rewind metadata for every session" },
  ] },
  { label: "Control", items: [
    { id: "approvals", label: "Approvals", icon: "approvals", hint: "Decisions waiting on you" },
    { id: "capabilities", label: "Capabilities", icon: "capabilities", hint: "What the agent may do, and how it must ask" },
    { id: "models", label: "Models", icon: "models", hint: "Model profiles and provider gates" },
    { id: "connections", label: "Extensions", icon: "connections", hint: "Governed service connectors and their status" },
    { id: "mcp", label: "MCP Servers", icon: "spark", hint: "Connect and monitor local or remote MCP servers" },
  ] },
  { label: "Observe", items: [
    { id: "activity", label: "Audit log", icon: "activity", hint: "The full append-only event record" },
    { id: "diagnostics", label: "Diagnostics", icon: "diagnostics", hint: "Runtime readiness and health" },
    { id: "work", label: "Work in Action", icon: "tasks", hint: "Live subagent work, queues, and schedules" },
  ] },
  { label: "Utilities", items: [{ id: "settings", label: "Settings", icon: "settings", hint: "Runtime mode, security posture, appearance" }] },
];
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
export const DEFAULT_ROUTE = "home";
export function routeFromHash(hash: string): string { const raw = hash.replace(/^#\/?/, "").split("?")[0]; return NAV_ITEMS.some((item) => item.id === raw) ? raw : DEFAULT_ROUTE; }
export function navItem(id: string): NavItem { return NAV_ITEMS.find((item) => item.id === id) ?? NAV_ITEMS[0]; }
