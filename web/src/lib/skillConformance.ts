import type { SkillConformance, SkillConformanceFinding, SkillView } from "./apiTypes";
import type { BadgeVariant } from "./types";

// ADD-21 — `SKILL.md` is an open standard now (https://agentskills.io), and the
// question an owner actually has about an installed skill is "will this work
// anywhere else?". The backend measures and reports; it never refuses, so a
// skill that installs today keeps installing. These helpers decide what the card
// says about the answer.

/** True when the payload carried a measurement at all. */
export function hasConformance(skill: SkillView): boolean {
  return skill.conformance !== undefined;
}

/** Findings that mean the skill would not validate under the standard. */
export function errors(conformance: SkillConformance): SkillConformanceFinding[] {
  return conformance.findings.filter((f) => f.severity === "error");
}

/** Findings that are portable-but-untidy: a strict reader may drop the field. */
export function warnings(conformance: SkillConformance): SkillConformanceFinding[] {
  return conformance.findings.filter((f) => f.severity === "warning");
}

/**
 * Fields Raiker read, understood, and declined to act on. Today that is only
 * `allowed-tools`: a skill cannot pre-approve its own tools here.
 */
export function refusals(conformance: SkillConformance): SkillConformanceFinding[] {
  return conformance.findings.filter((f) => f.severity === "refused");
}

/**
 * True when the row should escalate to a real status badge rather than a quiet
 * property tag.
 *
 * Found in live testing: rendering conformance as a `Badge` in every case put
 * two `►` pills side by side on every skill row — one meaning "switched on",
 * one meaning "matches the standard" — which look identical and mean nothing
 * alike. Conformance is a *property* of the document, not a lifecycle state, so
 * it reads as a quiet tag unless there is something to act on.
 */
export function needsAttention(conformance: SkillConformance): boolean {
  return errors(conformance).length > 0;
}

/**
 * The badge for a skill whose portability the owner may want to act on. Only
 * consulted when {@link needsAttention} is true.
 *
 * A refusal is deliberately *not* a failure — the document is valid and Raiker
 * simply does not honour one of its requests, so marking the skill
 * non-conformant for it would blame the author for Raiker's own governance
 * choice.
 */
export function conformanceBadge(conformance: SkillConformance): BadgeVariant {
  return needsAttention(conformance) ? "needs-approval" : "idle";
}

/** The short label beside that badge. */
export function conformanceLabel(conformance: SkillConformance): string {
  const errorCount = errors(conformance).length;
  if (errorCount > 0) return errorCount === 1 ? "1 portability issue" : `${errorCount} portability issues`;
  if (warnings(conformance).length > 0) return "portable, with notes";
  return "standard";
}

/**
 * One sentence under the badge. It answers the owner's question rather than
 * restating the count, and says which direction the incompatibility runs — a
 * skill can be perfectly good here and still be refused by a stricter reader.
 */
export function conformanceSummary(conformance: SkillConformance): string {
  if (errors(conformance).length > 0) {
    return "This skill works in Raiker and may be refused by other tools that read the Agent Skills standard.";
  }
  if (warnings(conformance).length > 0) {
    return "This skill matches the Agent Skills standard. A strict reader may drop the fields noted below.";
  }
  return "This skill matches the Agent Skills standard and should install in any tool that reads it.";
}
