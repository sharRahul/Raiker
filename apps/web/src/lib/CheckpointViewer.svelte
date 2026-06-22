<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "./api";
  import type { Checkpoint } from "./apiTypes";
  import Badge from "./Badge.svelte";

  let checkpoints = $state<Checkpoint[] | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      checkpoints = await api.checkpoints();
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  });
</script>

<h1 id="page-title">Checkpoints</h1>
<p class="lead">Checkpoint metadata. Rewind is metadata-only in this runtime (restore is not executed).</p>

{#if error}
  <p class="state-error">Checkpoints unavailable: {error}</p>
{:else if checkpoints === null}
  <p class="state-loading">Loading checkpoints…</p>
{:else if checkpoints.length === 0}
  <p class="state-empty">No checkpoints yet.</p>
{:else}
  <ul class="ckpts">
    {#each checkpoints as ckpt (ckpt.checkpoint_id)}
      <li>
        <code class="cid">{ckpt.checkpoint_id}</code>
        <span class="meta">session <code>{ckpt.session_id}</code> · turn <code>{ckpt.turn_id ?? "—"}</code> · {ckpt.created_at}</span>
        <span class="rewind">
          <Badge variant="metadata-only" />
          <span class="flags">restore-state: {ckpt.can_restore_state ? "metadata" : "no"} · restore-files: {ckpt.can_restore_files ? "metadata" : "no"}</span>
        </span>
        {#if ckpt.summary}<span class="summary">{ckpt.summary}</span>{/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .lead {
    color: #c2c2c9;
  }
  .ckpts {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .ckpts li {
    border: 1px solid #2a2a2e;
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    background: #101013;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    align-items: center;
  }
  .cid {
    color: #cfe5ff;
  }
  .meta,
  .flags {
    color: #8b8b93;
    font-size: 0.78rem;
  }
  .summary {
    color: #b6b6bd;
    font-size: 0.82rem;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading,
  .state-empty {
    color: #9a9aa2;
  }
</style>
