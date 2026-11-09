/**
 * QUI-P02 acceptance — a permission changed in one place is shown everywhere
 * without a reload.
 *
 * Each permission is stored once (decision modes, gates, standing grants and
 * Allow-with-limits rules, a conversation's profile); the surfaces that show
 * them each read the server. What they lacked was a reason to read again, so
 * a change in Permissions left the composer, Build's posture line, a
 * connection's detail and Memory › Controls showing what used to be true until
 * the page was reloaded.
 *
 * Two signals, the same pair approval resolution uses (`approvalResume.ts`):
 * an event on this page, and a `BroadcastChannel` for the owner's other tabs.
 * Both are hints carrying no data: every listener re-reads the server, which
 * stays the only authority on what is allowed.
 */
export const PERMISSIONS_CHANGED = "raiker:permissions-changed";
const CHANNEL = "raiker-permissions";

/** What changed, so a listener can skip a read it does not need. */
export type PermissionChange = "modes" | "gates" | "rules" | "profile" | "connections";

function channel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  try {
    return new BroadcastChannel(CHANNEL);
  } catch {
    return null;
  }
}

/** Tell this page and the owner's other tabs that a permission changed. */
export function announcePermissionsChanged(kind: PermissionChange): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<PermissionChange>(PERMISSIONS_CHANGED, { detail: kind }));
  const out = channel();
  if (out !== null) {
    try {
      out.postMessage(kind);
    } finally {
      out.close();
    }
  }
}

/**
 * Re-read when a permission changes here or in another tab.
 * Returns the function that stops listening.
 */
export function onPermissionsChanged(reread: (kind: PermissionChange) => void): () => void {
  if (typeof window === "undefined") return () => {};
  const local = (event: Event) => reread((event as CustomEvent<PermissionChange>).detail ?? "modes");
  window.addEventListener(PERMISSIONS_CHANGED, local);
  const inbox = channel();
  if (inbox !== null) inbox.onmessage = (event) => reread((event.data as PermissionChange) ?? "modes");
  return () => {
    window.removeEventListener(PERMISSIONS_CHANGED, local);
    inbox?.close();
  };
}
