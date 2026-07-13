<script lang="ts">
  import NotYetActive from "./NotYetActive.svelte";

  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  const inApp = $derived(settings["notification.in_app"] !== false);
  const desktop = $derived(Boolean(settings["notification.desktop"]));
</script>

<h2>Notification</h2>

<section class="card">
  <h3>Alerts</h3>
  <label class="toggle">
    <input type="checkbox" checked={inApp} onchange={(e) => save({ "notification.in_app": e.currentTarget.checked })} />
    In-app popups
  </label>
  <label class="toggle">
    <input type="checkbox" checked={desktop} onchange={(e) => save({ "notification.desktop": e.currentTarget.checked })} />
    Desktop alerts
  </label>
  <p class="sub">Saved to your account. In-app popups are honored by the dashboard.</p>
</section>

<section class="card">
  <h3>Email notifications</h3>
  <NotYetActive what="Email notification delivery (no mail transport is configured)" />
</section>

<style>
  .toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .sub {
    color: var(--text-2);
  }
</style>
