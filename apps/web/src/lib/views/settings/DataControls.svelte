<script lang="ts">
  import NotYetActive from "./NotYetActive.svelte";

  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  const historyTracking = $derived(settings["data.history_tracking"] !== false);
</script>

<h2>Data Controls</h2>

<section class="card">
  <h3>History</h3>
  <label class="toggle">
    <input
      type="checkbox"
      checked={historyTracking}
      onchange={(e) => save({ "data.history_tracking": e.currentTarget.checked })}
    />
    Keep chat &amp; task history
  </label>
  <p class="sub">Saved to your account.</p>
</section>

<section class="card">
  <h3>Model training</h3>
  <NotYetActive what="Model-training permission controls (this runtime never trains on your data)" />
</section>

<section class="card">
  <h3>Export your data</h3>
  <NotYetActive what="Exportable data request tooling" />
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
