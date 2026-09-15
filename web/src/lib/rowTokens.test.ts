import { describe, expect, it } from "vitest";
import type { SkillConformance, SkillView } from "./apiTypes";
import {
  approvalCandidates,
  ROW_TOKEN_BUDGET,
  rowTokens,
  sessionCandidates,
  skillCandidates,
} from "./rowTokens";

function skill(partial: Partial<SkillView> = {}): SkillView {
  return {
    skill_id: "skl_1",
    name: "Release notes",
    description: "Writes release notes.",
    active: true,
    version: null,
    command_trigger: null,
    ...partial,
  } as SkillView;
}

function conformance(severity: "error" | "warning" | null): SkillConformance {
  return {
    conformant: severity !== "error",
    spec_url: "https://agentskills.io/specification",
    findings:
      severity === null ? [] : [{ severity, code: "x", message: "m", field: "name" }],
    license: "MIT",
    compatibility: "portable",
    metadata: {},
    refused_allowed_tools: [],
  };
}

describe("the token budget for a repeated row (the badge budget)", () => {
  it("spends a badge only on a fact that is not in its ordinary state", () => {
    const { badges, facts } = rowTokens([
      { label: "active", variant: null },
      { label: "v2", variant: null },
    ]);
    expect(badges).toEqual([]);
    expect(facts).toEqual(["active", "v2"]);
  });

  it("never draws more badges than the budget, whatever the row knows", () => {
    const { badges } = rowTokens([
      { label: "one", variant: "blocked" },
      { label: "two", variant: "needs-approval" },
      { label: "three", variant: "stopped" },
      { label: "four", variant: "active" },
    ]);
    expect(badges).toHaveLength(ROW_TOKEN_BUDGET);
  });

  it("gives the badges to what needs acting on, not to what came first", () => {
    const { badges } = rowTokens([
      { label: "running", variant: "active" },
      { label: "queued", variant: "idle" },
      { label: "denied", variant: "stopped", attention: true },
    ]);
    expect(badges[0].label).toBe("denied");
  });

  it("keeps saying everything the row said: nothing is dropped, only reweighted", () => {
    const { badges, facts } = rowTokens([
      { label: "critical", variant: "blocked", attention: true },
      { label: "pending", variant: "needs-approval" },
      { label: "expires in an hour", variant: "idle" },
      { label: "asked by the scheduler", variant: null },
    ]);
    expect(badges.map((b) => b.label)).toEqual(["critical", "pending"]);
    expect(facts).toEqual(["expires in an hour", "asked by the scheduler"]);
  });
});

describe("what each repeated row spends its budget on (the exception-led rule)", () => {
  it("reads a switched-on skill as metadata and a switched-off one as a state", () => {
    expect(rowTokens(skillCandidates(skill({ active: true }), false)).badges).toEqual([]);
    expect(rowTokens(skillCandidates(skill({ active: false }), false)).badges).toEqual([
      { label: "inactive", variant: "idle" },
    ]);
  });

  it("does not let a command trigger or a version look like a status", () => {
    const { badges, facts } = rowTokens(
      skillCandidates(skill({ version: "1.2", command_trigger: "notes" }), true),
    );
    expect(badges).toEqual([]);
    expect(facts).toEqual(["active", "v1.2", "/notes", "from plugin"]);
  });

  it("escalates a skill that would not validate, ahead of everything else on the row", () => {
    const { badges } = rowTokens(
      skillCandidates(skill({ active: false, conformance: conformance("error") }), false),
    );
    expect(badges[0].variant).toBe("needs-approval");
    expect(badges).toHaveLength(2);
  });

  it("leaves a conformant skill's measurement as a quiet fact", () => {
    const { badges } = rowTokens(
      skillCandidates(skill({ conformance: conformance(null) }), false),
    );
    expect(badges).toEqual([]);
  });

  it("finds the running session in a list of idle ones", () => {
    expect(rowTokens(sessionCandidates({ status: "active", archived: false })).badges).toEqual([
      { label: "active", variant: "active" },
    ]);
    const idle = rowTokens(sessionCandidates({ status: "idle", archived: true }));
    expect(idle.badges).toEqual([]);
    expect(idle.facts).toEqual(["idle", "archived"]);
  });

  it("tones an approval's risk only when the risk is elevated", () => {
    const routine = rowTokens(
      approvalCandidates({ status: "pending", risk_level: "low", is_expired: false }),
    );
    expect(routine.badges).toEqual([{ label: "pending", variant: "needs-approval" }]);
    expect(routine.facts).toEqual(["low"]);

    const dangerous = rowTokens(
      approvalCandidates({ status: "pending", risk_level: "critical", is_expired: false }),
    );
    expect(dangerous.badges.map((b) => b.label)).toEqual(["critical", "pending"]);
  });

  it("says expired rather than the status an expired decision still carries", () => {
    const { badges } = rowTokens(
      approvalCandidates({ status: "pending", risk_level: "low", is_expired: true }),
    );
    expect(badges).toEqual([{ label: "expired", variant: "stopped" }]);
  });
});
