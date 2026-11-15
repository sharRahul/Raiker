/**
 * QUI-C07 — Chat's context panel.
 *
 * Closed by default. Its tabs are Context (files in use), Memories (what the
 * turns were given from Memory), Plan, Sources and Activity, and a tab is drawn
 * only when it has something in it: an empty tab is a report that there is
 * nothing to report.
 */
import type { AgentPlan, RecalledMemory, TurnSourceView } from "./apiTypes";
import type { ToolCallRow } from "./chatPresentation";
import type { ComposerAttachment } from "./composerAttachments.svelte";

export type ContextTab = "context" | "memories" | "plan" | "sources" | "activity";

export const CONTEXT_TAB_LABELS: Record<ContextTab, string> = {
  context: "Context",
  memories: "Memories",
  plan: "Plan",
  sources: "Sources",
  activity: "Activity",
};

export interface ContextContents {
  files: readonly ComposerAttachment[];
  memories?: readonly RecalledMemory[];
  plan: AgentPlan | null;
  sources: readonly TurnSourceView[];
  activity: readonly ToolCallRow[];
}

/** The tabs worth drawing, in their fixed order. */
export function contextTabs(contents: ContextContents): ContextTab[] {
  const tabs: ContextTab[] = [];
  if (contents.files.length > 0) tabs.push("context");
  if ((contents.memories?.length ?? 0) > 0) tabs.push("memories");
  if (contents.plan !== null && contents.plan.steps.length > 0) tabs.push("plan");
  if (contents.sources.length > 0) tabs.push("sources");
  if (contents.activity.length > 0) tabs.push("activity");
  return tabs;
}

/** Files used in a conversation, each once, newest last. */
export function filesInUse(perTurn: readonly (readonly ComposerAttachment[])[]): ComposerAttachment[] {
  const seen = new Set<string>();
  const files: ComposerAttachment[] = [];
  for (const attachments of perTurn) {
    for (const file of attachments) {
      const key = file.attachmentId ?? file.path ?? file.label;
      if (seen.has(key)) continue;
      seen.add(key);
      files.push(file);
    }
  }
  return files;
}

/**
 * QUI-C07 — the memories this conversation's turns were given, each once.
 *
 * Read from the recall ledger, which is read live from Memory: a memory
 * forgotten since its turn ran is already absent, so this never lists one.
 * Inclusion, not reliance: a turn was given it, which does not mean the
 * answer leaned on it.
 */
export function memoriesInUse(recalled: readonly RecalledMemory[]): RecalledMemory[] {
  const seen = new Set<string>();
  const memories: RecalledMemory[] = [];
  for (const memory of recalled) {
    if (seen.has(memory.memory_id)) continue;
    seen.add(memory.memory_id);
    memories.push(memory);
  }
  return memories;
}
