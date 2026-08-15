<script lang="ts">
  import Icon from "../components/Icon.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import SidePanel from "../components/SidePanel.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type { Checkpoint, RestorePlan } from "../apiTypes";
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

  // ── Restore preflight ────────────────────────────────────────────────
  // Restoring to a checkpoint is deliberately a funnel, not a button. Step one
  // reads a server-computed, metadata-only plan: which files would be rewritten,
  // deleted, or skipped, and whether any of them were last changed by another
  // principal. Reading the plan performs no restore, and this view never claims
  // one happened — execution belongs to the governed approval path.
  let planFor = $state<Checkpoint | null>(null);
  let plan = $state<RestorePlan | null>(null);
  let planError = $state<string | null>(null);
  let planBusy = $state(false);
  let acknowledged = $state(false);

  const escalates = $derived(plan?.touches_other_principal === true);

  async function openPreflight(checkpoint: Checkpoint) {
    planFor = checkpoint;
    plan = null;
    planError = null;
    acknowledged = false;
    planBusy = true;
    try {
      plan = await api.checkpointRestorePlan(checkpoint.checkpoint_id);
    } catch (e) {
      planError =
        e instanceof ApiError
          ? `Could not compute the restore plan (${e.status}).`
          : "Could not compute the restore plan.";
    } finally {
      planBusy = false;
    }
  }

  function closePreflight() {
    planFor = null;
    plan = null;
    planError = null;
    acknowledged = false;
  }

  function opLabel(op: string): string {
    if (op === "restore_content") return "Rewrite to its checkpoint state";
    if (op === "delete") return "Delete — it did not exist at the checkpoint";
    return "Skipped — too large to have been captured";
  }

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
  <GuideLink route="checkpoints" />
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
              <button
                type="button"
                class="btn btn-sm preflight-btn"
                onclick={() => openPreflight(cp)}
                aria-label={`Preview what restoring to checkpoint ${shortId(cp.checkpoint_id)} would change`}
              >
                Preview restore impact
              </button>
            </div>
          </li>
        {/each}
      </ol>
    </section>
  {/each}
{/if}

<SidePanel
  open={planFor !== null}
  title="Restore preflight"
  subtitle={planFor ? `Checkpoint ${shortId(planFor.checkpoint_id)}` : null}
  onclose={closePreflight}
  scrollIntoViewOnOpen
>
  {#if planBusy}
    <PageState state="loading" title="Computing what a restore would change…" />
  {:else if planError}
    <PageState state="error" title="Preflight unavailable" detail={planError} />
  {:else if plan}
    <p class="preflight-lead">
      Restoring rewinds every workspace file changed after this checkpoint back to the state it had
      then. Reading this plan changed nothing — it is a preview computed from stored metadata.
    </p>
    <div class="impact">
      <span><strong>{plan.restore_content_count}</strong> to rewrite</span>
      <span><strong>{plan.delete_count}</strong> to delete</span>
      <span><strong>{plan.skip_count}</strong> skipped</span>
      <span><strong>{plan.changed_count}</strong> changed since</span>
    </div>

    {#if plan.files.length === 0}
      <p class="quiet">
        No captured file changes after this checkpoint, so a restore would rewind nothing.
      </p>
    {:else}
      <ul class="affected">
        {#each plan.files as file (file.workspace_path)}
          <li class:changed={file.changed}>
            <span class="path mono">{file.workspace_path}</span>
            <span class="op">{opLabel(file.op)}</span>
            {#if file.changed_by_other_principal}
              <span class="escalation">Last changed by a different principal</span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if escalates}
      <div class="notice notice-danger" role="alert">
        <Icon name="warning" size={16} />
        <span>
          This restore would overwrite work last changed by a different principal. That is a
          cross-principal escalation and the runtime requires an explicit approval for it.
        </span>
      </div>
    {/if}

    <div class="undo-facts">
      <h3>Before you ask for this</h3>
      <ul>
        <li>The restore itself is captured, so it can be rewound the same way.</li>
        <li>Skipped files are left exactly as they are — they were never captured.</li>
        <li>
          Every step is written to the append-only record.
          <a href={`#/observe?tab=activity&session=${encodeURIComponent(plan.session_id)}`}>
            Open this session's audit log
          </a>
        </li>
      </ul>
    </div>

    <label class="ack">
      <input type="checkbox" bind:checked={acknowledged} />
      I have read what this would change.
    </label>
    <p class="handoff" class:ready={acknowledged}>
      {acknowledged
        ? "Ask for the restore in the conversation that owns this work. The runtime raises it as a governed approval, and it only runs once you approve it there."
        : "Confirm you have read the impact above to see how to request the restore."}
    </p>
    <p class="quiet">
      This panel cannot start a restore. Raiker never executes one from a read-only view.
    </p>
  {/if}
</SidePanel>

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
  .preflight-btn {
    margin-top: var(--space-3);
  }
  .preflight-lead {
    margin: 0;
    color: var(--text-2);
  }
  .impact {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    font-size: 0.8rem;
    color: var(--text-2);
  }
  .impact strong {
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
  }
  .affected {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
    max-height: 16rem;
    overflow: auto;
  }
  .affected li {
    display: grid;
    gap: 0.1rem;
    border-left: 2px solid var(--border);
    padding: 0.2rem 0 0.2rem 0.55rem;
  }
  .affected li.changed {
    border-left-color: var(--warn);
  }
  .path {
    overflow-wrap: anywhere;
    font-size: 0.78rem;
  }
  .op {
    color: var(--text-3);
    font-size: 0.75rem;
  }
  .escalation {
    color: var(--danger);
    font-size: 0.75rem;
    font-weight: 650;
  }
  .undo-facts h3 {
    margin: 0 0 0.3rem;
    font-size: 0.82rem;
  }
  .undo-facts ul {
    margin: 0;
    padding-left: 1.1rem;
    color: var(--text-2);
    font-size: 0.8rem;
    display: grid;
    gap: 0.2rem;
  }
  .ack {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.84rem;
    font-weight: 600;
  }
  .handoff {
    margin: 0;
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .handoff.ready {
    color: var(--text-1);
  }
  .quiet {
    color: var(--text-3);
    font-size: 0.78rem;
    margin: 0;
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
