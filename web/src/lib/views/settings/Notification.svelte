<script lang="ts">
  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  const inApp = $derived(settings["notification.in_app"] !== false);
  const desktop = $derived(Boolean(settings["notification.desktop"]));

  function toggleDesktop(enabled: boolean) {
    // Desktop alerts need the browser permission; request it on enable so the
    // preference never silently does nothing.
    if (enabled && typeof Notification !== "undefined" && Notification.permission === "default") {
      void Notification.requestPermission();
    }
    save({ "notification.desktop": enabled });
  }
</script>

<h2>Notifications</h2>

<section class="card">
  <h3>Alerts</h3>
  <label class="toggle">
    <input type="checkbox" checked={inApp} onchange={(e) => save({ "notification.in_app": e.currentTarget.checked })} />
    In-app popups
  </label>
  <label class="toggle">
    <input type="checkbox" checked={desktop} onchange={(e) => toggleDesktop(e.currentTarget.checked)} />
    Desktop alerts
  </label>
  <p class="sub">
    Desktop alerts appear only while Raiker is not the window you are looking at,
    and cover approvals waiting on you.
  </p>
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
