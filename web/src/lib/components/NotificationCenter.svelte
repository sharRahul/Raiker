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

{#if uiPrefs.inApp && unread.length}
  <section class="notifications" aria-label="Notifications">
    {#each unread.slice(0, 3) as notification (notification.notification_id)}
      <div class="notice notice-warn" role="status">
        <strong>{notification.title}</strong><span>{notification.body}</span>
      </div>
    {/each}
    <!-- Three is what fits without becoming the page. The rest are not lost:
         every notice is recorded, and the link says where. -->
    <a class="all" href="#/observe?tab=notifications">
      {unread.length > 3
        ? `All ${unread.length} notices`
        : unread.length === 1
          ? "Open notifications"
          : "All notices"}
    </a>
  </section>
{/if}

<style>
  .notifications {
    display: grid;
    gap: var(--space-2);
    margin: 0 auto var(--space-3);
    max-width: 64rem;
    padding: var(--space-3) var(--space-4) 0;
  }
  .notice { display: flex; gap: .45rem; flex-wrap: wrap; margin: 0; }
  .notice span { color: var(--text-2); }
  .all { color: var(--text-2); font-size: var(--text-sm); justify-self: start; }
</style>
