// COMPOSER-19 — the composer's capability contract, held to its two rules.
//
// The composer's bar grew by accretion: every capability Raiker gained arrived
// as one more permanent control, because a permanent control is the cheapest
// thing to add and nothing said not to. The registry is what says not to, and
// it can only do that if the two rules it exists for are actually enforced
// rather than merely written down:
//
//   1. Visibility is not authority. A menu entry reflects a capability the
//      runtime may still allow, ask about, or deny when it is invoked.
//   2. A menu entry has to reach something real, or not be drawn.
import { describe, expect, it } from "vitest";
import { makeGate } from "./test-helpers";
import {
  COMPOSER_CAPABILITIES,
  composerMenu,
  type ComposerSurface,
} from "./composerCapabilities";

const ALL = new Set(COMPOSER_CAPABILITIES.map((capability) => capability.id));

describe("the registry itself", () => {
  it("gives every capability a unique id", () => {
    expect(ALL.size).toBe(COMPOSER_CAPABILITIES.length);
  });

  it("names a surface for every capability", () => {
    // A capability that belongs nowhere is one nobody can reach, which is a
    // more expensive way of not having it.
    for (const capability of COMPOSER_CAPABILITIES) {
      expect(capability.surfaces.length, capability.id).toBeGreaterThan(0);
    }
  });

  it("gives every gated capability somewhere to go when it is off", () => {
    // Rule 1's other half: telling an owner a capability is disabled and
    // stopping there is a dead end. Every gated entry names the route that
    // changes it.
    for (const capability of COMPOSER_CAPABILITIES) {
      if (capability.gate === undefined) continue;
      expect(capability.enableHref, capability.id).toBeTruthy();
    }
  });

  it("says what each capability does rather than that it is safe", () => {
    for (const capability of COMPOSER_CAPABILITIES) {
      expect(capability.hint.trim(), capability.id).not.toBe("");
      expect(capability.hint, capability.id).not.toMatch(/\b(safe|secure|protected)\b/i);
    }
  });
});

describe("what a menu shows", () => {
  it("omits a capability the surface has no handler for", () => {
    // Rule 2. The acceptance test the review sets is that every exposed action
    // reaches a real path; the cheapest way to keep that true is to make the
    // absence of a handler mean absence from the menu, rather than a promise
    // this view happens not to keep.
    const none = composerMenu("add", "chat", [], new Set());
    expect(none).toEqual([]);

    const one = composerMenu("add", "chat", [], new Set(["attach-file"]));
    expect(one.map((item) => item.id)).toEqual(["attach-file"]);
  });

  it("keeps each surface to what means something there", () => {
    const build = composerMenu("tools", "build", [], ALL).map((item) => item.id);
    const chat = composerMenu("tools", "chat", [], ALL).map((item) => item.id);
    // Running a command is Build's, because Build is the surface with a
    // repository and a governed terminal.
    expect(build).toContain("run-command");
    expect(chat).not.toContain("run-command");
  });

  it("puts the two groups in different menus", () => {
    const add = composerMenu("add", "chat", [], ALL).map((item) => item.id);
    const tools = composerMenu("tools", "chat", [], ALL).map((item) => item.id);
    expect(add.filter((id) => tools.includes(id))).toEqual([]);
  });

  it("orders by declared priority, not by declaration order", () => {
    const items = composerMenu("add", "chat", [], ALL);
    const priorities = items.map((item) => item.priority);
    expect([...priorities].sort((left, right) => left - right)).toEqual(priorities);
  });
});

describe("a capability the runtime has turned off", () => {
  const off = makeGate({ capability: "web_fetch", state: "disabled", allowed_transitions: ["enabled_policy_gated"] });
  const on = makeGate({ capability: "web_fetch", state: "enabled_runtime" });

  it("stays listed, with the reason and the way to change it", () => {
    // Hiding it teaches the owner that Raiker cannot do the thing at all, which
    // is both worse and less true than "this is off, here is the switch".
    const items = composerMenu("tools", "chat", [off], ALL);
    const search = items.find((item) => item.id === "web-search");
    expect(search?.blocked?.reason).toBe("Turned off in Permissions");
    expect(search?.blocked?.href).toBe("#/capabilities");
  });

  it("is unblocked once the gate is on", () => {
    const items = composerMenu("tools", "chat", [on], ALL);
    expect(items.find((item) => item.id === "web-search")?.blocked).toBeNull();
  });

  it("is offered when no gate has been reported at all", () => {
    // A status read that did not answer is not evidence the capability is off,
    // and the runtime judges the action when it is actually invoked — on better
    // evidence than this menu will ever have.
    const items = composerMenu("tools", "chat", [], ALL);
    expect(items.find((item) => item.id === "web-search")?.blocked).toBeNull();
  });

  it("is dropped when this build has no executor for it", () => {
    // Deferred is not "off": there is nothing to turn on, so a route that
    // promised to turn it on would be the dead end rule 1 exists to prevent.
    const deferred = makeGate({
      capability: "web_fetch",
      state: "disabled",
      allowed_transitions: [],
      blocked_reason_code: "no_executor",
    });
    const items = composerMenu("tools", "chat", [deferred], ALL);
    expect(items.find((item) => item.id === "web-search")).toBeUndefined();
  });
});

describe("the three Work modes each get a composer", () => {
  it.each(["chat", "build", "design"] as ComposerSurface[])(
    "offers %s something to add",
    (surface) => {
      expect(composerMenu("add", surface, [], ALL).length).toBeGreaterThan(0);
    },
  );
});
