import { describe, expect, it } from "vitest";
import { DEFAULT_ROUTE, NAV_GROUPS, NAV_ITEMS, navItem, routeFromHash } from "./nav";

describe("nav model", () => {
  it("defaults to New Chat and resolves known hashes", () => {
    expect(DEFAULT_ROUTE).toBe("new-chat");
    expect(routeFromHash("")).toBe("new-chat");
    expect(routeFromHash("#/capabilities")).toBe("capabilities");
    expect(routeFromHash("#settings")).toBe("settings");
    expect(routeFromHash("#/search-chat")).toBe("search-chat");
    expect(routeFromHash("#/nonsense")).toBe("new-chat");
  });

  it("renames the top two groups (Epic 4)", () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual(["The Hustle", "Steering", "System"]);
  });

  it("orders The Hustle with Approvals below Tasks and the chat split up top", () => {
    expect(NAV_GROUPS[0].items.map((i) => i.id)).toEqual([
      "new-chat",
      "search-chat",
      "tasks",
      "approvals",
      "projects",
    ]);
  });

  it("moves Sessions and Audit log under System", () => {
    expect(NAV_GROUPS[2].items.map((i) => i.id)).toEqual([
      "sessions",
      "activity",
      "diagnostics",
      "settings",
    ]);
  });

  it("keeps every governed surface reachable from the nav", () => {
    const ids = NAV_ITEMS.map((i) => i.id);
    for (const required of [
      "new-chat",
      "search-chat",
      "approvals",
      "tasks",
      "sessions",
      "projects",
      "capabilities",
      "models",
      "connections",
      "checkpoints",
      "activity",
      "diagnostics",
      "settings",
    ]) {
      expect(ids).toContain(required);
    }
  });

  it("groups items without duplicates and navItem falls back to the first item", () => {
    const ids = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(navItem("capabilities").id).toBe("capabilities");
    expect(navItem("unknown").id).toBe(NAV_ITEMS[0].id);
  });
});
