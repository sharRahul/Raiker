<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { Diagnostics } from "../../apiTypes";
  import NotYetActive from "./NotYetActive.svelte";

  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  let diag = $state<Diagnostics | null>(null);
  let error = $state<string | null>(null);
  const threshold = $derived((settings["storage.attachment_threshold_mb"] as number) ?? 32);

  async function load() {
    try {
      diag = await api.diagnostics();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }
  onMount(load);
</script>

<h2>Storage</h2>

<section class="card">
  <h3>Local usage</h3>
  {#if error}
    <p class="error" role="alert">{error}</p>
  {:else if diag === null}
    <p class="sub">Loading…</p>
  {:else}
    <ul class="metrics">
      <li>Sessions: <strong>{diag.counts.sessions}</strong></li>
      <li>Events: <strong>{diag.counts.events}</strong></li>
      <li>Tasks: <strong>{diag.counts.tasks}</strong></li>
      <li>Checkpoints: <strong>{diag.counts.checkpoints}</strong></li>
    </ul>
    <p class="sub">Live counts from the local runtime.</p>
  {/if}
</section>

<section class="card">
  <h3>Attachments</h3>
  <label>
    Attachment size threshold (MB)
    <input
      type="number"
      min="1"
      max="64"
      value={threshold}
      onchange={(e) => save({ "storage.attachment_threshold_mb": Number(e.currentTarget.value) })}
    />
  </label>
  <p class="sub">Saved to your account.</p>
</section>

<section class="card">
  <h3>Cache &amp; cloud</h3>
  <NotYetActive what="Cache clearing and cloud usage metrics" />
</section>

<style>
  .metrics {
    list-style: none;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
    gap: var(--space-2);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-width: 16rem;
  }
  .sub {
    color: var(--text-2);
  }
  .error {
    color: var(--danger);
  }
</style>
