<script lang="ts">
  import Icon from "../components/Icon.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { Checkpoint } from "../apiTypes";
  import { humanize, relativeTime, shortId } from "../format";

  // When a project is active (topbar switcher) the list is scoped to it.
  let { projectId = null, sessionId = null }: { projectId?: string | null; sessionId?: string | null } = $props();

  let checkpoints = $state<Checkpoint[] | null>(null);
  let loadError = $state<string | null>(null);
  let sessionFilter = $state("");
  let typeFilter = $state("");
  let loadedSessionId = $state<string | null | undefined>(undefined);
  let loadedProjectId = $state<string | null | undefined>(undefined);

  // The recorder timeline groups snapshots under the session that produced
  // them, newest session first, entries in recorded order.
  const groups = $derived.by(() => {
    if (checkpoints === null) return [];
    const filtered = typeFilter
      ? checkpoints.filter((cp) => cp.checkpoint_type === typeFilter)
      : checkpoints;
    const bySession = new Map<string, Checkpoint[]>();
    for (const cp of filtered) {
      const list = bySession.get(cp.session_id) ?? [];
      list.push(cp);
      bySession.set(cp.session_id, list);
    }
    return [...bySession.entries()].map(([sessionId, items]) => ({
      sessionId,
      items: [...items].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    }));
  });

  const types = $derived(
    checkpoints === null ? [] : [...new Set(checkpoints.map((cp) => cp.checkpoint_type))].sort(),
  );

  async function load() {
    loadError = null;
    try {
      checkpoints = await api.checkpoints(sessionFilter.trim() || undefined, projectId ?? undefined);
    } catch (e) {
      checkpoints = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  // Reload when the route scope changes, but leave a manually edited filter
  // alone until the user applies it.
  $effect(() => {
    const sessionChanged = sessionId !== loadedSessionId;
    const projectChanged = projectId !== loadedProjectId;
    if (!sessionChanged && !projectChanged) return;
    loadedSessionId = sessionId;
    loadedProjectId = projectId;
    if (sessionChanged) sessionFilter = sessionId ?? "";
    void load();
  });
</script>

<div class="head-row">
  <p class="page-lead">
    The recorder timeline: metadata snapshots taken at safe points as sessions run. Nothing here
    executes a restore — every entry is a record of where the runtime stood, not a lever.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh checkpoints">
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
    <label class="field-label" for="cp-session">Filter by session id</label>
    <input id="cp-session" class="input mono" type="text" placeholder="sess_…" bind:value={sessionFilter} />
  </div>
  <div>
    <label class="field-label" for="cp-type">Filter by type</label>
    <select id="cp-type" class="select" bind:value={typeFilter}>
      <option value="">All types</option>
      {#each types as t (t)}
        <option value={t}>{humanize(t)}</option>
      {/each}
    </select>
  </div>
  <button type="submit" class="btn btn-sm apply">Apply</button>
</form>

{#if loadError}
  <PageState state="error" title="Couldn't load checkpoints" detail={loadError} />
{:else if checkpoints === null}
  <PageState state="loading" title="Loading checkpoints…" />
{:else if groups.length === 0}
  <div class="card">
    <EmptyState icon="checkpoints" title="No checkpoints" body="Checkpoints are recorded as sessions run." />
  </div>
{:else}
  {#each groups as group (group.sessionId)}
    <section class="session-group" aria-label={`Checkpoints for session ${group.sessionId}`}>
      <h2 class="session-head">
        <Icon name="sessions" size={14} />
        <span>Session</span>
        <span class="mono">{shortId(group.sessionId)}</span>
        <span class="count">{group.items.length} snapshot{group.items.length === 1 ? "" : "s"}</span>
      </h2>
      <ol class="timeline">
        {#each group.items as cp (cp.checkpoint_id)}
          <li class="entry">
            <span class="marker" aria-hidden="true"></span>
            <div class="entry-body card">
              <div class="entry-head">
                <strong>{humanize(cp.checkpoint_type)}</strong>
                <span class="badge-metadata">Snapshot metadata only</span>
                <span class="when" title={cp.created_at}>{relativeTime(cp.created_at)}</span>
              </div>
              {#if cp.summary}<p class="summary">{cp.summary}</p>{/if}
              <dl class="context">
                {#if cp.turn_id}<div><dt>Turn</dt><dd class="mono">{shortId(cp.turn_id)}</dd></div>{/if}
                {#if cp.task_id}<div><dt>Task</dt><dd class="mono">{shortId(cp.task_id)}</dd></div>{/if}
                {#if cp.last_event_id}<div><dt>Last event</dt><dd class="mono">{shortId(cp.last_event_id)}</dd></div>{/if}
                <div>
                  <dt>Recorded</dt>
                  <dd>
                    {cp.can_restore_state ? "state" : "no state"} · {cp.can_restore_files ? "files" : "no files"}
                  </dd>
                </div>
              </dl>
            </div>
          </li>
        {/each}
      </ol>
    </section>
  {/each}
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .filters {
    display: flex;
    align-items: flex-end;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-4);
  }
  .filters .input {
    max-width: 18rem;
  }
  .apply {
    margin-bottom: 2px;
  }
  .session-group {
    margin-bottom: var(--space-5);
  }
  .session-head {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    font-size: 0.86rem;
    color: var(--text-2);
    margin: 0 0 var(--space-3);
  }
  .session-head .mono {
    color: var(--text-1);
  }
  .count {
    font-size: 0.76rem;
    font-weight: 500;
    color: var(--text-3);
  }
  .timeline {
    list-style: none;
    margin: 0;
    padding: 0 0 0 1.1rem;
    display: grid;
    gap: var(--space-3);
    border-left: 2px solid var(--border);
  }
  .entry {
    position: relative;
  }
  .marker {
    position: absolute;
    left: calc(-1.1rem - 6px);
    top: 1.05rem;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--bg);
  }
  .entry-body {
    padding: var(--space-3) var(--space-4);
  }
  .entry-head {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .badge-metadata {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--info);
    background: var(--info-soft);
    border: 1px solid var(--info-border);
    border-radius: var(--r-pill);
    padding: 0.05rem 0.55rem;
    white-space: nowrap;
  }
  .when {
    margin-left: auto;
    font-size: 0.76rem;
    color: var(--text-3);
    white-space: nowrap;
  }
  .summary {
    margin: 0.4rem 0 0;
    color: var(--text-2);
    font-size: 0.88rem;
  }
  .context {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
    margin: 0.55rem 0 0;
  }
  .context div {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
  }
  .context dt {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
  }
  .context dd {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-2);
  }
  @media (max-width: 720px) {
    .head-row {
      flex-direction: column;
    }
    .when {
      margin-left: 0;
    }
  }
</style>
