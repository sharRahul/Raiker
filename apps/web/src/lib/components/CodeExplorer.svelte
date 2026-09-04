<script lang="ts">
  /**
   * B13 — the repository, on screen, in Build.
   *
   * Build could change a repository and never show it. Seeing what the agent
   * was working in, or reading the file it just changed, meant leaving the app;
   * the explorer component that would have answered it existed and was mounted
   * only on Projects. This is that surface for the *repository* a coding session
   * is pointed at.
   *
   * Three properties, each load-bearing:
   *
   * - **Lazy.** A connected repository can be arbitrarily large. One directory
   *   is read at a time and cached, so opening the panel never walks a tree the
   *   owner only wanted to glance at.
   * - **Read-only, and structurally so.** There is no write path here at all:
   *   the two calls behind it are a directory listing and a bounded file read.
   *   A change to a file still goes through a proposal the owner accepts.
   * - **It never guesses.** A file that cannot be shown — binary, oversize,
   *   gone — says which, in words. An empty pane would read as an empty file.
   *
   * Highlighting is the same locally-shipped, allowlisted scanner the transcript
   * uses (`highlight.ts`): escaped at emit time, a closed tag set, and plain
   * text for any language it does not ship a grammar for.
   */
  import { untrack } from "svelte";
  import { api, ApiError } from "../api";
  import type {
    CodeRepoBrowseView,
    CodeRepoDiagnosticsView,
    ProjectBrowseEntry,
  } from "../apiTypes";
  import { highlight, languageForFilename, languageLabel } from "../highlight";
  import Icon from "./Icon.svelte";

  let {
    repoId,
    repoLabel,
    onclose,
    onmention,
  }: {
    repoId: string;
    repoLabel: string;
    onclose: () => void;
    /** Put the open file's path in the composer, so reading leads to asking. */
    onmention?: (path: string) => void;
  } = $props();

  let listings = $state<Record<string, CodeRepoBrowseView>>({});
  let expanded = $state<Record<string, boolean>>({});
  let loadingPaths = $state<Record<string, boolean>>({});
  let error = $state<string | null>(null);

  let openPath = $state<string | null>(null);
  let fileText = $state("");
  let fileLoading = $state(false);
  let fileNotice = $state<string | null>(null);
  let fileTruncated = $state(false);
  // B10 — what a parser sees in the open file. Null while nothing is known,
  // which is deliberately distinct from "checked and clean": the strip renders
  // nothing until the read comes back, rather than claiming a clean file it has
  // not looked at.
  let fileDiagnostics = $state<CodeRepoDiagnosticsView | null>(null);

  const root = $derived(listings[""] ?? null);
  const missing = $derived(root?.root_missing ?? false);
  const language = $derived(openPath === null ? "" : languageForFilename(openPath));

  /** Why a file cannot be shown, in the owner's words rather than a code. */
  const NOTICES: Record<string, string> = {
    binary_file: "This file is not text, so there is nothing to show here.",
    file_too_large: "This file is too large to open in the viewer.",
    not_found: "That file is no longer there.",
    file_not_found: "That file is no longer there.",
    not_file: "That path is not a file.",
    unreadable: "This file could not be read.",
  };

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function loadDirectory(path: string): Promise<void> {
    if (listings[path] !== undefined) return;
    loadingPaths = { ...loadingPaths, [path]: true };
    try {
      const view = await api.browseCodeRepo(repoId, path);
      listings = { ...listings, [path]: view };
      if (path === "") error = null;
    } catch (e) {
      // A folder that cannot be read is worth saying and must not blank the
      // panel: the rest of the repository stays browsable.
      if (path === "") {
        error =
          e instanceof ApiError
            ? `This repository could not be read (${e.status}).`
            : "This repository could not be read.";
      }
    } finally {
      const rest = { ...loadingPaths };
      delete rest[path];
      loadingPaths = rest;
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

  async function openFile(entry: ProjectBrowseEntry): Promise<void> {
    openPath = entry.relative_path;
    fileLoading = true;
    fileNotice = null;
    fileText = "";
    fileTruncated = false;
    try {
      const view = await api.readCodeRepoFile(repoId, entry.relative_path);
      if (!view.readable) {
        fileNotice = NOTICES[view.reason_code] ?? "This file could not be shown.";
        return;
      }
      fileText = view.text;
      fileTruncated = view.truncated;
    } catch (e) {
      const code = e instanceof ApiError ? String(e.reasonCode ?? "") : "";
      fileNotice = NOTICES[code] ?? "This file could not be read.";
    } finally {
      fileLoading = false;
    }
    // After the text, never instead of it: a repository the owner can read is
    // worth more than a diagnostic, so a diagnostics failure must not take the
    // file down with it. The strip simply stays silent.
    if (fileNotice === null) {
      await loadDiagnostics(entry.relative_path);
    }
  }

  async function loadDiagnostics(path: string): Promise<void> {
    try {
      const view = await api.readCodeRepoDiagnostics(repoId, path);
      // A slow read for a file the owner has since closed or moved past must
      // not overwrite the current one's answer.
      if (openPath === path) fileDiagnostics = view;
    } catch {
      if (openPath === path) fileDiagnostics = null;
    }
  }

  const rendered = $derived(
    language === "" ? "" : highlight(fileText, language),
  );

  $effect(() => {
    // Re-read whenever the repository changes, so switching repositories never
    // shows the previous one's tree. Only `repoId` is a dependency: the reload
    // writes the very caches it reads.
    void repoId;
    untrack(() => {
      listings = {};
      expanded = {};
      openPath = null;
      fileText = "";
      fileNotice = null;
      fileDiagnostics = null;
      void loadDirectory("");
    });
  });
</script>

<section class="code-explorer" aria-labelledby="code-explorer-heading">
  <header class="head">
    <h2 id="code-explorer-heading">
      <Icon name="folder" size="sm" />
      <span class="repo">{repoLabel}</span>
    </h2>
    <button type="button" class="icon-btn" aria-label="Close files" onclick={onclose}>
      <Icon name="x" size="sm" />
    </button>
  </header>

  <div class="tree-pane">
    {#if missing}
      <p class="note">
        {root?.reason_code === "repo_not_checked_out"
          ? "This is a GitHub coordinate, not a checkout — there are no files on this machine to browse."
          : "That folder is no longer in the workspace."}
      </p>
    {:else if error !== null}
      <p class="note error" role="status">{error}</p>
    {:else if root === null}
      <p class="note">Reading…</p>
    {:else}
      <ul class="tree" role="tree" aria-label="Repository files">
        {#each root.entries as entry (entry.relative_path)}
          {@render node(entry, 0)}
        {/each}
      </ul>
      {#if root.entries.length === 0}
        <p class="note">This repository is empty.</p>
      {:else if root.truncated}
        <p class="note">The listing stopped at its size limit.</p>
      {/if}
    {/if}
  </div>

  {#if openPath !== null}
    <div class="viewer" aria-label={`Viewing ${openPath}`}>
      <header class="viewer-head">
        <span class="viewer-path" title={openPath}>{openPath}</span>
        <span class="viewer-actions">
          {#if language !== ""}
            <span class="lang">{languageLabel(language)}</span>
          {/if}
          {#if onmention !== undefined}
            <button
              type="button"
              class="icon-btn mention"
              aria-label={`Mention ${openPath} in the composer`}
              title="Mention in the composer"
              onclick={() => onmention?.(openPath ?? "")}
            >@</button>
          {/if}
          <button
            type="button"
            class="icon-btn"
            aria-label="Close file"
            onclick={() => {
              openPath = null;
              fileDiagnostics = null;
            }}
          >
            <Icon name="x" size="sm" />
          </button>
        </span>
      </header>
      <!-- B10 — the workspace could show a file and not say that it no longer
           parses, which is the one thing an owner most wants to know about a
           file the agent just edited. Three states, and the third is the point:
           problems, checked-and-clean, and *not checked* for a language this
           runtime has no parser for. "Not checked" is never rendered as
           "no problems". -->
      {#if fileDiagnostics !== null && fileDiagnostics.available}
        {#if fileDiagnostics.diagnostics.length > 0}
          <ul class="problems" aria-label={`Problems in ${openPath}`}>
            {#each fileDiagnostics.diagnostics as problem (`${problem.line}:${problem.column}:${problem.message}`)}
              <li>
                <Icon name="warning" size="sm" />
                <span class="where">{problem.line}:{problem.column}</span>
                <span class="what">{problem.message}</span>
              </li>
            {/each}
          </ul>
        {:else if fileDiagnostics.checked}
          <p class="note clean">No syntax problems.</p>
        {:else}
          <p class="note">Not checked — no parser for this language here.</p>
        {/if}
      {/if}
      {#if fileLoading}
        <p class="note">Reading…</p>
      {:else if fileNotice !== null}
        <p class="note" role="status">{fileNotice}</p>
      {:else}
        <!-- Read-only by construction: this is a `<pre>`, not an editor. A
             change to this file is still a proposal the owner accepts.

             `{@html}` is safe here for the same structural reason it is in the
             transcript: `highlight()` escapes every character of the source at
             emit time and emits only `<span class="tok-…">`, so nothing the
             file contains can reach the DOM as markup. A language the
             highlighter does not ship a grammar for takes the interpolated
             branch below instead, which Svelte escapes. -->
        {#if rendered !== ""}
          <!-- eslint-disable-next-line svelte/no-at-html-tags -->
          <pre class="code"><code>{@html rendered}</code></pre>
        {:else}
          <pre class="code"><code>{fileText}</code></pre>
        {/if}
        {#if fileTruncated}
          <p class="note">Shown up to the viewer's size limit.</p>
        {/if}
      {/if}
    </div>
  {/if}
</section>

{#snippet node(entry: ProjectBrowseEntry, depth: number)}
  <li role="none" style={`--depth:${depth}`}>
    <div
      class="row"
      role="treeitem"
      aria-selected={openPath === entry.relative_path}
      aria-expanded={entry.is_directory ? Boolean(expanded[entry.relative_path]) : undefined}
    >
      {#if entry.is_directory}
        <button
          type="button"
          class="twisty"
          onclick={() => void toggle(entry)}
          aria-label={`${expanded[entry.relative_path] ? "Collapse" : "Expand"} ${entry.name}`}
        >
          <Icon
            name={expanded[entry.relative_path] ? "chevron-down" : "chevron-right"}
            size="sm"
          />
        </button>
      {:else}
        <span class="twisty spacer"></span>
      {/if}
      <button
        type="button"
        class="entry"
        class:selected={openPath === entry.relative_path}
        onclick={() => (entry.is_directory ? void toggle(entry) : void openFile(entry))}
        aria-label={entry.is_directory ? `Open ${entry.name}` : `Read ${entry.name}`}
      >
        <Icon name={entry.is_directory ? "folder" : "file"} size="sm" />
        <span class="entry-name">{entry.name}</span>
        {#if !entry.is_directory}
          <span class="entry-meta">{formatSize(entry.size_bytes)}</span>
        {/if}
      </button>
    </div>
    {#if entry.is_directory && expanded[entry.relative_path]}
      <ul role="group">
        {#if loadingPaths[entry.relative_path]}
          <li role="none" class="child-note" style={`--depth:${depth + 1}`}>Reading…</li>
        {:else if listings[entry.relative_path] === undefined}
          <li role="none" class="child-note" style={`--depth:${depth + 1}`}>
            Could not be read.
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
  .code-explorer {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    height: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    overflow: hidden;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding: 0.5rem 0.5rem 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
  }
  .head h2 {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    min-width: 0;
  }
  .repo {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    padding: 0;
    border: 0;
    border-radius: var(--r-sm);
    background: none;
    color: var(--text-muted);
    cursor: pointer;
  }
  .icon-btn.mention {
    font-size: 0.85rem;
    font-weight: 600;
  }
  .icon-btn:hover {
    background: var(--sunken);
    color: var(--text-1);
  }
  .tree-pane {
    flex: 1 1 auto;
    min-height: 6rem;
    overflow: auto;
    padding: 0.35rem 0.4rem;
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
    gap: 0.15rem;
    padding-left: calc(var(--depth, 0) * 0.75rem);
  }
  .twisty {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.1rem;
    height: 1.1rem;
    flex: none;
    padding: 0;
    border: 0;
    background: none;
    color: var(--text-muted);
    cursor: pointer;
  }
  .twisty.spacer {
    cursor: default;
  }
  .entry {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex: 1;
    min-width: 0;
    padding: 0.15rem 0.35rem;
    border: 0;
    border-radius: var(--r-sm);
    background: none;
    color: inherit;
    font: inherit;
    font-size: 0.8rem;
    text-align: left;
    cursor: pointer;
  }
  .entry:hover,
  .entry.selected {
    background: var(--sunken);
  }
  .entry.selected {
    color: var(--text-1);
    font-weight: 600;
  }
  .entry-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .entry-meta {
    margin-left: auto;
    color: var(--text-muted);
    font-size: 0.7rem;
    white-space: nowrap;
  }
  .child-note,
  .note {
    margin: 0;
    padding: 0.25rem 0.5rem;
    color: var(--text-muted);
    font-size: 0.78rem;
  }
  .child-note {
    padding-left: calc(var(--depth, 0) * 0.75rem + 1.1rem);
  }
  /* B10 — problems sit between the file's name and its text, where an editor
     puts them, and scroll on their own so a file with many never pushes the
     code off screen. */
  .problems {
    list-style: none;
    margin: 0;
    padding: 0.3rem 0.5rem;
    max-height: 7rem;
    overflow: auto;
    border-bottom: 1px solid var(--border);
    background: var(--warn-soft, var(--sunken));
  }
  .problems li {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    font-size: 0.76rem;
    color: var(--warn, var(--text-1));
    line-height: 1.5;
  }
  .problems .where {
    flex: none;
    font-variant-numeric: tabular-nums;
    opacity: 0.8;
  }
  .problems .what {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .note.clean {
    color: var(--ok, var(--text-muted));
  }
  .note.error {
    color: var(--danger, var(--text-muted));
  }
  .viewer {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 55%;
    border-top: 1px solid var(--border);
  }
  .viewer-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding: 0.3rem 0.4rem 0.3rem 0.75rem;
    border-bottom: 1px solid var(--border);
    min-width: 0;
  }
  .viewer-path {
    font-family: var(--font-mono, ui-monospace, monospace);
    font-size: 0.72rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    direction: rtl;
    text-align: left;
  }
  .viewer-actions {
    display: flex;
    align-items: center;
    gap: 0.15rem;
    flex: none;
  }
  .lang {
    color: var(--text-muted);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .code {
    flex: 1;
    min-height: 0;
    margin: 0;
    padding: 0.5rem 0.75rem;
    overflow: auto;
    font-family: var(--font-mono, ui-monospace, monospace);
    font-size: 0.72rem;
    line-height: 1.55;
    tab-size: 2;
    white-space: pre;
  }
</style>
