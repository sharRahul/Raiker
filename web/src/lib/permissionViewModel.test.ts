/*
 * NEW-PERM-02 — one effective permission model, and the two races it has to
 * survive: a refresh that left before a change was confirmed, and a bulk
 * request that is refused partway through.
 *
 * These are pure functions on purpose. The defect was that the merge lived
 * inside a 800-line view and only one of four presentations used it, so the
 * rule is here, once, where it can be stated as cases.
 */
import { describe, expect, it } from "vitest";
import { makeGate } from "./test-helpers";
import {
  bulkOutcome,
  confirmMode,
  confirmedModeValues,
  effectiveGates,
  survivingModes,
} from "./permissionViewModel";

describe("the effective permission model", () => {
  it("renders the confirmed mode, not the one the last read carried", () => {
    const gates = [
      makeGate({ capability: "shell_execution", decision_mode: "auto" }),
      makeGate({ capability: "web_fetch", decision_mode: "ask" }),
    ];
    const confirmed = confirmMode({}, "shell_execution", "deny", 1);
    const merged = effectiveGates(gates, confirmed);

    expect(merged.map((gate) => gate.decision_mode)).toEqual(["deny", "ask"]);
    // The read stays authoritative about everything else on the gate …
    expect(merged[0].capability).toBe("shell_execution");
    // … and the untouched gate is the same object, so nothing re-renders for a
    // change that did not happen to it.
    expect(merged[1]).toBe(gates[1]);
  });

  it("does not invent a row for a capability this build does not list", () => {
    const confirmed = confirmMode({}, "not_in_this_build", "deny", 1);
    expect(effectiveGates([makeGate({ capability: "web_fetch" })], confirmed)).toHaveLength(1);
  });

  it("keeps a confirmation newer than the read that is answering", () => {
    // The sequence the defect takes: press Refresh, change a mode before it
    // comes back, and the response carries the value the owner just replaced.
    let confirmed = confirmMode({}, "shell_execution", "ask", 1);
    const readStartedAt = 1;
    confirmed = confirmMode(confirmed, "web_fetch", "deny", 2);

    const surviving = survivingModes(confirmed, readStartedAt);
    // Already reflected by the response, so redundant and dropped …
    expect(surviving.shell_execution).toBeUndefined();
    // … and the one confirmed while the response was in flight is kept.
    expect(surviving.web_fetch.mode).toBe("deny");
  });

  it("hands a control just the modes", () => {
    const confirmed = confirmMode(confirmMode({}, "a", "deny", 1), "b", "auto", 2);
    expect(confirmedModeValues(confirmed)).toEqual({ a: "deny", b: "auto" });
  });
});

describe("what a bulk change reports", () => {
  it("says nothing when nothing was attempted", () => {
    expect(bulkOutcome([], [])).toBeNull();
  });

  it("counts a clean run", () => {
    expect(bulkOutcome(["a"], [])).toEqual({ kind: "ok", text: "1 capability changed." });
    expect(bulkOutcome(["a", "b"], [])?.text).toBe("2 capabilities changed.");
  });

  it("does not imply the changes that succeeded were rolled back", () => {
    // The defect: the loop stopped at the first refusal and said "The bulk
    // change was rejected", while the capabilities already changed stayed
    // changed. Both halves are named.
    const outcome = bulkOutcome(["shell_execution"], ["web_fetch"])!;
    expect(outcome.kind).toBe("error");
    expect(outcome.text).toMatch(/^1 changed;/);
    expect(outcome.text).toContain("Web fetch");
    expect(outcome.text).toMatch(/left as it was/);
  });

  it("says so plainly when every one was refused", () => {
    const outcome = bulkOutcome([], ["web_fetch", "shell_execution"])!;
    expect(outcome.kind).toBe("error");
    expect(outcome.text).toMatch(/^No capability was changed/);
    expect(outcome.text).toContain("Shell commands");
  });
});
