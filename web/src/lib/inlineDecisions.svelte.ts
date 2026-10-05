/**
 * Decisions a page is already showing in its own body (BUG-317).
 *
 * Build lists a turn's pending approvals in its **Waiting on you** card, with
 * the diff and Accept/Deny beside it. The shell's approval card appeared at the
 * same moment, anchored bottom-right over the end of that card, offering the
 * same decision a second time. A page that shows a decision inline marks it
 * with {@link shownInline}; the approval card leaves it alone *while it is on
 * screen*. Chat and Build stay mounted, hidden, when the owner moves to another
 * route, so a mark alone would have hidden the card everywhere (found by the
 * live round); visibility is read from the element itself.
 */
// Element references, not state: `inlineDecisions.version` is what readers track.
// eslint-disable-next-line svelte/prefer-svelte-reactivity
const nodes = new Map<string, Set<HTMLElement>>();

/** Bumped when a mark is added or removed, so readers re-evaluate. */
export const inlineDecisions = $state<{ version: number }>({ version: 0 });

/** True when an element marking this decision is on screen now. */
export function shownInlineNow(approvalId: string): boolean {
  for (const node of nodes.get(approvalId) ?? []) {
    if (node.isConnected && node.getClientRects().length > 0) return true;
  }
  return false;
}

function add(id: string, node: HTMLElement) {
  // eslint-disable-next-line svelte/prefer-svelte-reactivity
  const set = nodes.get(id) ?? new Set<HTMLElement>();
  set.add(node);
  nodes.set(id, set);
  inlineDecisions.version += 1;
}

function remove(id: string, node: HTMLElement) {
  const set = nodes.get(id);
  if (!set) return;
  set.delete(node);
  if (set.size === 0) nodes.delete(id);
  inlineDecisions.version += 1;
}

/** Svelte action: `use:shownInline={approvalId}` on the element showing it. */
export function shownInline(node: HTMLElement, approvalId: string) {
  let current = approvalId;
  add(current, node);
  return {
    update(next: string) {
      remove(current, node);
      current = next;
      add(current, node);
    },
    destroy() {
      remove(current, node);
    },
  };
}

/** Test seam: forget every mark. */
export function resetInlineDecisions(): void {
  nodes.clear();
  inlineDecisions.version += 1;
}
