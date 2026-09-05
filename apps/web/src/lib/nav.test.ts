import { describe, expect, it } from "vitest";
import { SETTINGS_SECTIONS } from "./settingsSections";
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

  it("uses one direct Core section plus four discoverable groups", () => {
    expect(NAV_GROUPS.map((g) => [g.id, g.label, g.collapsible])).toEqual([
      ["core", "Core", false],
      ["knowledge", "Knowledge", true],
      ["manage", "Manage", true],
      ["observe", "Observe", true],
      ["support", "Support", true],
    ]);
  });

  it("keeps Knowledge to what Raiker has stored", () => {
    // Checkpoints moved to Observe: rewind data is an operational record, not
    // knowledge the agent recalls.
    expect(NAV_GROUPS[1].items.map((i) => i.id)).toEqual(["memory", "brain"]);
  });

  it("labels the capability gates as Permissions", () => {
    // The route id stays `capabilities` so every existing deep link and the
    // backend vocabulary keep working; only the human label changes.
    expect(navItem("capabilities").label).toBe("Permissions");
    expect(routeFromHash("#/capabilities")).toBe("capabilities");
  });

  it("keeps work objects together", () => {
    expect(NAV_GROUPS[0].items.map((i) => i.id)).toEqual([
      "home",
      "new-chat",
      // Design is a making surface, not plumbing: you describe what you want
      // and a model answers, exactly as in Chat and Build. It sat last in this
      // group, next to Messaging, which is where the channels live.
      "build",
      "design",
      "search-chat",
      "tasks",
      "projects",
      "approvals",
      "messaging",
    ]);
  });

  it("uses sentence case for the direct conversation browser", () => {
    expect(navItem("search-chat").label).toBe("Threads");
  });

  it("consolidates the operational record into one Observe destination", () => {
    expect(NAV_GROUPS[3].items.map((i) => i.id)).toEqual(["observe"]);
    expect(HUB_TABS.observe).toEqual([
      "overview",
      "sessions",
      "activity",
      "checkpoints",
      "work",
      "notifications",
    ]);
  });

  it("consolidates connectors and MCP into one Extensions destination", () => {
    // Approvals left this group for Core when Manage moved behind the gear: a
    // decision waiting on you arrives many times a day, while Permissions and
    // Models are configured once.
    expect(NAV_GROUPS[2].items.map((i) => i.id)).toEqual([
      "capabilities",
      "models",
      "extensions",
    ]);
    // Channels left Extensions for their own destination; the alias keeps every
    // link that named the tab working, which is what that map is for.
    expect(HUB_TABS.extensions).not.toContain("channels");
    expect(routeFromHash("#/channels")).toBe("messaging");
    expect(routeFromHash("#/extensions?tab=channels")).toBe("extensions");
    // Hooks sits with the other extension surfaces rather than under Permissions:
    // a hook is something the owner installs, and it can only ever tighten what
    // Permissions already allows.
    expect(HUB_TABS.extensions).toEqual([
      "connectors",
      "mcp",
      "skills",
      "hooks",
      "plugins",
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
    // Diagnostics was folded into Overview: four of its six cards restated the
    // tiles there from the same object, and the rest is an Overview section now.
    // The route still resolves rather than falling through to the Workbench.
    expect(routeFromHash("#/diagnostics?session=sess_1")).toBe("observe");
    expect(tabFromHash("#/diagnostics?session=sess_1")).toBe("overview");
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
  });

  // Bookmarks and older builds still emit the pre-split ids. They must land on
  // the panel that now owns their content, not on the default tab.
  it("maps a superseded Models tab id onto the panel that replaced it", () => {
    expect(tabFromHash("#/models?tab=providers")).toBe("local");
    // Posture held four read-only facts and a paragraph. The facts are a strip
    // at the top of Hosted, where they explain the cards beneath them; the
    // paragraph is in the guide.
    expect(tabFromHash("#/models?tab=posture")).toBe("hosted");
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
  // The rail itself, not a copy of it. This guard held a hand-copied list, and
  // the copy drifted: `updates` shipped with a deep link that silently opened
  // General and the guard could not see it, because the list it was comparing
  // against had the same omission.
  const RAIL = SETTINGS_SECTIONS.map((section) => section.id);

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
