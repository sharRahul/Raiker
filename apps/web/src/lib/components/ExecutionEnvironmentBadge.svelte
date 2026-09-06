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

  function runtimeName(runtime: string | undefined): string {
    return runtime ? runtime.charAt(0).toUpperCase() + runtime.slice(1) : "Container";
  }
</script>

<a class="environment-badge" class:unavailable={unavailable || selected?.available === false} href="#/settings?tab=runtime" aria-label="Execution environment">
  <span class="dot"></span>
  {#if unavailable}Environment unavailable{:else if selected}{selected.name}{selected.kind === "container" ? ` · ${runtimeName(selected.runtime)}` : ""} · {selected.available ? "Ready" : "Setup required"}{:else}Loading environment…{/if}
</a>

<style>
  .environment-badge { display:inline-flex; align-items:center; gap:.38rem; min-height:28px; padding:.25rem .55rem; border:1px solid var(--border); border-radius:var(--r-pill); background:var(--surface); color:var(--text-2); font-size:var(--text-xs); text-decoration:none; white-space:nowrap; } /* VIS2-16 — the healthy dot is neutral. This badge is on screen under every
     turn, so a green dot there is a green dot the owner sees all day; the
     amber one only means something because its neighbour does not. */
  .dot { width:6px; height:6px; border-radius:50%; background:var(--text-3); } .unavailable .dot { background:var(--warn); }
</style>
