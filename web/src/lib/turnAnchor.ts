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

/** A surface that owns a conversation, as a session records it. */
export type WorkOrigin = "chat" | "build" | "design";

/** The route each surface's conversations are resumed on. */
const WORK_MODE_ROUTES: Record<WorkOrigin, "new-chat" | "build" | "design"> = {
  chat: "new-chat",
  build: "build",
  design: "design",
};

/**
 * REM-THREAD-03 — where a conversation is resumed, from what opened it.
 *
 * Threads and the Sessions inspector both offered "open in chat" for every
 * row, because every session was stored as a chat. A Build conversation opened
 * in Chat is not the same conversation: its repository, its pending diffs and
 * the approvals over them are Build's, and none of them is on the Chat screen.
 *
 * An unrecognised origin resolves to Chat rather than to nothing. A workspace
 * written by an older build stores no origin at all, and the transcript is
 * readable in Chat whatever surface produced it — so the fallback is the one
 * that always works, not a dead row.
 */
export function workModeRoute(origin: string | null | undefined): "new-chat" | "build" | "design" {
  const named = (origin ?? "").toLowerCase();
  return WORK_MODE_ROUTES[named as WorkOrigin] ?? "new-chat";
}

/** The route link that opens `turnId` inside `sessionId`. */
export function conversationLink(
  route: "new-chat" | "build" | "design",
  sessionId: string,
  turnId?: string | null,
): string {
  const params = new URLSearchParams({ session: sessionId });
  if (turnId !== undefined && turnId !== null && turnId !== "")
    params.set("turn", turnId);
  return `#/${route}?${params.toString()}`;
}

/**
 * REM-THREAD-03 — the technical record behind one conversation.
 *
 * Threads resumes work; Observability's Sessions inspector verifies how it ran.
 * They are different jobs, and a row that offered only the first left the
 * second reachable by navigating to a hub and finding the session again.
 * `#/sessions?session=…` is the address the router already aliases, so a link
 * written before this existed still resolves.
 */
export function evidenceLink(sessionId: string, turnId?: string | null): string {
  const params = new URLSearchParams({ session: sessionId });
  if (turnId !== undefined && turnId !== null && turnId !== "") params.set("turn", turnId);
  return `#/sessions?${params.toString()}`;
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
