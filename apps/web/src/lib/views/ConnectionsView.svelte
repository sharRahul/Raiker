<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ConnectionsView, ConnectorView } from "../apiTypes";

  let view = $state<ConnectionsView | null>(null);
  let loadError = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      view = await api.connections();
    } catch (e) {
      view = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // A connector is usable in chat only when every fail-closed gate is open at
  // once: capability enabled AND decision mode raised to "allow" AND owner
  // credential set AND host egress-allowlisted. Reported honestly so the owner
  // sees exactly what is still holding it closed.
  function usable(c: ConnectorView): boolean {
    return (
      c.capability_enabled &&
      c.decision_mode === "allow" &&
      c.credential_configured &&
      c.egress_allowed
    );
  }

  type Check = { label: string; ok: boolean; detail: string };
  function checks(c: ConnectorView): Check[] {
    return [
      {
        label: "Capability gate",
        ok: c.capability_enabled,
        detail: c.capability_enabled
          ? `Enabled (${c.gate_state})`
          : `Off (${c.gate_state}) — turn on in Capabilities`,
      },
      {
        label: "Decision mode",
        ok: c.decision_mode === "allow",
        detail:
          c.decision_mode === "allow"
            ? "Allowed (standing reads run)"
            : `“${c.decision_mode}” — reads are withheld until raised to “allow” in Capabilities`,
      },
      {
        label: "Owner credential",
        ok: c.credential_configured,
        detail: c.credential_configured
          ? `${c.credential_env} is set`
          : `Set ${c.credential_env} in the server environment`,
      },
      {
        label: "Egress allowlist",
        ok: c.egress_allowed,
        detail: c.egress_allowed
          ? `${c.egress_host} is allowlisted`
          : `Add ${c.egress_host} to RAIKER_CONNECTOR_EGRESS_ALLOWLIST`,
      },
    ];
  }

  onMount(load);
</script>

<p class="page-lead">
  Governed service connectors let the agent read from outside services during a turn. Every
  connector is <strong>fail-closed by default</strong>: it works only when its capability is
  enabled, its decision mode is raised to <strong>allow</strong>, the owner credential is set in the
  server environment, and its host is on the egress allowlist. This page is read-only — it never
  reaches the network and never shows a credential value; enable connectors in
  <strong>Capabilities</strong>.
</p>

<div class="toolbar">
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh connections">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if view === null}
  <p class="loading">Loading…</p>
{:else}
  {#if !view.connector_egress_allowlist_configured}
    <p class="notice notice-warn" role="status">
      No connector egress allowlist is configured. Set
      <code>RAIKER_CONNECTOR_EGRESS_ALLOWLIST</code> in the server environment before any connector can
      reach the network.
    </p>
  {/if}
  <div class="conn-list">
    {#each view.connectors as c (c.connector_id)}
      <div class="conn card">
        <div class="conn-head">
          <div class="conn-title">
            <span class="conn-name">{c.display_name}</span>
            <span class="tag tag-kind">{c.kind === "read_only" ? "read-only" : c.kind}</span>
          </div>
          <span class="status" class:on={usable(c)}>
            <Icon name={usable(c) ? "check" : "lock"} size={14} />
            {usable(c) ? "Ready" : "Fail-closed"}
          </span>
        </div>
        <p class="conn-cap">Capability: <code>{c.capability}</code></p>
        <ul class="checks">
          {#each checks(c) as check (check.label)}
            <li class:ok={check.ok}>
              <Icon name={check.ok ? "check" : "x"} size={13} />
              <span class="check-label">{check.label}:</span>
              <span class="check-detail">{check.detail}</span>
            </li>
          {/each}
        </ul>
        <p class="conn-actions">
          Actions: {#each c.actions as a, i (a)}<code>{a}</code>{#if i < c.actions.length - 1}, {/if}{/each}
        </p>
      </div>
    {/each}
  </div>
{/if}

<style>
  .toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: var(--space-4);
  }
  .conn-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .conn {
    padding: var(--space-4);
  }
  .conn-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .conn-title {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .conn-name {
    font-weight: 600;
    font-size: 1rem;
  }
  .tag {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.1rem 0.5rem;
    border-radius: var(--r-pill);
    background: var(--sunken);
    color: var(--text-3);
    border: 1px solid var(--border);
  }
  .status {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-3);
  }
  .status.on {
    color: var(--accent);
  }
  .conn-cap {
    font-size: 0.82rem;
    color: var(--text-3);
    margin: 0.5rem 0 0.75rem;
  }
  .checks {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .checks li {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    font-size: 0.84rem;
    color: var(--danger);
  }
  .checks li.ok {
    color: var(--text-2);
  }
  .check-label {
    font-weight: 600;
    color: var(--text-1);
  }
  .check-detail {
    color: var(--text-2);
  }
  .conn-actions {
    margin: 0.9rem 0 0;
    font-size: 0.8rem;
    color: var(--text-3);
  }
  .notice-warn {
    background: var(--warning-soft, var(--sunken));
    border: 1px solid var(--border-strong);
    padding: 0.6rem 0.9rem;
    border-radius: var(--r-md, 8px);
    font-size: 0.84rem;
    margin-bottom: var(--space-3);
  }
  code {
    font-size: 0.8em;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
    font-size: 0.84rem;
  }
</style>
