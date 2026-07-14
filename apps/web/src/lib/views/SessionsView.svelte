<script lang="ts">
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { SessionDetail, SessionSummary, TurnDetail } from "../apiTypes";
  import { responseBadge } from "../statusMaps";
  import { humanize, relativeTime, shortId } from "../format";

  // When a project is active (topbar switcher) the list is scoped to it.
  let { projectId = null }: { projectId?: string | null } = $props();

  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);

  let detail = $state<SessionDetail | null>(null);
  let detailError = $state<string | null>(null);

  let turnDetail = $state<TurnDetail | null>(null);
  let turnError = $state<string | null>(null);

  // Conversation organisation: multi-select for bulk delete, plus a per-row
  // pin toggle. Pinned sessions surface first. These are organizing actions
  // only — they grant nothing and change no authority.
  let selected = $state<Set<string>>(new Set());
  let actionError = $state<string | null>(null);
  let deleting = $state(false);

  // Pinned sessions first, then most-recently-updated. The sort is display-only
  // — the backend list order is unchanged.
  const ordered = $derived(
    sessions === null
      ? null
      : [...sessions].sort((a, b) => {
          if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
          return b.updated_at.localeCompare(a.updated_at);
        }),
  );

  function toggleSelected(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected = next;
  }

  async function togglePin(s: SessionSummary) {
    actionError = null;
    try {
      await api.setSessionPinned(s.session_id, !s.pinned);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not update pin (${e.status}).` : "Could not update pin.";
    }
  }

  async function deleteOne(id: string) {
    if (!window.confirm("Delete this conversation permanently? Its turns and governed events will be removed.")) return;
    actionError = null;
    deleting = true;
    try {
      await api.deleteSession(id);
      if (detail?.session.session_id === id) detail = null;
      selected = new Set([...selected].filter((x) => x !== id));
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not delete (${e.status}).` : "Could not delete.";
    } finally {
      deleting = false;
    }
  }

  async function deleteSelected() {
    if (selected.size === 0) return;
    if (
      !window.confirm(
        `Delete ${selected.size} conversation${selected.size === 1 ? "" : "s"} permanently? Their turns and governed events will be removed.`,
      )
    )
      return;
    actionError = null;
    deleting = true;
    let failed = 0;
    for (const id of [...selected]) {
      try {
        await api.deleteSession(id);
        if (detail?.session.session_id === id) detail = null;
      } catch {
        failed += 1;
      }
    }
    selected = new Set();
    deleting = false;
    if (failed > 0) {
      actionError = `${failed} conversation${failed === 1 ? "" : "s"} could not be deleted.`;
    }
    await load();
  }

  async function load() {
    loadError = null;
    try {
      sessions = await api.sessions(projectId ?? undefined);
      // Drop any selection that no longer exists after a refresh.
      const ids = new Set((sessions ?? []).map((s) => s.session_id));
      selected = new Set([...selected].filter((id) => ids.has(id)));
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

  // Load on mount and again whenever the active project changes.
  $effect(() => {
    void projectId;
    void load();
  });
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
  {#if selected.size > 0}
    <div class="bulk-bar" role="toolbar" aria-label="Bulk actions">
      <span class="bulk-count">{selected.size} selected</span>
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        onclick={() => (selected = new Set())}
        disabled={deleting}
      >
        Clear
      </button>
      <button
        type="button"
        class="btn btn-danger btn-sm"
        onclick={deleteSelected}
        disabled={deleting}
      >
        <Icon name="x" size={14} />
        {deleting ? "Deleting…" : "Delete selected"}
      </button>
    </div>
  {/if}
  {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}

  <div class="layout">
    <div class="card list-card">
      <table class="table">
        <thead>
          <tr>
            <th class="check-col"></th>
            <th>Session</th>
            <th>Status</th>
            <th>Turns</th>
            <th>Updated</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each ordered as s (s.session_id)}
            <tr
              class="row-btn"
              class:selected={detail?.session.session_id === s.session_id}
            >
              <td class="check-col" onclick={() => toggleSelected(s.session_id)}>
                <input
                  type="checkbox"
                  checked={selected.has(s.session_id)}
                  aria-label={`Select ${s.title ?? shortId(s.session_id)}`}
                />
              </td>
              <td onclick={() => openSession(s.session_id)}>
                <span class="session-title">
                  {#if s.pinned}<span class="pin-mark" title="Pinned" aria-label="Pinned">★</span>{/if}
                  {s.title ?? shortId(s.session_id)}
                </span>
                <span class="mono sub">{shortId(s.session_id)}</span>
              </td>
              <td onclick={() => openSession(s.session_id)}><Badge variant={s.status === "active" ? "active" : "idle"} label={s.status} /></td>
              <td onclick={() => openSession(s.session_id)}>{s.turn_count}</td>
              <td onclick={() => openSession(s.session_id)} title={s.updated_at}>{relativeTime(s.updated_at)}</td>
              <td class="row-actions">
                <button
                  type="button"
                  class="icon-btn"
                  class:pinned={s.pinned}
                  onclick={() => void togglePin(s)}
                  aria-label={s.pinned ? "Unpin session" : "Pin session"}
                  title={s.pinned ? "Unpin" : "Pin to top"}
                >★</button>
                <button
                  type="button"
                  class="icon-btn danger"
                  onclick={() => void deleteOne(s.session_id)}
                  aria-label="Delete session"
                  title="Delete conversation"
                  disabled={deleting}
                >🗑</button>
              </td>
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
  .bulk-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: var(--space-3);
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--warn-border);
    background: var(--warn-soft);
    border-radius: var(--r-sm);
    flex-wrap: wrap;
  }
  .bulk-count {
    font-weight: 650;
    font-size: 0.86rem;
    margin-right: auto;
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
  .table .check-col {
    width: 2rem;
  }
  .row-btn {
    cursor: pointer;
  }
  .row-btn.selected {
    background: var(--accent-soft);
  }
  .row-btn > td {
    cursor: pointer;
  }
  .row-actions,
  .check-col {
    cursor: default;
  }
  .session-title {
    display: block;
    font-weight: 600;
  }
  .pin-mark {
    color: var(--accent);
    margin-right: 0.2rem;
  }
  .icon-btn {
    border: 1px solid transparent;
    background: none;
    color: var(--text-3);
    cursor: pointer;
    font-size: 0.95rem;
    line-height: 1;
    padding: 0.15rem 0.3rem;
    border-radius: var(--r-sm);
  }
  .icon-btn:hover:not(:disabled) {
    background: var(--neutral-soft);
    color: var(--text-1);
  }
  .icon-btn.pinned {
    color: var(--accent);
  }
  .icon-btn.danger:hover:not(:disabled) {
    color: var(--danger);
    background: var(--danger-soft);
  }
  .row-actions {
    display: flex;
    gap: 0.15rem;
    white-space: nowrap;
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
