/**
 * MEM-08 — a turn coordinate you can open.
 *
 * `conversation_search` has always returned `session_id` and `turn_id`, chat
 * search has always known which exchange matched (`match_turn_id`), and a
 * checkpoint has always named the turn it was taken at. None of the three was
 * a link: verifying "we settled this in March" meant opening the conversation
 * at the top and scrolling. The coordinates existed; nothing accepted one.
 *
 * This is the accepting half, and it is deliberately three small functions
 * rather than a router: the address bar already carries `session`
 * (`sessionRoute.ts`), so an anchor is one more non-secret key beside it, and
 * `routeState.ts`'s rule still holds — a URL may carry a coordinate, never a
 * payload, a credential or a decision.
 */

/** The route link that opens `turnId` inside `sessionId`. */
export function conversationLink(
  route: "new-chat" | "build",
  sessionId: string,
  turnId?: string | null,
): string {
  const params = new URLSearchParams({ session: sessionId });
  if (turnId !== undefined && turnId !== null && turnId !== "")
    params.set("turn", turnId);
  return `#/${route}?${params.toString()}`;
}

/** Drop `turn=` from the current address, keeping everything else. */
export function forgetTurnInRoute(): void {
  if (typeof window === "undefined") return;
  const hash = window.location.hash;
  const withoutHash = hash.startsWith("#") ? hash.slice(1) : hash;
  const [path, query = ""] = withoutHash.split("?", 2);
  const params = new URLSearchParams(query);
  if (!params.has("turn")) return;
  params.delete("turn");
  const rest = params.toString();
  const { pathname, search } = window.location;
  const next = rest === "" ? `#${path}` : `#${path}?${rest}`;
  window.history.replaceState(
    window.history.state,
    "",
    `${pathname}${search}${next}`,
  );
}

/**
 * Bring the anchored exchange into view and mark it, once.
 *
 * The mark is a class the transcript styles and a `tick` later removes: a
 * permanent highlight would make a shared link look like a permanent state of
 * the conversation, which it is not. Returns whether the turn was found, so the
 * caller can say "that exchange is not in this conversation" rather than
 * silently doing nothing.
 */
export function revealTurn(
  root: HTMLElement | undefined,
  turnId: string,
): boolean {
  if (root === undefined || turnId === "") return false;
  // `CSS` is absent in some non-browser DOM implementations, and a coordinate
  // that cannot be escaped is one that must not be spliced into a selector —
  // so an environment without it looks the id up by comparison instead.
  const escape = typeof CSS !== "undefined" && typeof CSS.escape === "function" ? CSS.escape : null;
  const target =
    escape === null
      ? [...root.querySelectorAll<HTMLElement>("[data-turn-id]")].find(
          (node) => node.dataset.turnId === turnId,
        ) ?? null
      : root.querySelector<HTMLElement>(`[data-turn-id="${escape(turnId)}"]`);
  if (target === null) return false;
  // jsdom implements neither, and a missing scroll must not cost the mark.
  target.scrollIntoView?.({ block: "center" });
  target.classList.add("turn-anchored");
  window.setTimeout(() => target.classList.remove("turn-anchored"), 2600);
  return true;
}
