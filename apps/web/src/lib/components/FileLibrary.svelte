<script lang="ts">
  /**
   * The shared document library for Memory and Projects.
   *
   * One component, two managed roots: `scope="memory"` manages the account's
   * own library, `scope="project"` manages one project's. The difference is a
   * prop, because the two libraries are the same object with different owners —
   * duplicating the UI would let them drift apart in exactly the places a
   * person compares them.
   *
   * Every file type is offered. The file inputs deliberately carry no `accept`
   * filter, because Raiker stores what it is given: whether a file's text can
   * be read is reported back per file as an index state, never decided in the
   * browser by guessing at a MIME type. An uploaded file is data — it is stored,
   * possibly indexed, and never executed.
   */
  import type {
    ManagedFile,
    ManagedFileImportResult,
    ManagedFileScope,
    ManagedFileUpload,
  } from "../apiTypes";
  import { api } from "../api";
  import Icon from "./Icon.svelte";

  let {
    scope,
    projectId = null,
    heading = "Document library",
    description = "Files kept in Raiker's managed storage. Uploaded content is data, never instructions.",
  }: {
    scope: ManagedFileScope;
    projectId?: string | null;
    heading?: string;
    description?: string;
  } = $props();

  let files = $state<ManagedFile[]>([]);
  let loading = $state(false);
  let importing = $state(false);
  let error = $state<string | null>(null);
  /** The last batch's per-file outcome, announced rather than silently applied. */
  let lastResults = $state<ManagedFileImportResult[]>([]);
  let busyFileId = $state<string | null>(null);
  let fileInput = $state<HTMLInputElement>();
  let folderInput = $state<HTMLInputElement>();

  const ready = $derived(scope === "memory" || Boolean(projectId));

  const STATE_LABELS: Record<string, string> = {
    queued: "Queued",
    indexing: "Indexing",
    ready: "Ready",
    metadata_only: "Metadata only",
    failed: "Failed",
    retired: "Removed",
  };

  /** Why a file has no content index, in words rather than a reason code. */
  const REASON_LABELS: Record<string, string> = {
    no_local_extractor: "No safe local reader for this format",
    no_extractable_text: "No readable text found",
    file_empty: "The file is empty",
    file_too_large_to_extract: "Too large to read locally",
    file_unreadable: "The stored file could not be read",
    extraction_failed: "Reading the file failed",
    truncated: "Indexed up to the size limit",
  };

  function label(file: ManagedFile): string {
    return STATE_LABELS[file.index_state] ?? file.index_state;
  }

  function detail(file: ManagedFile): string {
    if (!file.index_error) return "";
    return REASON_LABELS[file.index_error] ?? file.index_error;
  }

  export function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function load() {
    if (!ready) return;
    loading = true;
    try {
      const list = await api.managedFiles(scope, projectId);
      files = list.files;
      error = null;
    } catch {
      error = "The library could not be read.";
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    // Re-read whenever the scope changes, so switching projects never shows the
    // previous project's files.
    void scope;
    void projectId;
    void load();
  });

  function readBase64(file: File): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = String(reader.result);
        resolve(dataUrl.slice(dataUrl.indexOf(",") + 1));
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  /**
   * The path the file keeps inside the managed root.
   *
   * `webkitRelativePath` is what preserves a folder's hierarchy; a plain file
   * selection has none, so the name is the path. Either way the server
   * re-validates containment — this only decides where the owner asked it to go.
   */
  function relativePathOf(file: File): string {
    const relative = (file as File & { webkitRelativePath?: string })
      .webkitRelativePath;
    return relative && relative.length > 0 ? relative : file.name;
  }

  async function importFiles(selected: FileList | null) {
    if (!selected || selected.length === 0 || !ready) return;
    importing = true;
    error = null;
    try {
      const uploads: ManagedFileUpload[] = [];
      for (const file of Array.from(selected)) {
        uploads.push({
          relative_path: relativePathOf(file),
          media_type: file.type || "application/octet-stream",
          data_base64: await readBase64(file),
        });
      }
      const response = await api.importManagedFiles(scope, projectId, uploads);
      lastResults = response.results;
      await load();
    } catch {
      error = "The import could not be completed.";
    } finally {
      importing = false;
    }
  }

  async function remove(file: ManagedFile) {
    busyFileId = file.file_id;
    try {
      await api.deleteManagedFile(file.file_id);
      await load();
    } catch {
      error = "That file could not be removed.";
    } finally {
      busyFileId = null;
    }
  }

  async function retry(file: ManagedFile) {
    busyFileId = file.file_id;
    try {
      await api.retryManagedFile(file.file_id);
      await load();
    } catch {
      error = "Indexing could not be retried.";
    } finally {
      busyFileId = null;
    }
  }

  const failures = $derived(
    lastResults.filter((result): result is Extract<ManagedFileImportResult, { ok: false }> => !result.ok),
  );
  const importSummary = $derived(
    lastResults.length === 0
      ? ""
      : `${lastResults.length - failures.length} of ${lastResults.length} files stored.`,
  );
</script>

