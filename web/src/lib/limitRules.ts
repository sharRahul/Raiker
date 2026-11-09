/**
 * QUI-P03, QUI-P05, QUI-P09 — Allow with limits, as the owner sees and edits it.
 *
 * The runtime validates every limit (`grant_limits.py`) and derives a rule's
 * shape from the approval itself; this only turns the form into the request
 * and the runtime's reason codes into sentences.
 */
import type { LimitRuleLimits } from "./generated/apiContract";

export type LimitScope = "conversation" | "project" | "future";

export type LimitForm = {
  scope: LimitScope;
  /** One target per line or comma: recipients, sites, repositories, channels. */
  targets: string;
  maxUses: number;
  expiresHours: number;
  attachments: boolean;
  sensitiveAsks: boolean;
};

export const SCOPE_LABELS: Record<LimitScope, string> = {
  conversation: "This conversation",
  project: "This project",
  future: "Future work",
};

export const EXPIRY_CHOICES: ReadonlyArray<{ hours: number; label: string }> = [
  { hours: 1, label: "1 hour" },
  { hours: 8, label: "8 hours" },
  { hours: 24, label: "1 day" },
  { hours: 168, label: "1 week" },
];

export function formFromLimits(limits: LimitRuleLimits): LimitForm {
  return {
    scope: limits.scope,
    targets: limits.targets.join(", "),
    maxUses: limits.max_uses,
    expiresHours: limits.expires_hours,
    attachments: limits.attachments,
    sensitiveAsks: limits.sensitive_asks,
  };
}

export function splitTargets(text: string): string[] {
  return text
    .split(/[\n,;]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function limitsFromForm(form: LimitForm): LimitRuleLimits {
  return {
    scope: form.scope,
    targets: splitTargets(form.targets),
    max_uses: Math.round(form.maxUses),
    expires_hours: Math.round(form.expiresHours),
    attachments: form.attachments,
    sensitive_asks: form.sensitiveAsks,
  };
}

/** What the form can say before asking the server: the plan's required limits. */
export function formProblem(form: LimitForm): string | null {
  if (!Number.isInteger(form.maxUses) || form.maxUses < 1 || form.maxUses > 100) {
    return "Choose how many times, from 1 to 100.";
  }
  if (form.scope !== "conversation" && splitTargets(form.targets).length === 0) {
    return "Beyond this conversation, name who or where it may reach.";
  }
  return null;
}

const REASONS: Record<string, string> = {
  grant_limit_needs_targets: "Beyond this conversation, name who or where it may reach.",
  grant_limit_target_invalid: "One of the recipients, sites or repositories is not one Raiker can check.",
  grant_limit_targets_invalid: "That is more than 20 recipients or sites.",
  grant_limit_uses_invalid: "Choose how many times, from 1 to 100.",
  grant_limit_expiry_invalid: "Choose an expiry from 1 hour to 1 week.",
  grant_limit_needs_project: "This conversation is not in a project.",
  grant_limit_needs_conversation: "This rule needs the conversation it was allowed in.",
  grant_target_is_critical: "This kind of action is always decided by you, every time.",
  approval_is_a_question: "A question is answered, not allowed.",
};

export function limitRuleReason(code: string | null | undefined): string {
  return (code && REASONS[code]) || "The rule was not kept. Nothing was allowed beyond this once.";
}

/** The fields every grant list reads; a rule adds its limits in words. */
export type GrantLike = {
  tool_name: string;
  scope_pattern: string;
  risk_ceiling: string;
  use_count: number;
  limits_words?: string[] | null;
};

/**
 * One line for a standing grant or an Allow-with-limits rule, the same on every
 * surface that lists them. A rule says its limits; an older grant its pattern.
 */
export function grantSummary(grant: GrantLike): string {
  const words = grant.limits_words ?? [];
  if (words.length > 0) return words.join(" · ");
  const scope = grant.scope_pattern && grant.scope_pattern !== "*" ? `On ${grant.scope_pattern} · ` : "";
  return `${scope}up to ${grant.risk_ceiling} risk · used ${grant.use_count} ${grant.use_count === 1 ? "time" : "times"}`;
}
