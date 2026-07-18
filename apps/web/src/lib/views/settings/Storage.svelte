<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { Diagnostics } from "../../apiTypes";

  let diag = $state<Diagnostics | null>(null);
  let error = $state<string | null>(null);

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
    <p class="sub">Live counts from the local runtime. Everything stays on this machine.</p>
  {/if}
</section>

<style>
  .metrics {
    list-style: none;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
    gap: var(--space-2);
  }
  .sub {
    color: var(--text-2);
  }
  .error {
    color: var(--danger);
  }
</style>