<section class="file-library" aria-labelledby="file-library-heading">
  <header class="library-head">
    <div>
      <h3 id="file-library-heading">{heading}</h3>
      <p class="library-hint">{description}</p>
    </div>
    <div class="icon-button-group" role="group" aria-label="Add to library">
      <button
        type="button"
        class="control group-item"
        onclick={() => fileInput?.click()}
        disabled={!ready || importing}
      >
        <Icon name="file" size={15} /> Add files
      </button>
      <button
        type="button"
        class="control group-item"
        onclick={() => folderInput?.click()}
        disabled={!ready || importing}
      >
        <Icon name="folder" size={15} /> Add folder
      </button>
    </div>
  </header>

  <!-- No `accept`: every file type is stored. Hidden inputs, because the
       visible controls are the grouped buttons above. -->
  <input
    class="sr-only"
    type="file"
    multiple
    tabindex="-1"
    aria-hidden="true"
    bind:this={fileInput}
    onchange={(event) => {
      const input = event.currentTarget as HTMLInputElement;
      void importFiles(input.files).then(() => (input.value = ""));
    }}
  />
  <input
    class="sr-only"
    type="file"
    multiple
    webkitdirectory
    tabindex="-1"
    aria-hidden="true"
    bind:this={folderInput}
    onchange={(event) => {
      const input = event.currentTarget as HTMLInputElement;
      void importFiles(input.files).then(() => (input.value = ""));
    }}
  />

  <p class="import-status" role="status" aria-live="polite">
    {#if importing}Importing…{:else if importSummary}{importSummary}{/if}
  </p>

  {#if !ready}
    <p class="library-empty">Select a project to manage its files.</p>
  {:else if error}
    <!-- A status, not an alert: a library that could not be read is worth
         saying, but it must not interrupt whatever the page was doing. -->
    <p class="library-error" role="status">{error}</p>
  {/if}

  {#if failures.length > 0}
    <ul class="failures">
      {#each failures as failure (failure.relative_path + failure.reason_code)}
        <li>
          <code>{failure.relative_path || "(unnamed)"}</code>
          <span>{failure.reason_code}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#if loading && files.length === 0}
    <p class="library-empty">Loading…</p>
  {:else if ready && files.length === 0}
    <p class="library-empty">No files yet.</p>
  {:else if files.length > 0}
    <ul class="file-rows">
      {#each files as file (file.file_id)}
        <li class="file-row">
          <div class="file-id">
            <span class="file-path">{file.relative_path}</span>
            <span class="file-meta">
              {formatSize(file.size_bytes)} · {file.media_type}
            </span>
          </div>
          <div class="file-state">
            <span class="state-pill" data-state={file.index_state}>{label(file)}</span>
            {#if detail(file)}<span class="state-detail">{detail(file)}</span>{/if}
          </div>
          <div class="file-actions">
            {#if file.index_state !== "ready"}
              <button
                type="button"
                class="control icon-button"
                aria-label={`Retry indexing ${file.relative_path}`}
                onclick={() => retry(file)}
                disabled={busyFileId === file.file_id}
              ><Icon name="refresh" size={15} /></button>
            {/if}
            <button
              type="button"
              class="control icon-button danger"
              aria-label={`Remove ${file.relative_path}`}
              onclick={() => remove(file)}
              disabled={busyFileId === file.file_id}
            ><Icon name="x" size={15} /></button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .file-library { display: grid; gap: var(--space-3); }
  .library-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .library-head h3 { margin: 0; font-size: var(--text-md); }
  .library-hint { margin: 0.15rem 0 0; color: var(--text-3); font-size: var(--text-xs); }
  .group-item { display: inline-flex; align-items: center; gap: 0.4rem; }
  .import-status { margin: 0; min-height: 1rem; font-size: var(--text-xs); color: var(--text-3); }
  .library-empty { margin: 0; color: var(--text-3); font-size: var(--text-sm); }
  .library-error { margin: 0; color: var(--danger); font-size: var(--text-sm); }
  .failures { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.25rem; }
  .failures li { display: flex; gap: var(--space-2); font-size: var(--text-xs); color: var(--danger); }
  .file-rows { list-style: none; margin: 0; padding: 0; display: grid; }
  .file-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--row-y) var(--row-x);
    border-top: 1px solid var(--border);
  }
  .file-row:last-child { border-bottom: 1px solid var(--border); }
  .file-id { display: grid; min-width: 0; }
  .file-path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); }
  .file-meta { color: var(--text-3); font-size: var(--text-xs); }
  .file-state { display: grid; justify-items: end; gap: 0.1rem; }
  .state-pill {
    font-size: var(--text-xs);
    font-weight: 600;
    padding: 0.1rem 0.5rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
  }
  .state-pill[data-state="ready"] { border-color: var(--ok-border, var(--neutral-border)); color: var(--text-1); }
  .state-pill[data-state="failed"] { border-color: var(--danger); color: var(--danger); }
  .state-detail { color: var(--text-3); font-size: var(--text-xs); }
  .file-actions { display: inline-flex; gap: 0.25rem; }
  .file-actions .danger { color: var(--danger); }
</style>
