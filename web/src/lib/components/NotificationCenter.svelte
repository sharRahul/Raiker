<script lang="ts">
  /**
   * Unread notices, wherever the owner is — and the one place the notification
   * preferences actually reach.
   *
   * **REM-SET-NOTIFY.** Settings offered two switches, *In-app popups* and
   * *Desktop alerts*, described as though they governed how Raiker reaches you.
   * The second did. The first governed this strip, and this strip was mounted
   * on the MCP page and nowhere else — so a setting presented as an account-wide
   * alert preference decided whether a banner appeared on one destination the
   * owner may never open. That is not a control whose scope can be labelled
   * accurately; it is a control in the wrong place.
   *
   * It reads its own notifications rather than taking them as a prop, for the
   * same reason `ApprovalPrompt` does: the shell is where it belongs, the shell
   * has no reason to know about notifications, and a component that is the only
   * thing using a read should own it.
   *
   * **The in-app record is still the truth.** This is a courtesy on top of
   * Observability → Notifications, which holds every notice whether or not
   * either alert showed it. Nothing here is the only copy of anything, so a
   * failed read changes nothing on screen and the next tick tries again.
   */
  import type { Notification as RaikerNotification } from "../apiTypes";
  import { api, hasToken } from "../api";
  import { canRaiseDesktopNotice, raiseDesktopNotice } from "../desktopNotice";
  import { uiPrefs } from "../prefs.svelte";

  /** How often unread notices are re-read. The record is not urgent; a notice
   *  about work that finished is still true a minute later. */
  const POLL_MS = 30000;

  let notifications = $state<RaikerNotification[]>([]);
  const unread = $derived(notifications.filter((notification) => !notification.read));

  async function poll() {
    if (!hasToken()) return;
    try {
      notifications = await api.notifications();
    } catch {
      // A failed read leaves the strip as it was. The complete record is on
      // Observability → Notifications either way.
    }
  }

  $effect(() => {
    void poll();
    const timer = setInterval(() => void poll(), POLL_MS);
    return () => clearInterval(timer);
  });

  /**
   * Reading it is what clears it.
   *
   * A docked notice that nothing dismisses is a permanent obstruction, which is
   * a worse defect than the one this strip was moved to fix. Opening it marks
   * the notice read through the same route the bell's **Mark all read** uses,
   * so the strip, the bell's count and the record never disagree — and the
   * owner lands on the record rather than on a banner they have to ignore.
   */
  async function open(notification: RaikerNotification) {
    window.location.hash =
      notification.kind === "task_finished" ? "#/tasks" : "#/observe?tab=notifications";
    try {
      await api.markNotificationRead(notification.notification_id);
    } catch {
      // The navigation already happened and the record is still the record.
      // A failed mark leaves the notice unread, which is the truth.
    }
    await poll();
  }

  // Mirror new unread notifications to the desktop through the one path every
  // surface uses (BUG-255). Best-effort only — the in-app record is the source
  // of truth.
  let mirrored = new Set<string>();
  $effect(() => {
    if (!canRaiseDesktopNotice()) return;
    for (const item of unread) {
      if (mirrored.has(item.notification_id)) continue;
      mirrored.add(item.notification_id);
      raiseDesktopNotice({
        title: item.title,
        body: item.body,
        tag: item.notification_id,
        // C10 — clicking a notice about background work should land on the
        // work. Only for the kinds that have somewhere to land.
        route: item.kind === "task_finished" ? "#/tasks" : undefined,
      });
    }
  });
</script>

{#if uiPrefs.inApp && unread.length > 0}
  {@const newest = unread[0]}
  <section class="notifications" aria-label="Notifications">
    <!-- One, not a stack. Three docked cards covered Home's primary actions at
         1080p and most of the screen at 390px, which is a worse obstruction
         than the banner nobody could see. The rest are never lost: the bell
         counts them and the link below opens the record. -->
    <button type="button" class="notice" onclick={() => void open(newest)}>
      <strong>{newest.title}</strong><span>{newest.body}</span>
    </button>
    {#if unread.length > 1}
      <a class="all" href="#/observe?tab=notifications"
        >{unread.length} unread notices</a
      >
    {/if}
  </section>
{/if}

<style>
  /**
   * Docked rather than in the flow, and the reason is measurable.
   *
   * The first placement put this inside `main#main`, above the routed page. The
   * responsive sweep caught it immediately: Chat, Build and Design size
   * themselves to `--content-h` — the room between the topbar and the bottom of
   * the viewport — so anything added above them pushes their composer below the
   * fold. At 390×844 Build's composer ended 385px past the bottom edge.
   *
   * A notice is not page content; the record is, and it is one link away. So
   * this docks like `ApprovalPrompt` does — fixed, bounded, and taking no part
   * in any page's height — at the opposite corner, so the two never collide.
   */
  .notifications {
    position: fixed;
    top: calc(var(--topbar-h) + 12px);
    right: 20px;
    z-index: var(--z-docked);
    width: min(24rem, calc(100vw - 40px));
    display: grid;
    gap: var(--space-2);
    justify-items: start;
  }
  .notice {
    display: grid;
    gap: 0.15rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    padding: 0.72rem 0.8rem;
    border: 1px solid var(--warn-border, var(--neutral-border));
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  .notice:hover { border-color: var(--accent-border, var(--neutral-border)); }
  .notice strong { color: var(--text-1); font-size: var(--text-sm); }
  .notice span { color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .all {
    color: var(--text-2);
    font-size: var(--text-sm);
    padding: 0.2rem 0.5rem;
    border-radius: var(--r-sm);
    background: var(--surface);
    box-shadow: var(--shadow-1);
  }
</style>
