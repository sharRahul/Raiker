<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { EventEntry } from "./apiTypes";

  let events = $state<EventEntry[] | null>(null);
  let error = $state<string | null>(null);
  let sessionFilter = $state("");
  let typeFilter = $state("");

  async function load() {
    events = null;
    error = null;
    try {
      events = await api.events({
        session_id: sessionFilter || undefined,
        event_type: typeFilter || undefined,
        limit: 200,
      });
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  onMount(load);
</script>

<h1 id="page-title">Events / Audit Log</h1>
<p class="lead">Append-only governed event log (read-only).</p>

<form class="filters" onsubmit={(e) => { e.preventDefault(); load(); }}>
  <label>Session <input bind:value={sessionFilter} placeholder="sess_…" /></label>
  <label>Type <input bind:value={typeFilter} placeholder="e.g. policy_decision" /></label>
  <button type="submit">Filter</button>
</form>

{#if error}
  <p class="state-error">Events unavailable: {error}</p>
{:else if events === null}
  <p class="state-loading">Loading events…</p>
{:else if events.length === 0}
  <p class="state-empty">No events match.</p>
{:else}
  <table class="events">
    <thead>
      <tr><th>Time</th><th>Type</th><th>Actor</th><th>Session</th><th>Turn</th></tr>
    </thead>
    <tbody>
      {#each events as ev (ev.event_id)}
        <tr>
          <td class="mono">{ev.timestamp}</td>
          <td>{ev.event_type}</td>
          <td>{ev.actor}</td>
          <td class="mono">{ev.session_id}</td>
          <td class="mono">{ev.turn_id ?? "—"}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .lead {
    color: #c2c2c9;
  }
  .filters {
    display: flex;
    gap: 0.75rem;
    align-items: end;
    margin: 0.5rem 0 0.75rem;
    flex-wrap: wrap;
  }
  .filters label {
    display: flex;
    flex-direction: column;
    font-size: 0.72rem;
    color: #8b8b93;
    gap: 0.2rem;
  }
  .filters input {
    background: #0e0e11;
    border: 1px solid #33333a;
    color: #d6d6dc;
    border-radius: 5px;
    padding: 0.3rem 0.4rem;
  }
  .filters button {
    background: #1c2a3a;
    color: #cfe5ff;
    border: 1px solid #2d5a82;
    border-radius: 5px;
    padding: 0.35rem 0.8rem;
    cursor: pointer;
  }
  .filters input:focus-visible,
  .filters button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  table.events {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  .events th,
  .events td {
    text-align: left;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #1f1f24;
  }
  .events th {
    color: #8b8b93;
    font-weight: 600;
  }
  .mono {
    font-family: ui-monospace, monospace;
    color: #b6b6bd;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading,
  .state-empty {
    color: #9a9aa2;
  }
</style>
