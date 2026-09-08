/** Unsent text is shared within a project for this browser session only.
 * Attachments and execution/model settings remain owned by their surfaces. */
// This registry's membership is deliberately not reactive: callers react to the
// `$state` draft values. Making the Map reactive mutates state when a draft is
// first resolved from a `$derived`, which Svelte correctly refuses.
// eslint-disable-next-line svelte/prefer-svelte-reactivity
const drafts = new Map<string, { text: string }>();
export function workDraft(projectId: string): { text: string } {
  const existing = drafts.get(projectId);
  if (existing) return existing;
  const draft = $state({ text: "" });
  drafts.set(projectId, draft);
  return draft;
}

/** Clear browser-session drafts when the owning session/test boundary ends. */
export function resetWorkDrafts(): void {
  drafts.clear();
}
