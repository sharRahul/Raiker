<script lang="ts">
  import { api, ApiError } from "../../api";
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import type {
    HuggingFaceDownloadPreview,
    HuggingFaceSearchResult,
    HuggingFaceVariant,
    ModelConversionPreview,
    ModelLibraryView,
  } from "../../apiTypes";

  let query = $state("");
  let searching = $state(false);
  let results = $state<HuggingFaceSearchResult[]>([]);
  // The Hub cannot be browsed exhaustively, so this stays search-first. What it
  // must not do is open to an empty box: an owner who does not already know a
  // repository id had nowhere to start. Until the first search, the list shows
  // the most-downloaded GGUF repositories.
  let showingTrending = $state(false);
  let loadingTrending = $state(true);
  let selectedRepo = $state<string | null>(null);
  let variants = $state<HuggingFaceVariant[]>([]);
  let selected = $state<HuggingFaceVariant | null>(null);
  let library = $state<ModelLibraryView | null>(null);
  let destination = $state("");
  let preview = $state<HuggingFaceDownloadPreview | null>(null);
  let token = $state("");
  let tokenOpen = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let conversionSource = $state("");
  let conversionOutput = $state("");
  let quantization = $state("Q4_K_M");
  let conversionPreview = $state<ModelConversionPreview | null>(null);
  const size = (n: number) =>
    n < 1024 ** 3
      ? `${(n / 1024 ** 2).toFixed(0)} MB`
      : `${(n / 1024 ** 3).toFixed(1)} GB`;
  async function loadTrending() {
    loadingTrending = true;
    try {
      results = (await api.trendingHuggingFace()).items;
      showingTrending = results.length > 0;
    } catch {
      // A Hub that cannot be reached is not an error worth interrupting the
      // panel for before the owner has asked for anything; the empty state
      // still explains what to do, and a real search reports the failure.
      results = [];
      showingTrending = false;
    } finally {
      loadingTrending = false;
    }
  }
  void loadTrending();

  async function search() {
    if (!query.trim()) return;
    searching = true;
    error = null;
    selectedRepo = null;
    variants = [];
    try {
      results = (await api.searchHuggingFace(query.trim())).items;
      showingTrending = false;
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? `Search unavailable (${e.status})`)
          : "Search unavailable";
    } finally {
      searching = false;
    }
  }
  async function chooseRepo(repo: string) {
    selectedRepo = repo;
    selected = null;
    preview = null;
    error = null;
    try {
      variants = (await api.huggingFaceVariants(repo)).items;
      library = await api.modelLibrary();
      destination = library.roots[0]?.path ?? "";
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? "Could not inspect this repository")
          : "Could not inspect this repository";
    }
  }
  async function chooseVariant(variant: HuggingFaceVariant) {
    selected = variant;
    preview = null;
    try {
      preview = await api.previewHuggingFaceDownload(variant, destination);
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? "Could not estimate download")
          : "Could not estimate download";
    }
  }
  async function download() {
    if (!selected || !destination) return;
    try {
      const result = await api.downloadHuggingFaceModel(selected, destination);
      notice =
        selected.format === "safetensors"
          ? "Safetensors downloaded. Review the isolated conversion below."
          : "GGUF downloaded and indexed in your local library.";
      preview = null;
      if (selected.format === "safetensors") {
        conversionSource = result.snapshot_path;
        conversionOutput = result.conversion_output_path;
        conversionPreview = await api.previewModelConversion(
          conversionSource,
          conversionOutput,
          selected.revision,
          quantization,
        );
      }
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? "Download could not start")
          : "Download could not start";
    }
  }
  async function reviewConversion() {
    if (!selected || !conversionSource) return;
    try {
      conversionPreview = await api.previewModelConversion(
        conversionSource,
        conversionOutput,
        selected.revision,
        quantization,
      );
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? "Conversion cannot run safely")
          : "Conversion cannot run safely";
    }
  }
  async function convert() {
    if (!selected || !conversionPreview) return;
    if (
      !window.confirm(
        `Convert this immutable snapshot to ${quantization} in the isolated worker?`,
      )
    )
      return;
    try {
      await api.startModelConversion(
        conversionSource,
        conversionOutput,
        selected.revision,
        quantization,
      );
      notice = "Conversion queued. Follow it in Activity.";
    } catch (e) {
      error =
        e instanceof ApiError
          ? (e.reasonCode ?? "Conversion could not start")
          : "Conversion could not start";
    }
  }
  async function saveToken() {
    if (!token.trim()) return;
    try {
      await api.saveHuggingFaceCredential(token.trim());
      token = "";
      tokenOpen = false;
      notice = "Hugging Face token saved in the encrypted vault.";
    } catch {
      error = "Could not save the Hugging Face token.";
    }
  }
