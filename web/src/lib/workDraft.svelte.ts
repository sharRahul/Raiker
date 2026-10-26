/** Unsent text is kept per workspace and project for this browser session only.
 * Attachments and execution/model settings remain owned by their surfaces. */
// This registry's membership is deliberately not reactive: callers react to the
// `$state` draft values. Making the Map reactive mutates state when a draft is
// first resolved from a `$derived`, which Svelte correctly refuses.
// eslint-disable-next-line svelte/prefer-svelte-reactivity
const drafts = new Map<string, { text: string }>();
export function workDraft(projectId: string, surface: "chat" | "build" | "design"): { text: string } {
  const key = JSON.stringify([surface, projectId]);
  const existing = drafts.get(key);
  if (existing) return existing;
  const draft = $state({ text: "" });
  drafts.set(key, draft);
  return draft;
}

/** Clear browser-session drafts when the owning session/test boundary ends. */
export function resetWorkDrafts(): void {
  drafts.clear();
}
