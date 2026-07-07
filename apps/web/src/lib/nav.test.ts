import { describe, expect, it } from "vitest";
import { DEFAULT_ROUTE, NAV_GROUPS, NAV_ITEMS, navItem, routeFromHash } from "./nav";

describe("nav model", () => {
  it("defaults to chat and resolves known hashes", () => {
    expect(DEFAULT_ROUTE).toBe("chat");
    expect(routeFromHash("")).toBe("chat");
    expect(routeFromHash("#/capabilities")).toBe("capabilities");
    expect(routeFromHash("#settings")).toBe("settings");
    expect(routeFromHash("#/nonsense")).toBe("chat");
  });

  it("keeps every governed surface reachable from the nav", () => {
    const ids = NAV_ITEMS.map((i) => i.id);
    for (const required of [
      "chat",
      "approvals",
      "tasks",
      "sessions",
      "capabilities",
      "models",
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
