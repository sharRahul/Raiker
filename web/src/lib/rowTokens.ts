import type { SkillView } from "./apiTypes";
import { conformanceBadge, conformanceLabel, needsAttention } from "./skillConformance";
import { approvalBadge } from "./statusMaps";
import type { BadgeVariant } from "./types";

/*
 * VIS2-13 / VIS2-18 — the token budget for a repeated row.
 *
 * A list of skills, sessions or approvals is read by scanning it, and scanning
 * only works when the eye can tell *this row is different* from *this row is
 * ordinary*. Every extra pill on every row spends that difference: a skill row
 * carried a lifecycle badge, a `/command` badge and a conformance badge at
 * once, three shapes of the same weight saying three unrelated things, and the
 * one that meant "this needs you" looked exactly like the two that did not.
 *
 * So one rule, applied everywhere a row repeats:
 *
 *   needs action    a badge, with tone — at most {@link ROW_TOKEN_BUDGET} of
 *                   them, attention first
 *   worth knowing   plain metadata on the same row
 *   detail          not on the row at all
 *
 * A candidate whose `variant` is `null` is *the ordinary state of that fact* —
 * a skill that is switched on, an approval at routine risk — and becomes plain
 * metadata rather than a coloured badge. That is the whole of VIS2-13's
 * "healthy/default facts should usually be plain metadata": it is decided here,
 * once, instead of re-argued in each view's markup.
 */

/** Attention first, then the rest; the budget is two per row. */
export const ROW_TOKEN_BUDGET = 2;

export interface RowCandidate {
  /** What this fact says, in the owner's words. */
  label: string;
  /**
   * The badge to spend on it, or `null` when this is the fact's ordinary state
   * and it should read as metadata instead.
   */
  variant: BadgeVariant | null;
  /** True when the state is something the owner may need to act on. */
  attention?: boolean;
}

export interface RowToken {
  label: string;
  variant: BadgeVariant;
}

export interface RowTokens {
  /** The badges this row may draw, attention first, never more than the budget. */
  badges: RowToken[];
  /** Everything else the row still says, as plain metadata, in order. */
  facts: string[];
}

/**
 * Apply the budget to one row's candidates.
 *
 * Nothing is dropped: a fact that does not earn a badge — because it is
 * ordinary, or because the budget is already spent — stays on the row as text.
 * The row keeps saying everything it said before; only the weight moves.
 */
export function rowTokens(candidates: RowCandidate[]): RowTokens {
  const ordered = candidates
    .map((candidate, index) => ({ candidate, index }))
    .sort((a, b) => {
      const attention = Number(b.candidate.attention ?? false) - Number(a.candidate.attention ?? false);
      return attention !== 0 ? attention : a.index - b.index;
    });

  const badges: RowToken[] = [];
  const promoted = new Set<number>();
  for (const { candidate, index } of ordered) {
    if (candidate.variant === null || badges.length >= ROW_TOKEN_BUDGET) continue;
    badges.push({ label: candidate.label, variant: candidate.variant });
    promoted.add(index);
  }

  const facts = candidates
    .filter((_, index) => !promoted.has(index))
    .map((candidate) => candidate.label);

  return { badges, facts };
}

/**
 * A skill row.
 *
 * Switched on is how a skill sits when nothing is wrong with it, so it is
 * metadata; switched off is the state an owner goes looking for. The command
 * trigger and the version are facts about the document, and conformance
 * escalates only when there is something to fix — the judgement
 * `skillConformance.ts` already makes.
 */
export function skillCandidates(skill: SkillView, fromPlugin: boolean): RowCandidate[] {
  const candidates: RowCandidate[] = [
    skill.active
      ? { label: "active", variant: null }
      : { label: "inactive", variant: "idle" },
  ];
  if (skill.conformance) {
    const attention = needsAttention(skill.conformance);
    candidates.push({
      label: conformanceLabel(skill.conformance),
      variant: attention ? conformanceBadge(skill.conformance) : null,
      attention,
    });
  }
  if (skill.version) candidates.push({ label: `v${skill.version}`, variant: null });
  if (skill.command_trigger) candidates.push({ label: `/${skill.command_trigger}`, variant: null });
  if (fromPlugin) candidates.push({ label: "from plugin", variant: null });
  return candidates;
}

/**
 * A session row.
 *
 * A session that is running is the one an owner wants to find in a long list;
 * one that is idle is every other row on the page. Archived is reversible
 * organisation, not a state to act on.
 */
export function sessionCandidates(session: { status: string; archived: boolean }): RowCandidate[] {
  const running = session.status === "active";
  const candidates: RowCandidate[] = [
    { label: session.status, variant: running ? "active" : null },
  ];
  if (session.archived) candidates.push({ label: "archived", variant: null });
  return candidates;
}

/** Risk levels that are an exception rather than the ordinary shape of a queue. */
export const ELEVATED_RISK = new Set(["high", "critical"]);

/**
 * True when a decision's risk level is worth a badge.
 *
 * The approvals queue is a table, so the column headings already say which fact
 * each cell holds; what the cell decides is *weight*. Every row was toned —
 * `low` and `medium` in an info colour, `high` and `critical` in a danger one —
 * which made the queue uniformly loud and left the genuinely dangerous row
 * looking like all the others. Routine risk is metadata; elevated risk is the
 * exception this returns true for.
 */
export function elevatedRisk(risk: string): boolean {
  return ELEVATED_RISK.has(risk);
}

/**
 * An approval, as a flat row: risk first when it is elevated, then the
 * decision's own status, which `statusMaps.ts` tones as it does everywhere else
 * the same statuses are reported.
 */
export function approvalCandidates(approval: {
  status: string;
  risk_level: string;
  is_expired: boolean;
}): RowCandidate[] {
  const state = approval.is_expired ? "expired" : approval.status;
  const elevated = elevatedRisk(approval.risk_level);
  return [
    { label: approval.risk_level, variant: elevated ? "blocked" : null, attention: elevated },
    { label: state, variant: approvalBadge(state) },
  ];
}
