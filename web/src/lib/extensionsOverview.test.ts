// VIS2-10 / VIS2-18 — the overview is exception-led, and never invents a state.
import { describe, expect, it } from "vitest";
import {
  extensionExceptions,
  extensionReach,
  reachSentence,
  tabForKind,
} from "./extensionsOverview";
import type { ExtensionView } from "./apiTypes";

function extension(partial: Partial<ExtensionView>): ExtensionView {
  return {
    extension_id: "ext_1",
    kind: "connector",
    display_name: "GitHub",
    category: "connectors",
    installed: true,
    connected: true,
    enabled: true,
    usable: true,
    blocked_reason: null,
    detail: "",
    capability: null,
    gate_state: null,
    decision_mode: null,
    egress_host: null,
    egress_allowed: null,
    transport: null,
    monitor_state: null,
    tool_count: 3,
    last_activity_at: null,
    ...partial,
  };
}

describe("exceptions", () => {
  it("shows only what is installed and cannot be used", () => {
    // A wall of green cards reports "nothing is wrong" in the most expensive
    // way available, and trains the owner to skim past the one that is not.
    const rows = extensionExceptions([
      extension({ extension_id: "a", usable: true }),
      extension({ extension_id: "b", usable: false, blocked_reason: "Vault is locked." }),
    ]);
    expect(rows.map((row) => row.extensionId)).toEqual(["b"]);
    expect(rows[0].reason).toBe("Vault is locked.");
  });

  it("does not treat 'not installed' as a problem", () => {
    // Not installed is a thing the owner has not done, not a fault.
    expect(
      extensionExceptions([extension({ installed: false, usable: false })]),
    ).toEqual([]);
  });

  it("uses the runtime's own reason rather than a paraphrase", () => {
    const [row] = extensionExceptions([
      extension({ usable: false, blocked_reason: null, detail: "Server exited at start." }),
    ]);
    expect(row.reason).toBe("Server exited at start.");
  });

  it("says something rather than nothing when the runtime gave no reason", () => {
    const [row] = extensionExceptions([
      extension({ usable: false, blocked_reason: null, detail: "" }),
    ]);
    expect(row.reason).toBe("Not usable yet.");
  });

  it("points each exception at the tab that owns its fix", () => {
    const rows = extensionExceptions([
      extension({ extension_id: "a", kind: "mcp_server", usable: false }),
      extension({ extension_id: "b", kind: "skill", usable: false }),
      extension({ extension_id: "c", kind: "plugin", usable: false }),
    ]);
    expect(rows.map((row) => row.tab)).toEqual(["mcp", "skills", "plugins"]);
  });

  it("survives a payload that is not a list", () => {
    expect(extensionExceptions(null)).toEqual([]);
    expect(extensionExceptions(undefined)).toEqual([]);
  });
});

describe("reach", () => {
  it("counts what is usable, what is installed, and the tools they offer", () => {
    const reach = extensionReach([
      extension({ extension_id: "a", usable: true, tool_count: 3 }),
      extension({ extension_id: "b", usable: true, tool_count: 2 }),
      extension({ extension_id: "c", usable: false, tool_count: 9 }),
      extension({ extension_id: "d", installed: false, usable: false }),
    ]);
    // The unusable one's tools are not reach: they cannot be called.
    expect(reach).toEqual({ usable: 2, installed: 3, tools: 5 });
  });

  it("says nothing is installed rather than showing three zeroes", () => {
    expect(reachSentence(extensionReach([]))).toContain("Nothing is installed yet");
  });

  it("says plainly when everything installed is blocked", () => {
    const reach = extensionReach([extension({ usable: false })]);
    expect(reachSentence(reach)).toBe("1 installed, and none of them can be used yet.");
  });

  it("counts one tool in the singular", () => {
    expect(reachSentence({ usable: 1, installed: 1, tools: 1 })).toContain("offering 1 tool.");
  });

  it("omits the tool clause when there are none, rather than saying zero", () => {
    expect(reachSentence({ usable: 1, installed: 2, tools: 0 })).toBe(
      "1 of 2 installed extensions can be used.",
    );
  });
});

describe("tabForKind", () => {
  it("maps every kind the page renders", () => {
    expect(tabForKind("connector")).toBe("connectors");
    expect(tabForKind("mcp_servers")).toBe("mcp");
    expect(tabForKind("hooks")).toBe("hooks");
    expect(tabForKind("panels")).toBe("plugins");
  });

  it("sends an unknown kind somewhere real rather than nowhere", () => {
    expect(tabForKind("something-new")).toBe("connectors");
  });
});