</script>

<div class="hf-shell">
  <section class="search-hero">
    <div class="hf-brand"><ProviderLogo provider="huggingface" size={40} /></div>
    <div>
      <p class="eyebrow">Hugging Face</p>
      <h2>Find a model for this machine</h2>
      <p>
        Raiker prefers ready-to-run GGUF files. Safetensors can be downloaded
        for an optional isolated conversion when no suitable GGUF exists.
      </p>
    </div>
    <button
      class="btn btn-ghost btn-sm"
      type="button"
      onclick={() => (tokenOpen = !tokenOpen)}
      >{tokenOpen ? "Close token setup" : "Set access token"}</button
    >
  </section>
  <section class="card curated-embedding" aria-label="Curated local embedding model">
    <div>
      <p class="eyebrow">Curated for semantic recall</p>
      <strong>Nomic Embed Text v1.5 · GGUF · Apache-2.0</strong>
      <p>
        The recommended Q4_K_M variant is about 81 MiB. Raiker resolves the
        current immutable revision and exact byte count before you approve any download.
      </p>
    </div>
    <button
      class="btn btn-sm"
      type="button"
      onclick={() => void chooseRepo("nomic-ai/nomic-embed-text-v1.5-GGUF")}
    >Review variants</button>
  </section>
  {#if tokenOpen}<form
      class="token-card card"
      onsubmit={(e) => {
        e.preventDefault();
        void saveToken();
      }}
    >
      <label
        ><span>Hugging Face access token</span><input
          type="password"
          autocomplete="off"
          bind:value={token}
          placeholder="hf_…"
        /></label
      ><button class="btn" type="submit" disabled={!token.trim()}
        >Save securely</button
      >
      <p>
        Only needed for private or gated repositories. Accept gated model terms
        on Hugging Face first.
      </p>
    </form>{/if}
  <form
    class="search-box"
    onsubmit={(e) => {
      e.preventDefault();
      void search();
    }}
  >
    <input
      bind:value={query}
      aria-label="Search Hugging Face models"
      placeholder="Search by model, task, or organization"
    /><button
      class="btn btn-primary"
      type="submit"
      disabled={searching || !query.trim()}
      >{searching ? "Searching…" : "Search models"}</button
    >
  </form>
  {#if error}<p class="error" role="alert">
      {error.replaceAll("_", " ")}
    </p>{/if}{#if notice}<p class="notice" role="status">{notice}</p>{/if}

  <div class="catalogue">
    <section class="results" aria-label="Hugging Face search results">
      {#if showingTrending}<p class="results-lead">
          Most downloaded GGUF models — search above for anything else.
        </p>{/if}
      {#if results.length === 0}<div class="empty">
          <strong
            >{loadingTrending
              ? "Loading popular models…"
              : "Search the Hub catalogue"}</strong
          ><span
            >Results stay here; selecting one reveals immutable downloadable
            variants.</span
          >
        </div>{/if}
      {#each results as item (item.repo_id)}<button
          type="button"
          class:selected={selectedRepo === item.repo_id}
          onclick={() => void chooseRepo(item.repo_id)}
          ><span class="repo">{item.repo_id}</span><small
            >{item.downloads.toLocaleString()} downloads · {item.likes.toLocaleString()}
            likes</small
          >{#if item.gated}<em>Access gated</em>{/if}</button
        >{/each}
    </section>
    <section class="variants" aria-label="Model download options">
      {#if selectedRepo === null}<div class="empty">
          <strong>No repository selected</strong><span
            >Choose a result to compare formats, quantizations, size, and
            license.</span
          >
        </div>
      {:else}<header>
          <p class="eyebrow">Immutable snapshot</p>
          <h3>{selectedRepo}</h3>
        </header>
        {#if variants.length === 0}<p class="empty-copy">
            No complete GGUF or Safetensors download was found.
          </p>{:else}<div class="variant-list">
            {#each variants as item (`${item.revision}-${item.files.join("|")}`)}<button
                type="button"
                class:selected={selected === item}
                class:incomplete={!item.complete}
                disabled={!item.complete}
                onclick={() => void chooseVariant(item)}
                ><span
                  ><strong
                    >{item.format === "gguf"
                      ? (item.quantization ?? "GGUF")
                      : "Safetensors"}</strong
                  ><small
                    >{item.format === "gguf"
                      ? "Ready to deploy"
                      : "Requires isolated conversion"}</small
                  ></span
                ><span class="variant-meta"
                  ><strong>{size(item.total_bytes)}</strong><small
                    >{item.license_id ?? "License not declared"}</small
                  ></span
                ></button
              >{/each}
          </div>{/if}{/if}
    </section>
  </div>

  {#if selected}<section class="download-drawer card">
      <div>
        <p class="eyebrow">Review download</p>
        <h3>
          {selected.format === "gguf"
            ? `Download ${selected.quantization ?? "GGUF"}`
            : "Download Safetensors snapshot"}
        </h3>
        <p>
          Pinned to <code>{selected.revision.slice(0, 12)}</code>. {selected
            .files.length} selected file{selected.files.length === 1
            ? ""
            : "s"}; no repository code will run.
        </p>
      </div>
      <label
        ><span>Approved destination folder</span><select
          bind:value={destination}
          >{#each library?.roots ?? [] as root (root.path)}<option
              value={root.path}>{root.path}</option
            >{/each}</select
        ></label
      >{#if preview}<div class="estimate">
          <span>Download</span><strong>{size(preview.download_bytes)}</strong
          ><small>{size(preview.cached_bytes)} already cached</small>
        </div>{/if}<button
        class="btn btn-primary"
        type="button"
        disabled={!destination || preview === null}
        onclick={() => void download()}>Confirm download</button
      >{#if !destination}<a href="#/models?tab=local"
          >Approve a model folder first →</a
        >{/if}
    </section>{/if}
  {#if conversionSource}<section class="conversion-card card">
      <div>
        <p class="eyebrow">Optional conversion</p>
        <h3>Safetensors → GGUF</h3>
        <p>
          The immutable source is mounted read-only. The worker has no network,
          owner credentials, or Raiker workspace mount.
        </p>
      </div>
      <label
        ><span>Quantization</span><select
          bind:value={quantization}
          onchange={() => void reviewConversion()}
          ><option>Q4_K_M</option><option>Q5_K_M</option><option>Q6_K</option
          ><option>Q8_0</option></select
        ></label
      >{#if conversionPreview}<div class="isolation-proof">
          <strong>{conversionPreview.architecture}</strong><small
            >{conversionPreview.isolation.max_cpu_count} CPU cap · {size(
              conversionPreview.isolation.max_memory_bytes,
            )} memory cap · pinned toolchain</small
          >
        </div>{/if}<button
        class="btn btn-primary"
        type="button"
        disabled={conversionPreview === null}
        onclick={() => void convert()}>Convert in isolation</button
      >
    </section>{/if}
</div>

<style>
  .hf-shell {
    --text-muted: var(--text-2);
    display: grid;
    gap: 18px;
  }
  .search-hero {
    display: grid;
    grid-template-columns: 56px 1fr auto;
    align-items: start;
    gap: 16px;
    padding: 18px 4px;
  }
  .search-hero h2 {
    font-size: 1.65rem;
    margin: 2px 0 6px;
  }
  .search-hero p {
    margin: 0;
    max-width: 70ch;
    color: var(--text-muted);
  }
  .hf-brand {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    border-radius: 13px;
    background: #ffd21e;
    color: #171717;
    font-weight: 850;
  }
  .token-card {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: 12px;
    padding: 16px;
  }
  .token-card label {
    display: grid;
    gap: 6px;
  }
  .token-card p {
    grid-column: 1/-1;
    margin: 0;
    color: var(--text-muted);
    font-size: 0.82rem;
  }
  .search-box {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 10px;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 13px;
    background: var(--surface);
  }
  .search-box input {
    border: 0;
    background: transparent;
    font-size: 1rem;
  }
  .catalogue {
    display: grid;
    grid-template-columns: minmax(270px, 0.8fr) minmax(340px, 1.2fr);
    gap: 14px;
    min-height: 340px;
  }
  .results,
  .variants {
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
    overflow: hidden;
  }
  .results > button {
    width: 100%;
    display: grid;
    text-align: left;
    gap: 4px;
    padding: 14px 16px;
    border: 0;
    border-bottom: 1px solid var(--border);
    background: transparent;
    color: inherit;
  }
  .results > button:hover,
  .results > button.selected {
    background: var(--surface-raised, #f5f6f8);
  }
  .repo {
    font:
      650 0.9rem ui-monospace,
      monospace;
  }
  .results small,
  .variant-list small {
    color: var(--text-muted);
  }
  .results em {
    color: #a16207;
    font-size: 0.75rem;
  }
  .variants > header {
    padding: 18px;
    border-bottom: 1px solid var(--border);
  }
  .variants h3 {
    margin: 3px 0;
    font-family: ui-monospace, monospace;
  }
  .variant-list button {
    width: 100%;
    display: flex;
    justify-content: space-between;
    gap: 15px;
    text-align: left;
    padding: 14px 18px;
    border: 0;
    border-bottom: 1px solid var(--border);
    background: transparent;
    color: inherit;
  }
  .variant-list button.selected {
    box-shadow: inset 3px 0 #2563eb;
    background: var(--surface-raised, #f5f6f8);
  }
  .variant-list button span {
    display: grid;
    gap: 3px;
  }
  .variant-meta {
    text-align: right;
  }
  .incomplete {
    opacity: 0.55;
  }
  .results-lead {
    color: var(--text-3);
    font-size: 0.76rem;
    margin: 0 0 8px;
  }
  .empty {
    height: 100%;
    min-height: 230px;
    display: grid;
    place-content: center;
    text-align: center;
    gap: 6px;
    padding: 30px;
    color: var(--text-muted);
  }
  .empty-copy {
    padding: 18px;
    color: var(--text-muted);
  }
  .download-drawer,
  .conversion-card {
    display: grid;
    grid-template-columns: 1.3fr 1fr auto auto;
    gap: 18px;
    align-items: end;
    padding: 20px;
    border-top: 3px solid #2563eb;
  }
  .conversion-card {
    border-top-color: #7c3aed;
  }
  .download-drawer h3,
  .conversion-card h3 {
    margin: 2px 0 5px;
  }
  .download-drawer p,
  .conversion-card p {
    margin: 0;
    color: var(--text-muted);
  }
  .download-drawer label,
  .estimate,
  .conversion-card label,
  .isolation-proof {
    display: grid;
    gap: 5px;
  }
  .estimate small,
  .isolation-proof small {
    color: var(--text-muted);
  }
  .notice {
    color: var(--success, #15803d);
  }
  .curated-embedding {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 16px 18px;
    border-left: 3px solid var(--accent, #2563eb);
  }
  .curated-embedding p {
    margin: 3px 0 0;
    color: var(--text-muted);
  }
  @media (max-width: 850px) {
    .catalogue,
    .download-drawer,
    .conversion-card {
      grid-template-columns: 1fr;
    }
    .search-hero {
      grid-template-columns: 52px 1fr;
    }
    .search-hero button {
      grid-column: 2;
    }
    .token-card {
      grid-template-columns: 1fr;
    }
    .search-box {
      grid-template-columns: 1fr;
    }
    .curated-embedding {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
