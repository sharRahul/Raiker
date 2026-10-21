/**
 * QUI-C07 — Chat's context panel.
 *
 * Closed by default. Its tabs are Context (files in use), Plan, Sources and
 * Activity, and a tab is drawn only when it has something in it: an empty tab
 * is a report that there is nothing to report.
 */
import type { AgentPlan, TurnSourceView } from "./apiTypes";
import type { ToolCallRow } from "./chatPresentation";
import type { ComposerAttachment } from "./composerAttachments.svelte";

export type ContextTab = "context" | "plan" | "sources" | "activity";

export const CONTEXT_TAB_LABELS: Record<ContextTab, string> = {
  context: "Context",
  plan: "Plan",
  sources: "Sources",
  activity: "Activity",
};

export interface ContextContents {
  files: readonly ComposerAttachment[];
  plan: AgentPlan | null;
  sources: readonly TurnSourceView[];
  activity: readonly ToolCallRow[];
}

/** The tabs worth drawing, in their fixed order. */
export function contextTabs(contents: ContextContents): ContextTab[] {
  const tabs: ContextTab[] = [];
  if (contents.files.length > 0) tabs.push("context");
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
