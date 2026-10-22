/**
 * QUI-P04 — what a connection's activity does, in the owner's words.
 *
 * Read off the operation's own HTTP method, which is what the connector runtime
 * sends: a read method only reads; DELETE removes something the service will
 * not give back through Raiker; anything else changes something there. The
 * runtime's own rule for what asks first is separate (`requires_confirmation`)
 * and shown beside it.
 */
export type OperationEffect = { id: "reads" | "changes" | "permanent"; label: string };

const READ_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function operationEffect(method: string): OperationEffect {
  const verb = method.trim().toUpperCase();
  if (READ_METHODS.has(verb)) return { id: "reads", label: "Reads" };
  if (verb === "DELETE") return { id: "permanent", label: "Can't be undone" };
  return { id: "changes", label: "Changes" };
}
