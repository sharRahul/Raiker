import { describe, expect, it } from "vitest";
import { DEFAULT_ROUTE, NAV_GROUPS, NAV_ITEMS, navItem, routeFromHash } from "./nav";

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

  it("keeps audit and live work under Observe", () => {
    expect(NAV_GROUPS[4].items.map((i) => i.id)).toEqual([
      "activity",
      "diagnostics",
      "work",
    ]);
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
      "work",
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
