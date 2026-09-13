import { describe, expect, it } from "vitest";
import type { CapabilityGate } from "./apiTypes";
import {
  BEHAVIOUR_COPY,
  CANNOT_CHANGE_HERE,
  COMMON_PERMISSIONS,
  UNKNOWN_BEHAVIOUR,
  behaviourCopy,
  commonGates,
  permissionAttention,
  rowSummary,
} from "./permissionLanguage";
import { capabilityLabel, DECISION_MODES } from "./capabilityModel";

function gate(partial: Partial<CapabilityGate> = {}): CapabilityGate {
  return {
    capability: "shell_exec",
    phase: 3,
    state: "enabled_runtime",
    default_state: "disabled",
    source: "owner",
    runtime_enabled: true,
    allowed_transitions: ["disabled"],
    can_current_principal_change: true,
    blocked_reason_code: null,
    readiness: {},
    decision_mode: "ask",
    ...partial,
  } as CapabilityGate;
}

describe("the two questions Permissions asks (P1 — Permissions UX)", () => {
  it("gives every decision mode an owner-facing word", () => {
    // The store keeps `deny`; the owner reads "Never". A mode with no entry
    // here would render as a backend identifier on a settings page.
    for (const mode of DECISION_MODES) {
      expect(BEHAVIOUR_COPY[mode], `${mode} has no owner wording`).toBeTruthy();
      expect(BEHAVIOUR_COPY[mode].label).not.toBe(mode);
      expect(BEHAVIOUR_COPY[mode].hint.length).toBeGreaterThan(20);
    }
    expect(BEHAVIOUR_COPY.deny.label).toBe("Never");
    expect(BEHAVIOUR_COPY.auto.label).toBe("Automatic");
  });

  it("makes On + Never readable instead of contradictory", () => {
    // The review's own question. The answer is in the hint: the capability is
    // available and every attempt to use it is refused.
    expect(rowSummary(gate({ decision_mode: "deny" }), true)).toBe("On · Never");
    expect(BEHAVIOUR_COPY.deny.hint).toMatch(/available/i);
  });

  it("says both facts on a row that is still closed", () => {
    expect(rowSummary(gate({ decision_mode: "ask" }), true)).toBe("On · Ask me");
    expect(rowSummary(gate({ decision_mode: "allow" }), false)).toBe("Off · Allow");
  });

  it("names capabilities the registry actually ships", () => {
    // Found live: the first list used plausible-sounding names — `file_write`,
    // `shell_exec`, `git_push` — and the registry calls them
    // `file_write_execution`, `shell_execution`, `git_push_execution`. Nothing
    // failed; the section simply rendered one row and looked finished.
    for (const name of COMMON_PERMISSIONS) {
      expect(capabilityLabel(name), `${name} is not in the capability registry`).not.toBe(name);
    }
  });

  it("lists the common permissions that this build actually has", () => {
    const installed = [
      gate({ capability: "shell_execution" }),
      gate({ capability: "file_write_execution" }),
    ];
    expect(commonGates(installed).map((entry) => entry.capability)).toEqual([
      "file_write_execution",
      "shell_execution",
    ]);
    // Order follows the list, not the registry's order …
    expect(COMMON_PERMISSIONS.indexOf("web_fetch")).toBe(0);
    // … and a capability this build does not ship is simply absent.
    expect(commonGates([])).toEqual([]);
  });

  it("does not read an unrecognised mode as an answer it was never given", () => {
    // NEW-PERM-03 — a missing or future mode used to drop the behaviour half of
    // the row, so the summary quietly stopped answering its own second question.
    expect(rowSummary(gate({ decision_mode: "supervise" }), true)).toBe("On · Unknown");
    expect(rowSummary(gate({ decision_mode: "" }), false)).toBe("Off · Unknown");
    expect(behaviourCopy("supervise")).toBe(UNKNOWN_BEHAVIOUR);
    expect(behaviourCopy("deny")).toBe(BEHAVIOUR_COPY.deny);
    expect(UNKNOWN_BEHAVIOUR.hint).toMatch(/refresh/i);
  });

  it("calls attention only what an owner can act on", () => {
    // A capability at its default is not attention. A page that calls
    // everything attention has said nothing.
    expect(permissionAttention([gate({ decision_mode: "ask" })])).toEqual([]);
    const automatic = permissionAttention([gate({ decision_mode: "auto" })]);
    expect(automatic).toHaveLength(1);
    expect(automatic[0].reason).toMatch(/without asking you/);
    // And nothing else: `runtime_enabled` is derived from the gate's own state
    // in the backend, so "switched on but not running" cannot occur, and a rule
    // that can never fire only looks like safety.
    expect(permissionAttention([gate({ state: "enabled_runtime" })])).toEqual([]);
  });

  it("does not call a missing executor an owner's decision", () => {
    // Found live: the first version counted "no route yet" and "governed
    // elsewhere", which put fifteen rows under *needs your attention* with no
    // action available for any of them. Those are facts about what this build
    // ships, not decisions.
    const deferred = gate({
      capability: "calendar_runtime",
      state: "disabled",
      blocked_reason_code: "no_executor",
      runtime_enabled: false,
      decision_mode: "ask",
    });
    expect(permissionAttention([deferred])).toEqual([]);
  });

  it("does not tell an owner that an unavailable capability is running", () => {
    /*
     * NEW-PERM-03 — configured *Automatic* is a fact about the account. It is
     * not evidence that anything is running: an executor whose readiness the
     * backend reports as unmet, or a capability switched off, cannot act at
     * all, and an alarm about work that cannot happen is worse than no alarm.
     */
    const running = permissionAttention([
      gate({ decision_mode: "auto", state: "enabled_runtime", readiness: { provider: true } }),
    ]);
    expect(running[0].reason).toBe("runs automatically, without asking you");

    const notReady = permissionAttention([
      gate({ decision_mode: "auto", state: "enabled_runtime", readiness: { provider: false } }),
    ]);
    expect(notReady[0].reason).toMatch(/not available right now/);

    const switchedOff = permissionAttention([
      gate({ decision_mode: "auto", state: "disabled", allowed_transitions: ["enabled_runtime"] }),
    ]);
    expect(switchedOff[0].reason).toMatch(/not available right now/);
    // Still listed either way: the setting is real and the owner may want it
    // changed. What moves is the sentence, not whether the row exists.
    expect(notReady).toHaveLength(1);
  });

  it("explains an unchangeable setting as a fact about the account", () => {
    expect(CANNOT_CHANGE_HERE).not.toMatch(/principal/i);
    expect(CANNOT_CHANGE_HERE).toMatch(/account/i);
  });
});
