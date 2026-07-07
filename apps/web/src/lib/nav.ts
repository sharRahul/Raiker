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
    label: "Work",
    items: [
      { id: "chat", label: "Chat", icon: "chat", hint: "Talk to your governed agent" },
      { id: "approvals", label: "Approvals", icon: "approvals", hint: "Decisions waiting on you" },
      { id: "tasks", label: "Tasks", icon: "tasks", hint: "Agent tasks and progress" },
      { id: "sessions", label: "Sessions", icon: "sessions", hint: "Past conversations and turns" },
    ],
  },
  {
    label: "Governance",
    items: [
      {
        id: "capabilities",
        label: "Capabilities",
        icon: "capabilities",
        hint: "What the agent may do, and how it must ask",
      },
      { id: "models", label: "Models", icon: "models", hint: "Model profiles and provider gates" },
      {
        id: "checkpoints",
        label: "Checkpoints",
        icon: "checkpoints",
        hint: "Rewind metadata for every session",
      },
      { id: "activity", label: "Audit log", icon: "activity", hint: "The full append-only event record" },
    ],
  },
  {
    label: "System",
    items: [
      { id: "diagnostics", label: "Diagnostics", icon: "diagnostics", hint: "Runtime readiness and health" },
      { id: "settings", label: "Settings", icon: "settings", hint: "Runtime mode, security posture, appearance" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

export const DEFAULT_ROUTE = "chat";

export function routeFromHash(hash: string): string {
  const raw = hash.replace(/^#\/?/, "");
  return NAV_ITEMS.some((item) => item.id === raw) ? raw : DEFAULT_ROUTE;
}

export function navItem(id: string): NavItem {
  return NAV_ITEMS.find((item) => item.id === id) ?? NAV_ITEMS[0];
}
