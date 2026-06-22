export interface NavItem {
  id: string;
  label: string;
}

// Left-nav information architecture (docs/UI-implementation/01_INFORMATION_ARCHITECTURE.md).
export const NAV_ITEMS: NavItem[] = [
  { id: "home", label: "Home" },
  { id: "tasks", label: "Tasks & Plans" },
  { id: "approvals", label: "Approvals" },
  { id: "capabilities", label: "Capabilities" },
  { id: "runtime-gates", label: "Runtime Gates" },
  { id: "models", label: "Models" },
  { id: "events", label: "Events / Audit Log" },
  { id: "checkpoints", label: "Checkpoints" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "settings", label: "Settings" },
];

export const DEFAULT_ROUTE = "home";

export function routeFromHash(hash: string): string {
  const raw = hash.replace(/^#\/?/, "");
  return NAV_ITEMS.some((item) => item.id === raw) ? raw : DEFAULT_ROUTE;
}
