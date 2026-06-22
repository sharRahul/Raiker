<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { Diagnostics } from "./apiTypes";
  import Badge from "./Badge.svelte";

  let data = $state<Diagnostics | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      data = await api.diagnostics();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  });
</script>

<h1 id="page-title">Diagnostics</h1>

{#if error}
  <p class="state-error">Diagnostics unavailable: {error}</p>
{:else if data === null}
  <p class="state-loading">Loading diagnostics…</p>
{:else}
  <p class="scope">{data.scope_note}</p>
  <div class="card">
    <p>
      <span class="k">Runtime mode</span> <code>{data.runtime_mode}</code>
      {#if data.production_ready_local_single_user_runtime}<Badge variant="implemented" />{:else}<Badge variant="disabled" />{/if}
    </p>
    <p><span class="k">Production-ready (local single-user)</span> {data.production_ready_local_single_user_runtime ? "yes" : "no"}</p>
  </div>

  <div class="card">
    <h2>Counts</h2>
    <ul class="kv">
      {#each Object.entries(data.counts) as [key, value] (key)}
        <li><span class="k">{key}</span> {value}</li>
      {/each}
    </ul>
  </div>

  <div class="card">
    <h2>Disabled / deferred capabilities ({data.disabled_capabilities.length})</h2>
    <div class="chips">
      {#each data.disabled_capabilities as cap (cap)}
        <span class="chip"><Badge variant="disabled" /> <code>{cap}</code></span>
      {/each}
    </div>
  </div>
{/if}

<style>
  .scope {
    color: #8b8b93;
    font-style: italic;
  }
  .card {
    border: 1px solid #2a2a2e;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    background: #101013;
    margin-top: 0.75rem;
  }
  .k {
    color: #8b8b93;
    text-transform: uppercase;
    font-size: 0.66rem;
    letter-spacing: 0.05em;
    margin-right: 0.4rem;
  }
  .kv,
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.25rem;
  }
  .chip code {
    color: #cfe5ff;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading {
    color: #9a9aa2;
  }
</style>
