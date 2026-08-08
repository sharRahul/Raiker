<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import IdentityChip from "../components/IdentityChip.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { EventEntry } from "../apiTypes";
  import { humanize, relativeTime, shortId } from "../format";

  let { sessionId = null }: { sessionId?: string | null } = $props();
  let events = $state<EventEntry[] | null>(null);
  let loadError = $state<string | null>(null);

  let sessionFilter = $state("");
  let typeFilter = $state("");
  let limit = $state("100");
  let loadedSessionId = $state<string | null | undefined>(undefined);

  async function load() {
    loadError = null;
    try {
      events = await api.events({
        session_id: sessionFilter.trim() || undefined,
        event_type: typeFilter.trim() || undefined,
        limit: Number(limit) || 100,
      });
    } catch (e) {
      events = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  function riskTone(risk: string | null): string {
    if (risk === "critical" || risk === "high") return "risk-high";
    if (risk === "medium") return "risk-med";
    return "risk-low";
  }

  $effect(() => {
    if (sessionId === loadedSessionId) return;
    loadedSessionId = sessionId;
    sessionFilter = sessionId ?? "";
    void load();
  });
</script>

<div class="head-row">
  <p class="page-lead">
    The append-only audit record — every governed step the runtime took, in full detail. This is
    deliberately the deep-dive view; day-to-day work lives in Chat, Approvals, and Tasks.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh events">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

<form
  class="filters"
  onsubmit={(e) => {
    e.preventDefault();
    void load();
  }}
>
  <div>
    <label class="field-label" for="ev-session">Session id</label>
    <input id="ev-session" class="input mono" type="text" placeholder="sess_…" bind:value={sessionFilter} />
  </div>
  <div>
    <label class="field-label" for="ev-type">Event type</label>
    <input id="ev-type" class="input" type="text" placeholder="Filter by type…" bind:value={typeFilter} />
  </div>
  <div>
    <label class="field-label" for="ev-limit">Limit</label>
    <select id="ev-limit" class="select" bind:value={limit}>
      <option value="50">50</option>
      <option value="100">100</option>
      <option value="250">250</option>
      <option value="500">500</option>
    </select>
  </div>
  <button type="submit" class="btn btn-sm apply">Apply</button>
</form>

{#if loadError}
  <PageState state="error" title="Couldn't load events" detail={loadError} />
{:else if events === null}
  <PageState state="loading" title="Loading events…" />
{:else if events.length === 0}
  <div class="card">
    <EmptyState icon="activity" title="No events match" body="Adjust the filters or run a turn first." />
  </div>
{:else}
  <div class="card list-card">
    <table class="table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Actor</th>
          <th>Risk</th>
          <th>Summary</th>
          <th>Session / turn</th>
          <th>When</th>
        </tr>
      </thead>
      <tbody>
        {#each events as ev (ev.event_id)}
          <tr>
            <td title={ev.event_type}>{humanize(ev.event_type)}</td>
            <td class="actor">
              {#if ev.machine_identity}
                <IdentityChip identity={ev.machine_identity} />
              {:else}
                <span class="mono">{ev.actor}</span>
              {/if}
            </td>
            <td>
              <span class={`risk ${riskTone(ev.risk_level)}`}>{ev.risk_level ?? "—"}</span>
            </td>
            <td class="summary-cell">{ev.summary ?? "—"}</td>
            <td class="mono ids">
              {shortId(ev.session_id)}{ev.turn_id ? ` · ${shortId(ev.turn_id)}` : ""}
            </td>
            <td title={ev.timestamp}>{relativeTime(ev.timestamp)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  @media (max-width: 720px) {
    .head-row {
      flex-direction: column;
    }
  }
  .filters {
    display: flex;
    align-items: flex-end;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
  }
  .apply {
    margin-bottom: 2px;
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .summary-cell {
    max-width: 26rem;
  }
  .actor,
  .ids {
    font-size: 0.78rem;
    color: var(--text-2);
    white-space: nowrap;
  }
  .risk {
    font-size: 0.76rem;
    font-weight: 600;
    border-radius: var(--r-pill);
    padding: 0.05rem 0.5rem;
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
  }
  .risk-high {
    border-color: var(--danger-border);
    background: var(--danger-soft);
    color: var(--danger);
  }
  .risk-med {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
</style>
