/**
 * QUI-P05 — what the Raiker Safety card says, in the order the plan sets.
 *
 *   1. What will happen
 *   2. Why it needs you
 *   3. Which account, service or recipient is affected
 *   4. What data is involved
 *   5. Whether it can be undone
 *   6. The safer alternative, when there is one
 *
 * Every row is read off the proposal itself or the capability's own server
 * classification, and a row with nothing true to say is left out rather than
 * filled with a guess (the rules of `approvalConsequence.ts`). Nothing here
 * authorises anything: the runtime decides what a decision permits.
 */
import { consequenceFacts, destinationHost, type ConsequenceFact } from "./approvalConsequence";
import { capabilityLabel } from "./capabilityModel";

export interface SafetyRow {
  /** Stable key, also the row's test id. */
  key: "what" | "why" | "affects" | "data" | "undo" | "alternative";
  label: string;
  value: string;
}

/** The labels the facts in `consequenceFacts` use for what an action reaches. */
const AFFECTS = new Set([
  "Account",
  "Path",
  "Paths",
  "Destination",
  "Host",
  "Repository",
  "Branch",
  "Sent to",
  "Server",
]);

/** The undo row, from the capability's side-effect class (BUG-293). */
const UNDO: Record<string, string> = {
  reversible: "Can be undone afterwards.",
  external: "Can't be taken back once it leaves this machine.",
  destructive: "Can't be undone.",
  critical: "Changes what Raiker may do next.",
};

function countLines(text: string): number {
  return text === "" ? 0 : text.replace(/\n$/, "").split("\n").length;
}

/** What content the action carries, in words, or null when it carries none. */
export function dataInvolved(args: Record<string, unknown> | null | undefined): string | null {
  if (!args) return null;
  const patch = args.patch;
  if (typeof patch === "string" && patch.trim() !== "") {
    const files = new Set(
      [...patch.matchAll(/^\+\+\+ (?:b\/)?(.+)$/gm)].map((match) => match[1].trim()),
    );
    const changed = patch.split("\n").filter((line) => /^[+-](?![+-]{2} )/.test(line)).length;
    const fileWord = files.size === 1 ? "1 file" : `${files.size} files`;
    return `A change to ${files.size > 0 ? fileWord : "files"}: ${changed} line${changed === 1 ? "" : "s"} added or removed.`;
  }
  for (const key of ["text", "content"]) {
    const value = args[key];
    if (typeof value === "string") {
      const lines = countLines(value);
      return `${lines} line${lines === 1 ? "" : "s"} of text.`;
    }
  }
  for (const key of ["body", "message", "arguments", "payload"]) {
    if (key in args && args[key] !== null && args[key] !== undefined && args[key] !== "") {
      return "The request's contents, shown in full in Approvals.";
    }
  }
  return null;
}

/** The facts naming what this action reaches. */
export function affectedFacts(args: Record<string, unknown> | null | undefined): ConsequenceFact[] {
  const facts = consequenceFacts(args).filter((fact) => AFFECTS.has(fact.label));
  const host = destinationHost(args);
  if (host && !facts.some((fact) => fact.value === host)) facts.push({ label: "Host", value: host });
  return facts;
}

export interface SafetyInput {
  toolTitle: string;
  /** The runtime's own sentence about the proposal, when it wrote one. */
  message?: string;
  expectedEffect: string;
  capability: string | null;
  sideEffect: string | null;
  /** The policy decision's reasons, which say who asked for the decision. */
  reasons?: readonly string[];
  arguments: Record<string, unknown> | null | undefined;
  /** The decision can be narrowed or edited in Approvals (a patch or file change). */
  changeable: boolean;
}

/** Who asked for this decision: the conversation, a hook, or the owner's permissions. */
export function whyItNeedsYou(reasons: readonly string[], capability: string | null): string | null {
  if (reasons.includes("turn_posture_requires_approval")) {
    return "This conversation asks before every change.";
  }
  if (reasons.includes("hook_requested_approval")) {
    return "A hook you set up asked to check this first.";
  }
  if (capability) return `Your permissions ask before ${capabilityLabel(capability).toLowerCase()}.`;
  return null;
}

export function safetyRows(input: SafetyInput): SafetyRow[] {
  const rows: SafetyRow[] = [];
  // The runtime's expected effect says what approving does; its message is a
  // generic "approval required" line, used only when no effect was stated.
  const effect = input.expectedEffect.trim();
  const said = (input.message ?? "").trim();
  rows.push({
    key: "what",
    label: "What will happen",
    value: effect !== "" ? `${input.toolTitle}: ${effect}` : said !== "" ? said : `${input.toolTitle}.`,
  });
  const why = whyItNeedsYou(input.reasons ?? [], input.capability);
  if (why) rows.push({ key: "why", label: "Why it needs you", value: why });
  const affects = affectedFacts(input.arguments);
  if (affects.length > 0) {
    rows.push({
      key: "affects",
      label: "Affects",
      value: affects.map((fact) => fact.value).join(" · "),
    });
  }
  const data = dataInvolved(input.arguments);
  if (data) rows.push({ key: "data", label: "Data involved", value: data });
  const undo = input.sideEffect ? UNDO[input.sideEffect] : undefined;
  if (undo) rows.push({ key: "undo", label: "Undo", value: undo });
  if (input.changeable) {
    rows.push({
      key: "alternative",
      label: "Safer alternative",
      value: "Accept only part of the change, or edit it first: Change.",
    });
  }
  return rows;
}
