<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { ExecutionEnvironment } from "../apiTypes";

  let selected = $state<ExecutionEnvironment | null>(null);
  let unavailable = $state(false);

  async function load() {
    try {
      const view = await api.executionEnvironments();
      selected = view.environments.find((item) => item.selected) ?? null;
      unavailable = false;
    } catch { selected = null; unavailable = true; }
  }
  onMount(load);
</script>

<a class="environment-badge" class:unavailable href="#/settings/runtime" aria-label="Execution environment">
  <span class="dot"></span>
  {#if unavailable}Environment unavailable{:else if selected}{selected.name} · {selected.available ? "Ready" : "Setup required"}{:else}Loading environment…{/if}
</a>

<style>
  .environment-badge { display:inline-flex; align-items:center; gap:.38rem; min-height:28px; padding:.25rem .55rem; border:1px solid var(--border); border-radius:var(--r-pill); background:var(--surface); color:var(--text-2); font-size:.72rem; text-decoration:none; white-space:nowrap; } .dot { width:6px; height:6px; border-radius:50%; background:var(--ok); } .unavailable .dot { background:var(--warn); }
</style>
