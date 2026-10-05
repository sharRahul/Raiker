/**
 * §13.2 item 6 — one key per draft, so sending the same draft twice files it once.
 *
 * A composer holds a key from the moment a draft starts until the server has
 * accepted it; a double click, or pressing again after a lost response, sends
 * the same key and gets the first answer back instead of a second task. A key
 * is replaced only after success, or when the server says this draft's earlier
 * attempt already went through with different content.
 */
export function newIdempotencyKey(): string {
  const random =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  return `draft-${random}`;
}
