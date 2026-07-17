import type { IconName } from "./icons";

export interface NavItem {
  id: string;
  label: string;
  icon: IconName;
  /** Short description shown as the page kicker / tooltip. */
  hint: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

// Grouped left-nav for the local web app. The chat is the front door; governance
// and audit surfaces have their own sections so background detail never crowds
// the conversation.
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "The Hustle",
    items: [
      { id: "new-chat", label: "New Chat", icon: "chat", hint: "Start a fresh governed conversation" },
      { id: "search-chat", label: "Search Chat", icon: "search", hint: "Search your chat history" },
      { id: "memory", label: "Memory", icon: "activity", hint: "Approved memories the agent can recall" },
      { id: "tasks", label: "Tasks", icon: "tasks", hint: "Agent tasks and progress" },
      { id: "brain", label: "Brain View", icon: "spark", hint: "Graph of your workspace and Raiker activity" },
      { id: "work", label: "Work in Action", icon: "tasks", hint: "Live subagent work, queues, and schedules" },
      { id: "approvals", label: "Approvals", icon: "approvals", hint: "Decisions waiting on you" },
      { id: "projects", label: "Projects", icon: "projects", hint: "Named scopes for ongoing work" },
    ],
  },
  {
    label: "Steering",
    items: [
      {
        id: "capabilities",
        label: "Capabilities",
        icon: "capabilities",
        hint: "What the agent may do, and how it must ask",
      },
      { id: "models", label: "Models", icon: "models", hint: "Model profiles and provider gates" },
      {
        id: "connections",
        label: "Connections",
        icon: "connections",
        hint: "Governed service connectors and their status",
      },
      {
        id: "mcp",
        label: "MCP Servers",
        icon: "spark",
        hint: "Build, test, and manage local MCP servers",
      },
      {
        id: "checkpoints",
        label: "Checkpoints",
        icon: "checkpoints",
        hint: "Rewind metadata for every session",
      },
    ],
  },
  {
    label: "System",
    items: [
      { id: "sessions", label: "Sessions", icon: "sessions", hint: "Past conversations and turns" },
      { id: "activity", label: "Audit log", icon: "activity", hint: "The full append-only event record" },
      { id: "diagnostics", label: "Diagnostics", icon: "diagnostics", hint: "Runtime readiness and health" },
      { id: "settings", label: "Settings", icon: "settings", hint: "Runtime mode, security posture, appearance" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

export const DEFAULT_ROUTE = "new-chat";

export function routeFromHash(hash: string): string {
  const raw = hash.replace(/^#\/?/, "").split("?")[0];
  return NAV_ITEMS.some((item) => item.id === raw) ? raw : DEFAULT_ROUTE;
}

export function navItem(id: string): NavItem {
  return NAV_ITEMS.find((item) => item.id === id) ?? NAV_ITEMS[0];
}
