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

  it("keeps Knowledge to what Raiker has stored", () => {
    // Checkpoints moved to Observe: rewind data is an operational record, not
    // knowledge the agent recalls.
    expect(NAV_GROUPS[2].items.map((i) => i.id)).toEqual(["memory", "brain"]);
  });

  it("labels the capability gates as Permissions", () => {
    // The route id stays `capabilities` so every existing deep link and the
    // backend vocabulary keep working; only the human label changes.
    expect(navItem("capabilities").label).toBe("Permissions");
    expect(routeFromHash("#/capabilities")).toBe("capabilities");
  });

  it("keeps work objects together", () => {
    expect(NAV_GROUPS[1].items.map((i) => i.id)).toEqual([
      "new-chat",
      "build",
      "search-chat",
      "tasks",
      "projects",
    ]);
  });

  it("consolidates the operational record into one Observe destination", () => {
    expect(NAV_GROUPS[4].items.map((i) => i.id)).toEqual(["observe"]);
    expect(HUB_TABS.observe).toEqual([
      "overview",
      "sessions",
      "activity",
      "checkpoints",
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
    // Hooks sits with the other extension surfaces rather than under Permissions:
    // a hook is something the owner installs, and it can only ever tighten what
    // Permissions already allows.
    expect(HUB_TABS.extensions).toEqual([
      "connectors",
      "mcp",
      "skills",
      "hooks",
      "plugins",
      "channels",
    ]);
  });

  it("keeps every governed surface reachable from the nav", () => {
    const ids = NAV_ITEMS.map((i) => i.id);
    for (const required of [
      "new-chat",
      "build",
      "search-chat",
      "memory",
      "approvals",
      "tasks",
      "brain",
      "projects",
      "capabilities",
      "models",
      "extensions",
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
    expect(routeFromHash("#/sessions?session=sess_1")).toBe("observe");
    expect(tabFromHash("#/sessions?session=sess_1")).toBe("sessions");
    expect(routeFromHash("#/mcp")).toBe("extensions");
    expect(tabFromHash("#/mcp")).toBe("mcp");
    expect(routeFromHash("#/connections")).toBe("extensions");
    expect(tabFromHash("#/connections")).toBe("connectors");
    expect(routeFromHash("#/checkpoints")).toBe("observe");
    expect(tabFromHash("#/checkpoints")).toBe("checkpoints");
  });

  // Models grew Local, Hosted, Hugging Face, and Activity panels but `HUB_TABS`
  // still listed only the pre-BUG-69 four, so every deep link into an
  // unregistered panel fell through to the hub's first tab. Verified live on
  // 2026-08-09: `#/models?tab=library` opened Providers, which is where the
  // "Use models LM Studio already downloaded →" link and the operation tray's
  // "View downloads" both pointed.
  it("resolves every Models panel from a deep link", () => {
    expect(tabFromHash("#/models?tab=local")).toBe("local");
    expect(tabFromHash("#/models?tab=hosted")).toBe("hosted");
    expect(tabFromHash("#/models?tab=huggingface")).toBe("huggingface");
    expect(tabFromHash("#/models?tab=activity")).toBe("activity");
    expect(tabFromHash("#/models?tab=routing")).toBe("routing");
    expect(tabFromHash("#/models?tab=pricing")).toBe("pricing");
    expect(tabFromHash("#/models?tab=posture")).toBe("posture");
  });

  // Bookmarks and older builds still emit the pre-split ids. They must land on
  // the panel that now owns their content, not on the default tab.
  it("maps a superseded Models tab id onto the panel that replaced it", () => {
    expect(tabFromHash("#/models?tab=providers")).toBe("local");
    expect(tabFromHash("#/models?tab=library")).toBe("local");
    expect(tabFromHash("#/models?tab=discover")).toBe("huggingface");
    expect(tabFromHash("#/models?tab=downloads")).toBe("activity");
  });

  it("falls back to a hub's first panel for an unknown or absent tab", () => {
    expect(tabFromHash("#/observe")).toBe("overview");
    expect(tabFromHash("#/observe?tab=nonsense")).toBe("overview");
    expect(tabFromHash("#/extensions?tab=plugins")).toBe("plugins");
    expect(tabFromHash("#/settings?tab=runtime")).toBe("runtime");
    expect(tabFromHash("#/capabilities")).toBeNull();
  });

  it("groups items without duplicates and navItem falls back to the first item", () => {
    const ids = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(navItem("capabilities").id).toBe("capabilities");
    expect(navItem("unknown").id).toBe(NAV_ITEMS[0].id);
  });

  // A route with a page but no sidebar entry used to inherit the first nav
  // item's title and hint, so the first-run model setup screen was headed
  // "Workbench · Resume governed work and see what needs attention".
  it("titles an off-nav route as itself rather than as the Workbench", () => {
    expect(navItem("model-setup").label).toBe("Finish setup");
    expect(navItem("model-setup").hint).not.toBe(NAV_ITEMS[0].hint);
    expect(NAV_ITEMS.some((item) => item.id === "model-setup")).toBe(false);
  });
});

// BUG-215 shipped a Privacy section and found the same defect this file already
// guards for Models: the settings rail renders sections `HUB_TABS.settings` does
// not list, so `#/settings?tab=web-access` silently opened General. A deep link
// that lands on the wrong page looks exactly like one that works.
describe("settings sections and their deep links", () => {
  // The rail's own order, read from SettingsView. Kept here rather than imported
  // because the point is that two independent lists agree.
  const RAIL = [
    "general",
    "notification",
    "personalisation",
    "security",
    "privacy",
    "account",
    "web-access",
    "git-credential",
    "runtime",
  ];

  it("gives every settings section a working deep link", () => {
    expect(HUB_TABS.settings).toEqual(RAIL);
    for (const section of RAIL) {
      expect(tabFromHash(`#/settings?tab=${section}`)).toBe(section);
    }
  });

  it("still falls back to General for a section that does not exist", () => {
    expect(tabFromHash("#/settings?tab=nonsense")).toBe("general");
    expect(tabFromHash("#/settings")).toBe("general");
  });
});
