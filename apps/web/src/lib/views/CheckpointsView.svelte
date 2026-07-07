<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { Checkpoint } from "../apiTypes";
  import { humanize, relativeTime, shortId } from "../format";

  let checkpoints = $state<Checkpoint[] | null>(null);
  let loadError = $state<string | null>(null);
  let sessionFilter = $state("");

  async function load() {
    loadError = null;
    try {
      checkpoints = await api.checkpoints(sessionFilter.trim() || undefined);
    } catch (e) {
      checkpoints = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    Rewind metadata recorded at safe points in every session. Restore flags are metadata only —
    restore execution is not implemented in this runtime, so nothing here can change state.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh checkpoints">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

<form
  class="filter-row"
  onsubmit={(e) => {
    e.preventDefault();
    void load();
  }}
>
  <label class="field-label" for="cp-session">Filter by session id</label>
  <div class="filter-controls">
    <input id="cp-session" class="input mono" type="text" placeholder="sess_…" bind:value={sessionFilter} />
    <button type="submit" class="btn btn-sm">Apply</button>
  </div>
</form>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if checkpoints === null}
  <p class="loading">Loading…</p>
{:else if checkpoints.length === 0}
  <div class="card">
    <EmptyState icon="checkpoints" title="No checkpoints" body="Checkpoints are recorded as sessions run." />
  </div>
{:else}
  <div class="card list-card">
    <table class="table">
      <thead>
        <tr>
          <th>Checkpoint</th>
          <th>Type</th>
          <th>Session</th>
          <th>Summary</th>
          <th>Restore</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        {#each checkpoints as cp (cp.checkpoint_id)}
          <tr>
            <td class="mono">{shortId(cp.checkpoint_id)}</td>
            <td>{humanize(cp.checkpoint_type)}</td>
            <td class="mono">{shortId(cp.session_id)}</td>
            <td class="summary-cell">{cp.summary ?? "—"}</td>
            <td>
              <span class="restore-flags">
                <Badge
                  variant={cp.can_restore_state ? "metadata-only" : "disabled"}
                  label={cp.can_restore_state ? "state" : "no state"}
                />
                <Badge
                  variant={cp.can_restore_files ? "metadata-only" : "disabled"}
                  label={cp.can_restore_files ? "files" : "no files"}
                />
              </span>
            </td>
            <td title={cp.created_at}>{relativeTime(cp.created_at)}</td>
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
  .filter-row {
    margin-bottom: var(--space-4);
  }
  .filter-controls {
    display: flex;
    gap: 0.5rem;
  }
  .filter-controls .input {
    max-width: 20rem;
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .summary-cell {
    max-width: 24rem;
  }
  .restore-flags {
    display: inline-flex;
    gap: 0.3rem;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
