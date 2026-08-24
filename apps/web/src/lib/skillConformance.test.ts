import { describe, expect, it } from "vitest";
import type { SkillConformance, SkillConformanceFinding } from "./apiTypes";
import {
  conformanceBadge,
  conformanceLabel,
  conformanceSummary,
  errors,
  needsAttention,
  refusals,
  warnings,
} from "./skillConformance";

function report(findings: SkillConformanceFinding[] = []): SkillConformance {
  return {
    conformant: !findings.some((f) => f.severity === "error"),
    spec_url: "https://agentskills.io/specification",
    findings,
    license: "",
    compatibility: "",
    metadata: {},
    refused_allowed_tools: [],
  };
}

const finding = (severity: SkillConformanceFinding["severity"]): SkillConformanceFinding => ({
  field: "name",
  code: "x",
  severity,
  message: "m",
});

describe("skill conformance presentation", () => {
  it("separates the three kinds of finding", () => {
    const r = report([finding("error"), finding("warning"), finding("refused")]);
    expect(errors(r)).toHaveLength(1);
    expect(warnings(r)).toHaveLength(1);
    expect(refusals(r)).toHaveLength(1);
  });

  it("reads a clean skill as matching the standard", () => {
    expect(conformanceLabel(report())).toBe("standard");
    expect(conformanceSummary(report())).toMatch(/should install in any tool/i);
  });

  it("keeps conformance a quiet tag unless there is something to act on", () => {
    // Found in live testing: a `Badge` in every case put two `►` pills on every
    // skill row — "switched on" and "matches the standard" — which look
    // identical and mean nothing alike. Conformance is a property of the
    // document, not a lifecycle state.
    expect(needsAttention(report())).toBe(false);
    expect(needsAttention(report([finding("warning")]))).toBe(false);
    expect(needsAttention(report([finding("refused")]))).toBe(false);
    expect(needsAttention(report([finding("error")]))).toBe(true);
    expect(conformanceBadge(report([finding("error")]))).toBe("needs-approval");
  });

  it("counts portability issues rather than announcing a failure", () => {
    // The skill works here. A label of "invalid" would be false, and would send
    // an owner to fix something that is not broken for them.
    const r = report([finding("error"), finding("error")]);
    expect(conformanceLabel(r)).toBe("2 portability issues");
    expect(conformanceSummary(r)).toMatch(/works in Raiker and may be refused/i);
  });

  it("treats a refusal as Raiker's choice, not the author's mistake", () => {
    // `allowed-tools` is read and deliberately not honoured. The document is
    // valid and installs elsewhere, so the row must not read as non-conformant.
    const r = report([finding("refused")]);
    expect(needsAttention(r)).toBe(false);
    expect(conformanceLabel(r)).toBe("standard");
  });

  it("distinguishes portable-with-notes from a portability failure", () => {
    const r = report([finding("warning")]);
    expect(needsAttention(r)).toBe(false);
    expect(conformanceLabel(r)).toBe("portable, with notes");
    expect(conformanceSummary(r)).toMatch(/strict reader may drop/i);
  });
});
