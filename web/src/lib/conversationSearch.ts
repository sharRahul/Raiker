/**
 * QUI-C01 — search in conversation.
 *
 * Which turns of the conversation on screen mention the words typed, in order.
 * A turn matches when its prompt or its answer contains every word, ignoring
 * case, so "anna reply" finds "Draft a reply to Anna". It searches only what
 * this conversation holds; Search finds things across conversations.
 */
export interface SearchableTurn {
  prompt: string;
  answer: string;
}

export function conversationMatches(turns: readonly SearchableTurn[], query: string): number[] {
  const words = query.toLowerCase().split(/\s+/).filter((word) => word !== "");
  if (words.length === 0) return [];
  const hits: number[] = [];
  turns.forEach((turn, index) => {
    const text = `${turn.prompt}\n${turn.answer}`.toLowerCase();
    if (words.every((word) => text.includes(word))) hits.push(index);
  });
  return hits;
}

/** "2 of 5", or "No matches" once something has been typed. */
export function matchLabel(current: number, total: number): string {
  if (total === 0) return "No matches";
  return `${current + 1} of ${total}`;
}
