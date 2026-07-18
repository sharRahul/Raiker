<script lang="ts">
  import type { Notification } from "../apiTypes";

  let { notifications }: { notifications: Notification[] } = $props();
  const unread = $derived(notifications.filter((notification) => !notification.read));
</script>

{#if unread.length}
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
