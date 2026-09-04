<script lang="ts">
  import type { Notification as RaikerNotification } from "../apiTypes";
  import { canRaiseDesktopNotice, raiseDesktopNotice } from "../desktopNotice";
  import { uiPrefs } from "../prefs.svelte";

  let { notifications }: { notifications: RaikerNotification[] } = $props();
  const unread = $derived(notifications.filter((notification) => !notification.read));

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
      <div class="notice notice-warn" role="status"><strong>{notification.title}</strong><span>{notification.body}</span></div>
    {/each}
  </section>
{/if}

<style>
  .notifications { display: grid; gap: var(--space-2); margin-bottom: var(--space-3); }
  .notice { display: flex; gap: .45rem; flex-wrap: wrap; margin: 0; }
  .notice span { color: var(--text-2); }
</style>
