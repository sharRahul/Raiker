/**
 * QUI-C06 — the conversations the sidebar lists under Chat.
 *
 * The owner's own chats only: a routine's thread is work Raiker advances on its
 * own and lives in Work › Threads. Untitled and archived threads are left out.
 * Newest first, five at most.
 */
import type { WorkThread } from "./apiTypes";

export interface RecentChat {
  readonly sessionId: string;
  readonly title: string;
  readonly href: string;
}

export const RECENT_CHAT_LIMIT = 5;

export function recentChats(threads: readonly WorkThread[]): RecentChat[] {
  return threads
    .filter((thread) => thread.kind === "chat" && !thread.archived && thread.title.trim() !== "")
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
    .slice(0, RECENT_CHAT_LIMIT)
    .map((thread) => ({
      sessionId: thread.session_id,
      title: thread.title,
      href: `#/new-chat?session=${encodeURIComponent(thread.session_id)}`,
    }));
}
