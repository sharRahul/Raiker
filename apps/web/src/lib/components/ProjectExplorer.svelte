<script lang="ts">
  /**
   * One file tree for both kinds of project root.
   *
   * A project's files used to appear twice on this page: once as the managed
   * document library and once as a walk of the project folder. They were the
   * same files described differently, which meant the owner had to work out
   * which list to believe. This is the one list.
   *
   * Two properties shape everything below:
   *
   * - **Lazy.** A folder the owner attached can be an entire repository. The
   *   tree reads one directory at a time and caches what it read, so opening a
   *   project never walks a tree the owner only wanted to glance at.
   * - **Honest about freshness.** An indexed attached folder is kept current by
   *   a watcher that can fail. When it has, this says so; it never renders a
   *   stale index as though it were live.
   *
   * File content is never fetched here. The tree is metadata, exactly as the
   * listing it replaces was, and an attached folder's bytes stay on the owner's
   * disk.
   */
  import { untrack } from "svelte";
  import { api, ApiError } from "../api";
  import type {
    ProjectBrowseEntry,
    ProjectBrowseView,
    ProjectRootKind,
    ProjectRootStatus,
  } from "../apiTypes";
  import FileLibrary from "./FileLibrary.svelte";
  import Icon from "./Icon.svelte";

  let {
    projectId,
    rootKind,
    rootLabel,
    onselect,
  }: {
    projectId: string;
    rootKind: ProjectRootKind;
    rootLabel: string;
    onselect?: (entry: ProjectBrowseEntry | null) => void;
  } = $props();

  /** Directory listings by relative path. The cache *is* the laziness. */
  let listings = $state<Record<string, ProjectBrowseView>>({});
  let expanded = $state<Record<string, boolean>>({});
  let loadingPaths = $state<Record<string, boolean>>({});
  let error = $state<string | null>(null);
  let status = $state<ProjectRootStatus | null>(null);
  let indexing = $state(false);
  let indexSummary = $state<string | null>(null);
  let selectedPath = $state<string | null>(null);

  const root = $derived(listings[""] ?? null);
  const missing = $derived(root?.root_missing ?? status?.root_missing ?? false);

  const STATE_LABELS: Record<string, string> = {
    queued: "Queued",
    indexing: "Indexing",
    ready: "Ready",
    metadata_only: "Metadata only",
    failed: "Failed",
    retired: "Removed",
  };

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function loadDirectory(path: string, force = false): Promise<void> {
    if (!force && listings[path] !== undefined) return;
    loadingPaths = { ...loadingPaths, [path]: true };
    try {
      const view = await api.browseProject(projectId, path);
      listings = { ...listings, [path]: view };
      if (path === "") error = null;
    } catch (e) {
      // A folder that cannot be read is worth saying and must not blank the
      // page: the project's other sections stay usable.
      if (path === "") {
        error =
          e instanceof ApiError
            ? `The project folder could not be read (${e.status}).`
            : "The project folder could not be read.";
      }
    } finally {
      const rest = { ...loadingPaths };
      delete rest[path];
      loadingPaths = rest;
    }
  }

  async function loadStatus(): Promise<void> {
    try {
      status = await api.projectRootStatus(projectId);
    } catch {
      // Status is supplementary. Without it the tree still lists files; what is
      // lost is only the freshness note, and claiming freshness we cannot
      // confirm would be worse than omitting it.
      status = null;
    }
  }

  async function toggle(entry: ProjectBrowseEntry): Promise<void> {
    const path = entry.relative_path;
    if (expanded[path]) {
      expanded = { ...expanded, [path]: false };
      return;
    }
    expanded = { ...expanded, [path]: true };
    await loadDirectory(path);
  }

  function select(entry: ProjectBrowseEntry): void {
    selectedPath = entry.relative_path;
    onselect?.(entry);
  }

  async function indexNow(): Promise<void> {
    if (indexing) return;
    indexing = true;
    indexSummary = null;
    try {
      const report = await api.indexProjectRoot(projectId);
      indexSummary =
        `${report.indexed} newly indexed, ${report.updated} updated, ` +
        `${report.retired} removed, ${report.skipped} skipped.`;
      listings = {};
      await Promise.all([loadDirectory(""), loadStatus()]);
      for (const path of Object.keys(expanded)) {
        if (expanded[path]) await loadDirectory(path);
      }
    } catch (e) {
      indexSummary =
        e instanceof ApiError ? `Indexing failed (${e.status}).` : "Indexing failed.";
    } finally {
      indexing = false;
    }
  }

  $effect(() => {
    // Re-read whenever the project changes, so switching projects never shows
    // the previous project's tree. Only `projectId` is a dependency: the reload
    // writes the very caches it reads, so tracking them would make the effect
    // re-run on its own output for ever.
    void projectId;
    untrack(() => {
      listings = {};
      expanded = {};
      selectedPath = null;
      indexSummary = null;
      void loadDirectory("");
      void loadStatus();
    });
  });

  const freshness = $derived.by(() => {
    if (status === null || status.root_kind !== "attached") return null;
    if (status.indexed_files === 0) {
      return "This folder is not indexed. Index it to let Build recall from its files.";
    }
    if (status.watching) {
      return status.last_scanned_at === ""
        ? "Watching this folder for changes."
        : `Watching this folder for changes. Last checked ${status.last_scanned_at}.`;
    }
    return (
      "Raiker is not watching for changes in this folder" +
      (status.watch_reason && status.watch_reason !== "not_started"
        ? ` (${status.watch_reason})`
        : "") +
      ". The index is as fresh as the last scan; index again to bring it up to date."
    );
  });
