<script lang="ts">
  /**
   * REM-MEM-03 — the recall engine's controls, out of the personal review.
   *
   * Memory's job is the owner's own facts: what Raiker has been allowed to
   * remember, what is waiting on a decision, what has expired. Which embedding
   * space recall searches, and building one, are neither — they are engine
   * configuration, and they sat on the same page as an owner reading back
   * sentences about themselves.
   *
   * Memory keeps what an owner needs there: whether recall is matching meaning
   * or only words, and the link to this page when it is not what they want.
   * Nothing is duplicated — this page and that sentence read the same settings.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { MemorySettingsView } from "../../apiTypes";
  import PageState from "../../components/PageState.svelte";
  import Icon from "../../components/Icon.svelte";

  let settings = $state<MemorySettingsView | null>(null);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state(false);
  let indexProvider = $state("");
  let indexResult = $state<string | null>(null);

  const providers = $derived(settings?.embedding_providers ?? []);
  const indexTarget = $derived(providers.find((provider) => provider.space === indexProvider) ?? null);
  const pending = $derived(providers.some((provider) => (provider.pending_count ?? 0) > 0));

  async function load(): Promise<void> {
    try {
      loadError = null;
      settings = await api.memorySettings();
    } catch (error) {
      settings = null;
      loadError = error instanceof ApiError ? error.message : "Memory settings are unavailable.";
    }
  }

  // MEM-03 — recall searches exactly one embedding space. Reloading rather than
  // assuming is what keeps this page from claiming a backend it did not confirm.
  async function chooseBackend(backend: string): Promise<void> {
    busy = true;
    actionError = null;
    try {
      await api.setMemoryEmbeddingBackend(backend);
      await load();
    } catch (error) {
      actionError =
        error instanceof ApiError
          ? `Could not change the recall backend (${error.status}).`
          : "Could not change the recall backend.";
    } finally {
      busy = false;
    }
  }

  // A governed run that sends each approved memory to the named embedding model.
  // The count and the destination are both stated before the owner confirms,
  // because the text really does leave the machine when the model is hosted.
  async function buildIndex(): Promise<void> {
    if (!indexTarget || busy) return;
    const waiting = indexTarget.unindexed_memories ?? 0;
    const waitingFiles = indexTarget.unindexed_file_chunks ?? 0;
    const where = indexTarget.local_only ? "on this machine" : `to ${indexTarget.provider}`;
    const question =
      `${indexTarget.local_only ? "Process" : "Send"} ${waiting} approved ` +
      `${waiting === 1 ? "memory" : "memories"} and ${waitingFiles} managed document ` +
      `${waitingFiles === 1 ? "passage" : "passages"} ${where} to be embedded as ` +
      `${indexTarget.model}? Secret-like or credential-like content is never embedded.`;
    if (!window.confirm(question)) return;
    busy = true;
    actionError = null;
    indexResult = null;
    try {
      const result = await api.buildMemoryEmbeddingIndex(indexTarget.provider, indexTarget.model);
      indexResult = `Embedded ${result.indexed_count} memories and ${result.indexed_file_chunk_count ?? 0} document passages into ${result.embedding_model}.`;
      await load();
    } catch (error) {
      actionError =
        error instanceof ApiError ? `The index could not be built (${error.status}).` : "The index could not be built.";
    } finally {
      busy = false;
    }
  }

  onMount(load);
</script>

<section class="memory-engine">
  <header class="section-heading">
    <h2>Memory engine</h2>
    <p>
      Which space recall searches, and how one gets built. What Raiker is allowed to
      remember is <a href="#/memory">Memory</a>; this is the machinery behind it.
    </p>
  </header>

  {#if loadError}
    <PageState state="error" title="Couldn't load the memory engine" detail={loadError} />
  {:else if !settings}
    <PageState state="loading" title="Loading…" />
  {:else}
    {#if actionError}<p class="notice notice-danger" role="alert">{actionError}</p>{/if}

    <div class="card">
      <h3>Recall backend</h3>
      <p class="lead">
        Recall searches exactly one embedding space. <strong>Automatic</strong> uses the
        best space that holds vectors; naming one pins it.
      </p>
      <label class="field">
        <span class="field-label">Space to search</span>
        <select
          class="select"
          aria-label="Recall backend"
          value={settings.embedding_backend ?? "auto"}
          disabled={busy}
          onchange={(event) => void chooseBackend(event.currentTarget.value)}
        >
          <option value="auto">Automatic</option>
          {#each settings.spaces ?? [] as space (space.model)}
            <option value={space.model}>{space.model} · {space.dimensions}d</option>
          {/each}
        </select>
      </label>
      {#if settings.vector_search_strategy === "exact_then_approximate"}
        <p class="note">
          Ranks {settings.vector_search_exact_limit ?? 512} vectors exactly, then approximates.
        </p>
      {/if}
    </div>

    <div class="card">
      <h3>Build a meaning-based index</h3>
      <!-- MEM-10 — the select above can only offer spaces that already hold
           vectors, so on a default install it offers the fallback and nothing
           else. This is the way out of that: it builds one. -->
      {#if pending}
        <p class="lead">
          Sends each approved memory to the embedding model you name. Nothing is sent
          anywhere a local model is chosen.
        </p>
        <div class="index-row">
          <label class="field">
            <span class="sr-only">Embedding model to build with</span>
            <select class="select" aria-label="Embedding model" bind:value={indexProvider} disabled={busy}>
              <option value="">Choose an embedding model…</option>
              {#each providers as provider (provider.space)}
                <option value={provider.space}
                  >{provider.model} · {provider.local_only ? "on this machine" : provider.provider}</option
                >
              {/each}
            </select>
          </label>
          <button
            class="btn btn-primary"
            type="button"
            disabled={busy || !indexTarget || !(indexTarget.pending_count ?? 0)}
            onclick={() => void buildIndex()}>Embed {indexTarget?.pending_count ?? 0}</button
          >
        </div>
        {#if providers.some((provider) => provider.provider === "llama.cpp")}
          <p class="note">
            <Icon name="download" size="sm" />
            <span>
              Need a local embedding model? The curated Apache-2.0 Nomic Embed Q4_K_M
              option is about 81 MiB.
              <a href="#/models?tab=add">Review and download it in Models</a>; Raiker pins
              the revision and shows the exact bytes before download.
            </span>
          </p>
        {/if}
        {#if indexResult}
          <p class="note" role="status"><Icon name="check" size="sm" /><span>{indexResult}</span></p>
        {/if}
      {:else}
        <p class="lead">
          Nothing is waiting to be embedded. Every approved memory is already in a space
          recall can search.
        </p>
      {/if}
    </div>
  {/if}
</section>

<style>
  .section-heading h2 { margin: 0; }
  .section-heading p { color: var(--text-2); margin: 0.3rem 0 var(--space-5); }
  .card { margin-bottom: var(--space-4); }
  .card h3 { margin: 0 0 0.3rem; font-size: var(--text-lg); }
  .lead { color: var(--text-2); font-size: var(--text-sm); margin: 0 0 var(--space-3); }
  .field { display: grid; gap: 0.35rem; min-width: 0; }
  .field-label { color: var(--text-2); font-size: var(--text-sm); }
  .field select { width: 100%; min-width: 0; max-width: 24rem; }
  /* `min-width: 0` lets the label shrink; a select still claims the width of
     its longest option unless it is told otherwise (BUG-284). */
  .index-row { display: flex; gap: var(--space-2); align-items: end; flex-wrap: wrap; }
  .index-row .field { flex: 1 1 16rem; }
  .note { display: flex; align-items: baseline; gap: 0.4rem; color: var(--text-2);
    font-size: var(--text-sm); margin: var(--space-2) 0 0; }
  .note :global(svg) { flex: none; align-self: center; color: var(--text-3); }
</style>
