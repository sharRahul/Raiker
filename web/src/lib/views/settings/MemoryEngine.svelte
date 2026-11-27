<script lang="ts">
  import { failure } from "../../errorCopy";
  import { askConfirm } from "../../confirm.svelte";
  // RU-11: recalled facts lead the landing view; engine configuration lives
  // under Memory Controls. Settings deep links forward there.
  import { onMount } from "svelte";
  import { api } from "../../api";
  import { providerName } from "../../format";
  import type { MemorySettingsView } from "../../apiTypes";
  import PageState from "../../components/PageState.svelte";
  import Icon from "../../components/Icon.svelte";
  import { backgroundIndexCopy } from "../../backgroundIndex";

  let { onchanged = () => {} }: { onchanged?: () => void | Promise<void> } = $props();

  let settings = $state<MemorySettingsView | null>(null);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state(false);
  let indexProvider = $state("");
  let indexResult = $state<string | null>(null);
  let localResult = $state<string | null>(null);
  let localChoice = $state("");

  const providers = $derived(settings?.embedding_providers ?? []);
  const localProviders = $derived(providers.filter((profile) => profile.local_only && !profile.requires_network));
  const localTarget = $derived(localProviders.find((profile) => profile.space === localChoice) ?? (localProviders.length === 1 ? localProviders[0] : null));
  const indexTarget = $derived(providers.find((provider) => provider.space === indexProvider) ?? null);
  const pending = $derived(providers.some((provider) => (provider.pending_count ?? 0) > 0));
  const background = $derived(backgroundIndexCopy(settings?.background_index));

  async function load(): Promise<void> {
    try {
      loadError = null;
      settings = await api.memorySettings();
    } catch (error) {
      settings = null;
      loadError = failure("Memory settings could not be read", "Nothing was changed.", "Reopen this section to read them again.", error);
    }
  }

  async function enableLocalMeaning(): Promise<void> {
    if (!localTarget || busy) return;
    busy = true; actionError = null; localResult = null;
    try {
      await api.enableLocalMeaning(localTarget.provider, localTarget.model);
      await load();
      await onchanged();
      localResult = settings?.retrieval?.semantic && settings.retrieval.query_embeddable
        ? "Find by meaning is ready on this computer."
        : "Local index prepared. Recall still matches words until query embedding is available; check model authorization in Memory Controls.";
    } catch (error) {
      actionError = failure("Could not prepare meaning search", "No successful setup was confirmed.", "Check that the local model is running and its use is authorized, then try again.", error);
    } finally { busy = false; }
  }

  // MEM-03 — recall searches exactly one embedding space. Reloading rather than
  // assuming is what keeps this page from claiming a backend it did not confirm.
  async function chooseBackend(backend: string): Promise<void> {
    busy = true;
    actionError = null;
    try {
      await api.setMemoryEmbeddingBackend(backend);
      await load();
      await onchanged();
    } catch (error) {
      actionError =
        failure("The recall backend was not changed", "Recall keeps searching the space it used.", "Try again.", error);
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
    const where = indexTarget.local_only ? "on this machine" : `to ${providerName(indexTarget.provider)}`;
    const question =
      `${indexTarget.local_only ? "Process" : "Send"} ${waiting} approved ` +
      `${waiting === 1 ? "memory" : "memories"} and ${waitingFiles} managed document ` +
      `${waitingFiles === 1 ? "passage" : "passages"} ${where} to be embedded as ` +
      `${indexTarget.model}? Secret-like or credential-like content is never embedded.`;
    if (!(await askConfirm({ title: question, confirmLabel: indexTarget.local_only ? "Process" : "Send" }))) return;
    busy = true;
    actionError = null;
    indexResult = null;
    try {
      const result = await api.buildMemoryEmbeddingIndex(indexTarget.provider, indexTarget.model);
      indexResult = `Embedded ${result.indexed_count} memories and ${result.indexed_file_chunk_count ?? 0} document passages into ${result.embedding_model}.`;
      await load();
      await onchanged();
    } catch (error) {
      actionError =
        failure("The index could not be built", "The previous index is still used.", "Try Rebuild again.", error);
    } finally {
      busy = false;
    }
  }

  onMount(load);
</script>

<section class="memory-engine">
  <header class="section-heading">
    <h2>Find by meaning</h2>
    <p>Set up local meaning-based recall, or manage an existing index.</p>
  </header>

  {#if loadError}
    <PageState state="error" title="Couldn't load the memory engine" detail={loadError} />
  {:else if !settings}
    <PageState state="loading" title="Reading the memory engine…" />
  {:else}
    {#if actionError}<p class="notice notice-danger" role="alert">{actionError}</p>{/if}

    <div class="card">
      <h3>Keep memory search on this computer</h3>
      {#if localProviders.length > 0}
        <p class="lead">Build and select a local index of your approved memories and document passages. Your existing model permissions still apply.</p>
        {#if localProviders.length > 1}
          <label class="field"><span class="field-label">Local embedding model</span>
            <select class="select" aria-label="Local embedding model" bind:value={localChoice} disabled={busy}>
              <option value="">Choose a local model…</option>
              {#each localProviders as provider (provider.space)}<option value={provider.space}>{provider.model}</option>{/each}
            </select>
          </label>
        {/if}
        <button type="button" class="btn btn-primary local-action" disabled={busy || !localTarget} onclick={() => void enableLocalMeaning()}>{busy ? "Preparing…" : "Find by meaning (stays on this computer)"}</button>
        {#if localTarget}<p class="note">Uses {localTarget.model} on this computer.</p>{/if}
      {:else}
        <p class="lead">Add a local embedding model in Models before setting up meaning-based recall.</p>
        <a class="btn btn-ghost" href="#/models?tab=add">Review local models</a>
      {/if}
      {#if localResult}<p class="note" role="status" aria-label="Meaning search result">{localResult}</p>{/if}
    </div>

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
      {#if background}
        <!-- FIXED-1426 — the background indexer's last pass, so "is recall
             keeping up?" has an answer here rather than in a log file. -->
        <p class="background {background.tone}" role="status" data-testid="background-index">
          <Icon name={background.tone === "ok" ? "check" : "info"} size="sm" />
          <span>{background.text}
            {#if background.action}<a href={background.action.href}>{background.action.label}</a>{/if}</span>
        </p>
      {/if}
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
                  >{provider.model} · {provider.local_only ? "on this machine" : providerName(provider.provider)}</option
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
  .local-action { margin-top: var(--space-3); white-space: normal; }
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
  .background { display: flex; align-items: baseline; gap: 0.4rem; font-size: var(--text-sm);
    color: var(--text-2); margin: 0 0 var(--space-3); }
  .background :global(svg) { flex: none; align-self: center; color: var(--text-3); }
  .background.ok :global(svg) { color: var(--ok, var(--text-3)); }
  .background.attention :global(svg) { color: var(--warn, var(--text-3)); }
  .background a { margin-left: 0.35rem; }
  .note :global(svg) { flex: none; align-self: center; color: var(--text-3); }
</style>
