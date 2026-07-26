import { describe, expect, it } from "vitest";
import {
  DEFAULT_ROUTE,
  HUB_TABS,
  NAV_GROUPS,
  NAV_ITEMS,
  navItem,
  routeFromHash,
  tabFromHash,
} from "./nav";

describe("nav model", () => {
  it("defaults to the Workbench and resolves known hashes", () => {
    expect(DEFAULT_ROUTE).toBe("home");
    expect(routeFromHash("")).toBe("home");
    expect(routeFromHash("#/capabilities")).toBe("capabilities");
    expect(routeFromHash("#settings")).toBe("settings");
    expect(routeFromHash("#/search-chat")).toBe("search-chat");
    expect(routeFromHash("#/nonsense")).toBe("home");
  });

  it("uses the five stable workbench destinations plus utilities", () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual(["Home", "Work", "Knowledge", "Control", "Observe", "Utilities"]);
  });

  it("keeps work objects together", () => {
    expect(NAV_GROUPS[1].items.map((i) => i.id)).toEqual([
      "new-chat",
      "search-chat",
      "tasks",
      "projects",
      "sessions",
    ]);
  });

  it("consolidates the operational record into one Observe destination", () => {
    expect(NAV_GROUPS[4].items.map((i) => i.id)).toEqual(["observe"]);
    expect(HUB_TABS.observe).toEqual([
      "overview",
      "activity",
      "diagnostics",
      "work",
      "notifications",
    ]);
  });

  it("consolidates connectors and MCP into one Extensions destination", () => {
    expect(NAV_GROUPS[3].items.map((i) => i.id)).toEqual([
      "approvals",
      "capabilities",
      "models",
      "extensions",
    ]);
    expect(HUB_TABS.extensions).toEqual(["connectors", "mcp", "plugins", "channels"]);
  });

  it("keeps every governed surface reachable from the nav", () => {
    const ids = NAV_ITEMS.map((i) => i.id);
    for (const required of [
      "new-chat",
      "search-chat",
      "memory",
      "approvals",
      "tasks",
      "brain",
      "sessions",
      "projects",
      "capabilities",
      "models",
      "extensions",
      "checkpoints",
      "observe",
      "settings",
    ]) {
      expect(ids).toContain(required);
    }
  });

  it("resolves a pre-hub deep link to its hub and the matching tab", () => {
    // Links already emitted by session detail, notifications, and the guides
    // must keep working — a stale hash opens the right panel, never the
    // Workbench fallback.
    expect(routeFromHash("#/activity")).toBe("observe");
    expect(tabFromHash("#/activity")).toBe("activity");
    expect(routeFromHash("#/work")).toBe("observe");
    expect(tabFromHash("#/work")).toBe("work");
    expect(routeFromHash("#/diagnostics?session=sess_1")).toBe("observe");
    expect(tabFromHash("#/diagnostics?session=sess_1")).toBe("diagnostics");
    expect(routeFromHash("#/mcp")).toBe("extensions");
    expect(tabFromHash("#/mcp")).toBe("mcp");
    expect(routeFromHash("#/connections")).toBe("extensions");
    expect(tabFromHash("#/connections")).toBe("connectors");
  });

  it("falls back to a hub's first panel for an unknown or absent tab", () => {
    expect(tabFromHash("#/observe")).toBe("overview");
    expect(tabFromHash("#/observe?tab=nonsense")).toBe("overview");
    expect(tabFromHash("#/extensions?tab=plugins")).toBe("plugins");
    expect(tabFromHash("#/capabilities")).toBeNull();
  });

  it("groups items without duplicates and navItem falls back to the first item", () => {
    const ids = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(navItem("capabilities").id).toBe("capabilities");
    expect(navItem("unknown").id).toBe(NAV_ITEMS[0].id);
  });
});
