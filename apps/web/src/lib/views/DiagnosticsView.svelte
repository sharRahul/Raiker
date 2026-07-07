<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { Diagnostics } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize } from "../format";

  let diag = $state<Diagnostics | null>(null);
  let loadError = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      diag = await api.diagnostics();
    } catch (e) {
      diag = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  const readinessChecks = $derived.by(() => {
    if (diag === null) return [];
    return Object.entries(diag.readiness)
      .filter(([, v]) => typeof v === "boolean")
      .map(([key, ok]) => ({ key, ok: Boolean(ok) }));
  });

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    An honest report of the local runtime, derived from stored state only — nothing here probes the
    network or fabricates health.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh diagnostics">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if diag === null}
  <p class="loading">Loading…</p>
{:else}
  <div class="grid">
    <section class="card" aria-labelledby="diag-status-h">
      <h2 id="diag-status-h">Runtime</h2>
      <p class="big-status">
        <Badge
          variant={diag.production_ready_local_single_user_runtime ? "implemented" : "approval-required"}
          label={diag.production_ready_local_single_user_runtime ? "production-ready (local)" : "not ready"}
        />
      </p>
      <dl class="kv">
        <div><dt>Mode</dt><dd>{humanize(diag.runtime_mode)}</dd></div>
        {#each Object.entries(diag.counts) as [key, value] (key)}
          <div><dt>{humanize(key)}</dt><dd>{value}</dd></div>
        {/each}
      </dl>
      <p class="sub">{diag.scope_note}</p>
    </section>

    <section class="card" aria-labelledby="diag-config-h">
      <h2 id="diag-config-h">Configuration gaps</h2>
      {#if diag.missing_config.length === 0}
        <p class="ok-line"><Icon name="check" size={15} /> No configuration gaps detected.</p>
      {:else}
        <ul class="gaps">
          {#each diag.missing_config as gap (gap)}
            <li><Icon name="warning" size={14} /> {gap}</li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="card" aria-labelledby="diag-readiness-h">
      <h2 id="diag-readiness-h">Readiness checks</h2>
      <ul class="checks">
        {#each readinessChecks as check (check.key)}
          <li class:ok={check.ok}>
            <Icon name={check.ok ? "check" : "x"} size={14} />
            <span>{check.key.replaceAll("_", " ")}</span>
          </li>
        {/each}
      </ul>
    </section>

    <section class="card" aria-labelledby="diag-providers-h">
      <h2 id="diag-providers-h">Provider status</h2>
      <p class="sub">Configuration-derived; reachability is never probed by this page.</p>
      <table class="table">
        <thead>
          <tr><th>Profile</th><th>Kind</th><th>Status</th></tr>
        </thead>
        <tbody>
          {#each diag.provider_health as p (p.profile_id)}
            <tr>
              <td class="mono">{p.profile_id}</td>
              <td>{p.endpoint_kind}</td>
              <td>
                <Badge variant={p.selected ? "active" : "idle"} label={p.status} />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    <section class="card wide" aria-labelledby="diag-disabled-h">
      <h2 id="diag-disabled-h">Disabled / deferred capabilities ({diag.disabled_capabilities.length})</h2>
      <p class="sub">
        These stay fail-closed until a real, governed executor exists. That is by design — the
        documentation never runs ahead of the code.
      </p>
      <div class="cap-chips">
        {#each diag.disabled_capabilities as cap (cap)}
          <span class="chip" title={cap}>{capabilityLabel(cap)}</span>
        {/each}
      </div>
    </section>
  </div>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
    gap: var(--space-4);
    align-items: start;
  }
  .wide {
    grid-column: 1 / -1;
  }
  .big-status {
    margin: 0 0 var(--space-3);
  }
  .kv {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
    gap: 0.4rem 1rem;
    margin: 0 0 var(--space-3);
  }
  .kv dt {
    font-size: 0.7rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .kv dd {
    margin: 0.05rem 0 0;
    font-size: 0.88rem;
  }
  .checks,
  .gaps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.85rem;
  }
  .checks li {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--danger);
  }
  .checks li.ok {
    color: var(--ok);
  }
  .checks li span {
    color: var(--text-1);
  }
  .gaps li {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    color: var(--warn);
  }
  .ok-line {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--ok);
    margin: 0;
  }
  .cap-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .chip {
    font-size: 0.74rem;
    font-weight: 600;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    padding: 0.1rem 0.6rem;
  }
  .sub {
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
