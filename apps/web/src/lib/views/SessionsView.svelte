<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { SessionDetail, SessionSummary, TurnDetail } from "../apiTypes";
  import { responseBadge } from "../statusMaps";
  import { humanize, relativeTime, shortId } from "../format";

  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);

  let detail = $state<SessionDetail | null>(null);
  let detailError = $state<string | null>(null);

  let turnDetail = $state<TurnDetail | null>(null);
  let turnError = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      sessions = await api.sessions();
    } catch (e) {
      sessions = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function openSession(id: string) {
    detailError = null;
    turnDetail = null;
    turnError = null;
    try {
      detail = await api.session(id);
    } catch (e) {
      detail = null;
      detailError = e instanceof ApiError ? `Could not load session (${e.status}).` : "Could not load session.";
    }
  }

  async function openTurn(id: string) {
    turnError = null;
    try {
      turnDetail = await api.turn(id);
    } catch (e) {
      turnDetail = null;
      turnError = e instanceof ApiError ? `Could not load turn (${e.status}).` : "Could not load turn.";
    }
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    Every conversation with the runtime, with its turns and the governed events behind each turn.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh sessions">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if sessions === null}
  <p class="loading">Loading…</p>
{:else if sessions.length === 0}
  <div class="card">
    <EmptyState icon="sessions" title="No sessions yet" body="Start a chat to create your first governed session." />
  </div>
{:else}
  <div class="layout">
    <div class="card list-card">
      <table class="table">
        <thead>
          <tr>
            <th>Session</th>
            <th>Status</th>
            <th>Turns</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {#each sessions as s (s.session_id)}
            <tr
              class="row-btn"
              class:selected={detail?.session.session_id === s.session_id}
              onclick={() => openSession(s.session_id)}
            >
              <td>
                <span class="session-title">{s.title ?? shortId(s.session_id)}</span>
                <span class="mono sub">{shortId(s.session_id)}</span>
              </td>
              <td><Badge variant={s.status === "active" ? "active" : "idle"} label={s.status} /></td>
              <td>{s.turn_count}</td>
              <td title={s.updated_at}>{relativeTime(s.updated_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="detail-col">
      {#if detailError}
        <p class="error" role="alert">{detailError}</p>
      {:else if detail !== null}
        <section class="card" aria-labelledby="session-detail-h">
          <h2 id="session-detail-h">{detail.session.title ?? shortId(detail.session.session_id)}</h2>
          <p class="sub">Created {relativeTime(detail.session.created_at)} · {detail.turns.length} turns</p>
          <ol class="turns">
            {#each detail.turns as t (t.turn_id)}
              <li>
                <button type="button" class="turn-btn" onclick={() => openTurn(t.turn_id)}>
                  <span class="turn-prompt">{t.prompt_text ?? t.turn_type}</span>
                  <Badge variant={responseBadge(t.status)} label={t.status} />
                </button>
              </li>
            {/each}
          </ol>
        </section>
      {/if}

      {#if turnError}
        <p class="error" role="alert">{turnError}</p>
      {:else if turnDetail !== null}
        <section class="card" aria-labelledby="turn-detail-h">
          <div class="turn-head">
            <h3 id="turn-detail-h">Turn {shortId(turnDetail.turn.turn_id)}</h3>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => (turnDetail = null)}>
              <Icon name="x" size={14} />
              Close
            </button>
          </div>
          {#if turnDetail.turn.prompt_text}
            <p class="prompt-text">{turnDetail.turn.prompt_text}</p>
          {/if}
          {#if turnDetail.turn.summary}
            <p class="sub">{turnDetail.turn.summary}</p>
          {/if}
          <h4 class="kicker">Governed events</h4>
          {#if turnDetail.events.length === 0}
            <p class="sub">No indexed events for this turn.</p>
          {:else}
            <ul class="events">
              {#each turnDetail.events as ev (ev.event_id)}
                <li>
                  <span class="ev-type">{humanize(ev.event_type)}</span>
                  <span class="ev-summary">{ev.summary ?? ""}</span>
                  <span class="ev-time" title={ev.timestamp}>{relativeTime(ev.timestamp)}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {/if}
    </div>
  </div>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(20rem, 5fr) minmax(20rem, 6fr);
    gap: var(--space-4);
    align-items: start;
  }
  @media (max-width: 1100px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .row-btn {
    cursor: pointer;
  }
  .row-btn.selected {
    background: var(--accent-soft);
  }
  .session-title {
    display: block;
    font-weight: 600;
  }
  .sub {
    color: var(--text-3);
    font-size: 0.78rem;
  }
  .detail-col {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  .turns {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .turn-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    width: 100%;
    text-align: left;
    font: inherit;
    font-size: 0.86rem;
    color: var(--text-1);
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.45rem 0.65rem;
    cursor: pointer;
  }
  .turn-btn:hover {
    border-color: var(--accent-border);
  }
  .turn-prompt {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .turn-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .prompt-text {
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    border-radius: var(--r-sm);
    padding: 0.5rem 0.7rem;
    font-size: 0.88rem;
  }
  .events {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.82rem;
  }
  .events li {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
    border-bottom: 1px dashed var(--border);
    padding-bottom: 0.3rem;
  }
  .ev-type {
    font-weight: 600;
    color: var(--text-1);
    white-space: nowrap;
  }
  .ev-summary {
    color: var(--text-2);
    flex: 1;
  }
  .ev-time {
    color: var(--text-3);
    font-size: 0.74rem;
    white-space: nowrap;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
