<script lang="ts">
  /**
   * BUG-305 — what Raiker can read, in one list.
   *
   * There are two kinds of source and they stay two controllers, because they
   * are genuinely different objects: a **managed file** is bytes Raiker holds,
   * copied into its own storage, and a **granted folder** is somewhere on this
   * machine Raiker may read in place. Merging the stores would mean either
   * copying a folder nobody asked to copy, or holding an upload as a path that
   * can move.
   *
   * What the owner has is one question — *what can Raiker read?* — and it had
   * two answers in two places. This is the one answer. Each row says which kind
   * it is, whether recall and the Knowledge Map can reach it, and what stopping
   * it would do: a copy Raiker made goes with it, and a folder the owner
   * granted is left exactly where it is.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { KnowledgeSource, KnowledgeSourcesView } from "../apiTypes";
  import PageState from "./PageState.svelte";
  import Icon from "./Icon.svelte";
  import { relativeTime } from "../format";

  let { onchange }: { onchange?: () => void } = $props();

  let view = $state<KnowledgeSourcesView | null>(null);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state<string | null>(null);

  const KIND_LABEL: Record<string, string> = {
    managed_file: "Kept by Raiker",
    granted_folder: "Read where it is",
  };

  async function load(): Promise<void> {
    try {
      loadError = null;
      view = await api.knowledgeSources();
    } catch (error) {
      view = null;
      loadError = error instanceof ApiError ? error.message : "Sources are unavailable.";
    }
  }

  /** What stopping this source does, said before it is done. */
  function consequence(source: KnowledgeSource): string {
    return source.held
      ? `Stop reading “${source.label}”? Raiker made this copy, so it is deleted with it. The original you imported it from is untouched.`
      : `Stop reading “${source.label}”? Raiker stops reading the folder and forgets what it indexed from it. Nothing in the folder is deleted — it is yours, and it stays where it is.`;
  }

  async function revoke(source: KnowledgeSource): Promise<void> {
    if (!window.confirm(consequence(source))) return;
    busy = source.source_id;
    actionError = null;
    try {
      await api.revokeKnowledgeSource(source.kind, source.source_id);
      await load();
      onchange?.();
    } catch (error) {
      actionError =
        error instanceof ApiError
          ? `Could not stop reading that source (${error.status}).`
          : "Could not stop reading that source.";
    } finally {
      busy = null;
    }
  }

  onMount(load);
</script>

<section class="knowledge-sources" aria-label="What Raiker can read">
  <div class="head">
    <h3>What Raiker can read</h3>
    <!-- The counts are a summary of a list, so they appear when there is a
         list. On an empty workspace "0 documents and 0 folders" above "Nothing
         yet" is the same fact twice, and the second one is the useful one. -->
    {#if view && view.sources.length > 0}
      <p class="lead">
        {view.held_count}
        {view.held_count === 1 ? "document Raiker keeps" : "documents Raiker keeps"}, and
        {view.granted_count}
        {view.granted_count === 1 ? "folder" : "folders"} it reads where they already live.
      </p>
    {/if}
  </div>

  {#if actionError}<p class="error-line" role="alert">{actionError}</p>{/if}

  {#if loadError}
    <PageState state="error" title="Couldn't read your sources" detail={loadError} />
  {:else if view === null}
    <PageState state="loading" title="Reading your sources…" />
  {:else if view.sources.length === 0}
    <p class="empty">
      Nothing yet. Add a document below, or grant a folder on the
      <a href="#/brain">Knowledge Map</a>.
    </p>
  {:else}
    <ul class="sources">
      {#each view.sources as source (source.kind + source.source_id)}
        <li data-kind={source.kind}>
          <div class="what">
            <strong>{source.label}</strong>
            <span class="where">{source.location}</span>
          </div>
          <span class="kind">{KIND_LABEL[source.kind] ?? source.kind}</span>
          <!-- Reach is stated rather than implied: a granted folder nobody has
               indexed yet is a folder Raiker may read and has not read. -->
          <span class="reach">
            {#if source.recall}<span class="on"><Icon name="check" size="sm" /> Recall</span>{/if}
            {#if source.graph}<span class="on"><Icon name="check" size="sm" /> Map</span>{/if}
            {#if !source.recall && !source.graph}<span class="off">Not indexed yet</span>{/if}
          </span>
          <span class="added" title={source.added_at}>{relativeTime(source.added_at)}</span>
          <button
            class="btn btn-ghost btn-sm"
            type="button"
            disabled={busy === source.source_id}
            onclick={() => void revoke(source)}
            aria-label={`Stop reading ${source.label}`}>Stop reading</button
          >
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .knowledge-sources { margin-bottom: var(--space-4); }
  .head h3 { margin: 0 0 0.2rem; font-size: var(--text-lg); }
  .lead, .empty { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .sources { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.4rem; }
  .sources li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto auto auto;
    align-items: center; gap: var(--space-3);
    padding: var(--row-y) var(--row-x);
    border: 1px solid var(--border); border-radius: var(--r-sm);
  }
  .what { display: grid; gap: 0.1rem; min-width: 0; }
  .where { color: var(--text-3); font-family: var(--font-mono); font-size: var(--text-xs); overflow-wrap: anywhere; }
  .kind, .added { color: var(--text-2); font-size: var(--text-xs); white-space: nowrap; }
  .reach { display: flex; gap: var(--space-2); font-size: var(--text-xs); white-space: nowrap; }
  .on { display: inline-flex; align-items: center; gap: 0.2rem; color: var(--text-2); }
  .on :global(svg) { color: var(--text-3); }
  .off { color: var(--text-3); }
  .error-line { color: var(--danger); font-size: var(--text-sm); margin: 0 0 var(--space-2); }
  @media (max-width: 52rem) {
    .sources li { grid-template-columns: minmax(0, 1fr) auto; row-gap: 0.3rem; }
    .kind, .reach, .added { grid-column: 1 / -1; }
  }
</style>