</script>

<section class="project-explorer" aria-labelledby="project-explorer-heading">
  <header class="explorer-head">
    <div>
      <h3 id="project-explorer-heading">Project files</h3>
      <p class="explorer-hint">
        {#if rootKind === "attached"}
          Read where they live in <code class="mono">{rootLabel}</code>. Raiker keeps no copy.
        {:else}
          Files kept under this project's managed root. Build can read them only while this
          project is selected.
        {/if}
      </p>
    </div>
    {#if rootKind === "attached"}
      <div class="icon-button-group" role="group" aria-label="Project folder index">
        <button
          type="button"
          class="control group-item"
          onclick={() => void indexNow()}
          disabled={indexing || missing}
        >
          <Icon name="refresh" size={15} />
          {indexing ? "Indexing…" : "Index this folder"}
        </button>
      </div>
    {/if}
  </header>

  {#if rootKind === "attached" && freshness !== null}
    <p class="explorer-note" role="status">{freshness}</p>
  {/if}
  {#if indexSummary !== null}
    <p class="explorer-note" role="status" aria-live="polite">{indexSummary}</p>
  {/if}

  {#if missing}
    <!-- A revoked grant, a detached project, or a folder the owner moved. An
         empty tree here would read as "no files", which is a different and
         much more alarming claim. -->
    <p class="explorer-empty">
      That folder is no longer available. Its files are untouched — reattach the folder, or
      grant it again, to browse them here.
    </p>
  {:else if error !== null}
    <p class="explorer-error" role="status">{error}</p>
  {:else if root === null}
    <p class="explorer-empty">Reading the project folder…</p>
  {:else}
    <!-- The tree is rendered even when empty, so the landmark a screen reader
         navigates to does not appear and disappear with the folder's contents. -->
    <ul class="tree" role="tree" aria-label="Project files">
      {#each root.entries as entry (entry.relative_path)}
        {@render node(entry, 0)}
      {/each}
    </ul>
    {#if root.entries.length === 0}
      <p class="explorer-empty">This folder is empty.</p>
    {:else if root.truncated}
      <p class="explorer-note">
        The listing stopped at its size limit. Not every file in this folder is shown.
      </p>
    {/if}
  {/if}

  {#if rootKind === "managed"}
    <!-- Import belongs to a managed root only. An attached folder is read where
         it lives, so offering to add files to it would imply a copy Raiker
         never makes. -->
    <FileLibrary
      scope="project"
      {projectId}
      heading="Add to this project"
      description="Files imported here are copied into the project's managed root."
    />
  {/if}
</section>

{#snippet node(entry: ProjectBrowseEntry, depth: number)}
  <li role="none" style={`--depth:${depth}`}>
    <div
      class="row"
      role="treeitem"
      aria-selected={selectedPath === entry.relative_path}
      aria-expanded={entry.is_directory ? Boolean(expanded[entry.relative_path]) : undefined}
    >
      {#if entry.is_directory}
        <button
          type="button"
          class="twisty"
          onclick={() => void toggle(entry)}
          aria-label={`${expanded[entry.relative_path] ? "Collapse" : "Expand"} ${entry.name}`}
        >
          <Icon name={expanded[entry.relative_path] ? "chevron-down" : "chevron-right"} size={14} />
        </button>
      {:else}
        <span class="twisty spacer"></span>
      {/if}
      <button
        type="button"
        class="entry"
        class:selected={selectedPath === entry.relative_path}
        onclick={() => (entry.is_directory ? void toggle(entry) : select(entry))}
        aria-label={entry.is_directory ? `Open ${entry.name}` : `Inspect ${entry.name}`}
      >
        <Icon name={entry.is_directory ? "folder" : "file"} size={14} />
        <span class="entry-name">{entry.name}</span>
        {#if !entry.is_directory}
          <span class="entry-meta">{formatSize(entry.size_bytes)}</span>
        {/if}
        {#if entry.index_state !== null}
          <!-- Only where a catalogue row exists. A file Raiker cannot read has
               no index state, and a blank badge would read as a failure. -->
          <span class="entry-state">{STATE_LABELS[entry.index_state] ?? entry.index_state}</span>
        {/if}
      </button>
    </div>
    {#if entry.is_directory && expanded[entry.relative_path]}
      <ul role="group">
        {#if loadingPaths[entry.relative_path]}
          <li role="none" class="child-note" style={`--depth:${depth + 1}`}>Reading…</li>
        {:else if listings[entry.relative_path] === undefined}
          <li role="none" class="child-note" style={`--depth:${depth + 1}`}>
            This folder could not be read.
          </li>
        {:else if listings[entry.relative_path].entries.length === 0}
          <li role="none" class="child-note" style={`--depth:${depth + 1}`}>Empty.</li>
        {:else}
          {#each listings[entry.relative_path].entries as child (child.relative_path)}
            {@render node(child, depth + 1)}
          {/each}
        {/if}
      </ul>
    {/if}
  </li>
{/snippet}

<style>
  .project-explorer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 1rem;
  }
  .explorer-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .explorer-head h3 {
    margin: 0;
  }
  .explorer-hint,
  .explorer-note,
  .explorer-empty,
  .explorer-error {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .explorer-error {
    color: var(--danger, var(--text-muted));
  }
  .tree,
  .tree ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding-left: calc(var(--depth, 0) * 1rem);
  }
  .twisty {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    padding: 0;
    border: 0;
    background: none;
    color: inherit;
    cursor: pointer;
  }
  .twisty.spacer {
    cursor: default;
  }
  .entry {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    min-width: 0;
    padding: 0.2rem 0.4rem;
    border: 0;
    border-radius: 4px;
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .entry:hover,
  .entry.selected {
    background: var(--sunken);
  }
  .entry-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .entry-meta,
  .entry-state {
    color: var(--text-muted);
    font-size: 0.75rem;
    white-space: nowrap;
  }
  .child-note {
    padding-left: calc(var(--depth, 0) * 1rem + 1.25rem);
    color: var(--text-muted);
    font-size: 0.8rem;
  }
</style>
