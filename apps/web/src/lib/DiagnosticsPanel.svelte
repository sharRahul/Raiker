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
    <h2>Readiness</h2>
    <ul class="kv">
      {#each Object.entries(data.readiness) as [key, ok] (key)}
        <li>
          <Badge variant={ok ? "implemented" : "disabled"} />
          <span class="rk">{key.replace(/_/g, " ")}</span>
        </li>
      {/each}
    </ul>
  </div>

  <div class="card">
    <h2>Missing configuration ({data.missing_config.length})</h2>
    {#if data.missing_config.length === 0}
      <p class="ok-line"><Badge variant="implemented" /> No missing configuration detected.</p>
    {:else}
      <ul class="list">
        {#each data.missing_config as gap (gap)}
          <li><Badge variant="needs-approval" /> {gap}</li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="card">
    <h2>Provider health ({data.provider_health.length})</h2>
    <p class="hint">Configuration-derived. Reachability is not probed from the browser; check it on demand via the CLI.</p>
    {#if data.provider_health.length === 0}
      <p class="state-empty">No model providers configured.</p>
    {:else}
      <table class="providers">
        <thead>
          <tr><th>Profile</th><th>Provider</th><th>Network</th><th>Status</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {#each data.provider_health as p (p.profile_id)}
            <tr>
              <td class="mono">{p.profile_id}{#if p.selected} <Badge variant="implemented" />{/if}</td>
              <td>{p.provider}</td>
              <td>{p.requires_network ? "required" : p.local_only ? "local-only" : "—"}</td>
              <td>{p.status}</td>
              <td class="muted">{p.detail}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
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
  .rk {
    text-transform: capitalize;
    font-size: 0.84rem;
  }
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.86rem;
  }
  .list li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .ok-line {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0;
  }
  .hint {
    color: #8b8b93;
    font-size: 0.8rem;
    margin: 0 0 0.5rem;
  }
  table.providers {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  .providers th,
  .providers td {
    text-align: left;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #1f1f24;
    vertical-align: top;
  }
  .providers th {
    color: #8b8b93;
    font-weight: 600;
  }
  .mono {
    font-family: ui-monospace, monospace;
    color: #b6b6bd;
  }
  .muted {
    color: #8b8b93;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading,
  .state-empty {
    color: #9a9aa2;
  }
</style>
