<script lang="ts">
  import type { Notification as RaikerNotification } from "../apiTypes";
  import { uiPrefs } from "../prefs.svelte";

  let { notifications }: { notifications: RaikerNotification[] } = $props();
  const unread = $derived(notifications.filter((notification) => !notification.read));

  // Mirror new unread notifications to the desktop when the owner enabled the
  // preference and the browser permission is granted. Best-effort only — the
  // in-app record is the source of truth.
  let mirrored = new Set<string>();
  $effect(() => {
    if (!uiPrefs.desktop || typeof Notification === "undefined" || Notification.permission !== "granted") return;
    for (const item of unread) {
      if (mirrored.has(item.notification_id)) continue;
      mirrored.add(item.notification_id);
      try {
        new Notification(item.title, { body: item.body });
      } catch {
        // Notification constructor unavailable (e.g. headless): in-app only.
      }
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
