<script lang="ts">
  /**
   * VIS2-12 — Build's third pane, as the object of work.
   *
   * The pane existed; what it lacked was a subject. Two unrelated things were
   * stacked into one column — background work and the governed terminal — each
   * with its own toggle in the header, so the column meant "whatever you last
   * switched on" rather than "what you are looking at". Meanwhile the two
   * things a coding session actually reviews had nowhere to live: **the change
   * the turn made**, which existed only as a *proposed* diff attached to an
   * approval and vanished the moment it was applied, and **the file you are
   * reading**, which the explorer could open but only inside itself.
   *
   * So the column becomes one pane with four views of one workspace:
   *
   *   Changes    what is uncommitted in the working tree, right now
   *   Preview    the file currently open, read-only
   *   Terminal   the governed command output
   *   Runs       background work and standing agents
   *
   * Two rules make it a workbench rather than a fourth navigation bar.
   *
   * **It focuses itself.** Opening a file selects Preview; starting a command
   * selects Terminal; finishing a turn that changed files selects Changes. The
   * owner is looking at something because they did something, and a pane that
   * makes them find the right tab afterwards has made them do the work twice.
   * The caller owns that decision (`tab` is bindable) because only the caller
   * knows what just happened.
   *
   * **It closes when nothing warrants it.** The transcript is the primary
   * object on this surface; a permanently open third column takes width from it
   * to show an empty state.
   *
   * Nothing here is a new authority. Changes is a read of the working tree
   * through the same helpers a commit proposal is built from — so this pane and
   * that commit describe one change set — and every other view is the component
   * that already owned it.
   */
  import BuildSidePanel from "./BuildSidePanel.svelte";
  import CommandOutputPane from "./CommandOutputPane.svelte";
  import DiffView from "./DiffView.svelte";
  import Icon from "./Icon.svelte";
  import PageState from "./PageState.svelte";
  import { api, ApiError } from "../api";
  import type {
    CodeRepoChangesView,
    CodeRepoFileView,
    ProjectsList,
  } from "../apiTypes";
  import { ARTIFACT_TABS, changesSummary, type ArtifactTab } from "../buildArtifacts";

  let {
    tab = $bindable("changes"),
    repoId = null,
    repoLabel = "",
    previewPath = null,
    sessionId = null,
    visible = true,
    projectId = null,
    projects = null,
    /** Bumped by the caller when a turn ends, so Changes re-reads without a button. */
    revision = 0,
    terminalOpen = $bindable(false),
    onclose,
  }: {
    tab?: ArtifactTab;
    repoId?: string | null;
    repoLabel?: string;
    previewPath?: string | null;
    sessionId?: string | null;
    visible?: boolean;
    projectId?: string | null;
    projects?: ProjectsList | null;
    revision?: number;
    terminalOpen?: boolean;
    onclose: () => void;
  } = $props();

  let changes = $state<CodeRepoChangesView | null>(null);
  let changesError = $state<string | null>(null);
  let changesLoading = $state(false);

  let file = $state<CodeRepoFileView | null>(null);
  let fileError = $state<string | null>(null);
  let fileLoading = $state(false);

  /**
   * Read the working tree when this pane is showing Changes, and again whenever
   * the caller says a turn ended.
   *
   * Deliberately not a poll. A repository does not change on its own, it changes
   * because something ran — so the two moments worth re-reading at are "you
   * looked" and "a turn finished", and a timer would be asking a question
   * nobody's action had made stale.
   */
  $effect(() => {
    const id = repoId;
    // Named so the effect re-runs when the caller bumps it.
    void revision;
    if (tab !== "changes" || id === null) return;
    let cancelled = false;
    changesLoading = true;
    void api
      .readCodeRepoChanges(id)
      .then((view) => {
        if (cancelled) return;
        changes = view;
        changesError = null;
      })
      .catch((error) => {
        if (cancelled) return;
        // The previous answer stays on screen rather than blanking: a failed
        // read is not evidence the working tree is clean, and "no changes" is
        // the one thing this pane must never say without having looked.
        changesError =
          error instanceof ApiError ? error.message : "Couldn't read the working tree.";
      })
      .finally(() => {
        if (!cancelled) changesLoading = false;
      });
    return () => {
      cancelled = true;
    };
  });

  $effect(() => {
    const id = repoId;
    const path = previewPath;
    if (tab !== "preview" || id === null || path === null) return;
    let cancelled = false;
    fileLoading = true;
    void api
      .readCodeRepoFile(id, path)
      .then((view) => {
        if (cancelled) return;
        file = view;
        fileError = null;
      })
      .catch((error) => {
        if (cancelled) return;
        file = null;
        fileError = error instanceof ApiError ? error.message : "Couldn't read that file.";
      })
      .finally(() => {
        if (!cancelled) fileLoading = false;
      });
    return () => {
      cancelled = true;
    };
  });

  const summary = $derived(changesSummary(changes));
</script>

<section class="artifact-pane" aria-label="Workbench">
  <div class="pane-head">
    <div class="tabs" role="tablist" aria-label="Workbench views">
      {#each ARTIFACT_TABS as entry (entry.id)}
        <button
          type="button"
          role="tab"
          id={`artifact-tab-${entry.id}`}
          aria-selected={tab === entry.id}
          aria-controls={`artifact-panel-${entry.id}`}
          onclick={() => (tab = entry.id)}
        >
          {entry.label}
          <!-- VIS2-13 — one token, and only when it is not the ordinary
               state. A count of changed files is the exception worth seeing;
               "0 changes" beside a tab called Changes is noise. -->
          {#if entry.id === "changes" && summary.count > 0}
            <span class="tab-count">{summary.count}</span>
          {/if}
        </button>
      {/each}
    </div>
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      onclick={onclose}
      aria-label="Close the workbench"
      title="Close the workbench"
    >
      <Icon name="x" size="sm" />
    </button>
  </div>

  {#if tab === "changes"}
    <div
      id="artifact-panel-changes"
      role="tabpanel"
      aria-labelledby="artifact-tab-changes"
      class="panel"
    >
      {#if repoId === null}
        <PageState
          state="empty"
          title="No repository connected"
          detail="Connect one from the header to see what a turn changed."
        />
      {:else if changesError}
        <PageState state="error" title="Couldn't read the working tree" detail={changesError} />
      {:else if changes === null && changesLoading}
        <PageState state="loading" title="Reading the working tree…" />
      {:else if changes !== null && changes.reason_code === "not_a_git_repository"}
        <!-- Not a failure, and not "no changes": a folder under no version
             control has nothing to compare against, which is a different
             answer and a different thing for the owner to do about it. -->
        <PageState
          state="empty"
          title="{repoLabel || 'This folder'} is not a git repository"
          detail="There is no history to compare the working tree against."
        />
      {:else if changes !== null && changes.root_missing}
        <PageState
          state="empty"
          title="Nothing on this machine to read"
          detail={changes.reason_code === "repo_not_checked_out"
            ? "This is a GitHub coordinate, not a checkout."
            : "That folder has moved or been removed."}
        />
      {:else if changes !== null && changes.entries.length === 0}
        <PageState
          state="empty"
          title="No uncommitted changes"
          detail="The working tree matches the last commit."
        />
      {:else if changes !== null}
        <p class="changes-lead">
          {summary.text}
          {#if changes.truncated}
            <span class="note">More files changed than are listed.</span>
          {/if}
        </p>
        <ul class="changed-files" aria-label="Changed files">
          {#each changes.entries as entry (entry.path)}
            <li>
              <span class="state" data-state={entry.state}>{entry.state}</span>
              <span class="path" title={entry.path}>
                {#if entry.previous_path}{entry.previous_path} → {/if}{entry.path}
              </span>
            </li>
          {/each}
        </ul>
        {#if changes.diff}
          <DiffView diff={changes.diff} open={true} />
          {#if changes.diff_truncated}
            <p class="note">
              This diff is longer than the pane renders. Open the files to read the rest.
            </p>
          {/if}
        {/if}
      {/if}
    </div>
  {:else if tab === "preview"}
    <div
      id="artifact-panel-preview"
      role="tabpanel"
      aria-labelledby="artifact-tab-preview"
      class="panel"
    >
      {#if previewPath === null}
        <PageState
          state="empty"
          title="No file open"
          detail="Open one from Files and it is read here."
        />
      {:else if fileError}
        <PageState state="error" title="Couldn't read that file" detail={fileError} />
      {:else if file === null && fileLoading}
        <PageState state="loading" title="Reading…" />
      {:else if file !== null && !file.readable}
        <PageState
          state="empty"
          title="This file cannot be shown here"
          detail={file.reason_code.replaceAll("_", " ")}
        />
      {:else if file !== null}
        <p class="preview-path" title={file.path}>{file.path}</p>
        <pre class="preview-text">{file.text}</pre>
        {#if file.truncated}
          <p class="note">Shown up to this build's reading limit.</p>
        {/if}
      {/if}
    </div>
  {:else if tab === "terminal"}
    <div
      id="artifact-panel-terminal"
      role="tabpanel"
      aria-labelledby="artifact-tab-terminal"
      class="panel terminal-panel"
    >
      <CommandOutputPane {sessionId} {visible} bind:open={terminalOpen} />
    </div>
  {:else}
    <div
      id="artifact-panel-runs"
      role="tabpanel"
      aria-labelledby="artifact-tab-runs"
      class="panel runs-panel"
    >
      <BuildSidePanel {projectId} {projects} {onclose} />
    </div>
  {/if}
</section>

<style>
  .artifact-pane {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    overflow: hidden;
  }
  .pane-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0.35rem 0.4rem 0.35rem 0.5rem;
    border-bottom: 1px solid var(--border);
    background: var(--sunken);
  }
  .tabs {
    display: flex;
    gap: 0.15rem;
    flex: 1;
    min-width: 0;
    overflow-x: auto;
  }
  .tabs button {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.25rem 0.5rem;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: var(--text-xs);
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
  }
  .tabs button:hover { color: var(--text-1); }
  .tabs button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text-1);
    box-shadow: inset 0 0 0 1px var(--border);
  }
  .tabs button:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .tab-count {
    padding: 0 0.3rem;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    color: var(--accent);
    font-size: var(--text-2xs);
    font-variant-numeric: tabular-nums;
  }
  .panel {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: var(--space-3);
  }
  /* The two panels that own their own frame keep it; padding here would draw a
     second border inside the first. */
  .terminal-panel, .runs-panel { padding: 0; }
  .changes-lead { margin: 0 0 var(--space-2); color: var(--text-2); font-size: var(--text-sm); }
  .changed-files { list-style: none; margin: 0 0 var(--space-3); padding: 0; display: grid; gap: 0.2rem; }
  .changed-files li {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    font-size: var(--text-xs);
    min-width: 0;
  }
  .state {
    flex: none;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: var(--text-2xs);
    min-width: 4.5rem;
  }
  /* VIS2-18 — a deletion is the one working-tree state worth a second glance;
     the rest are information, and colouring all five would make none of them
     mean anything. */
  .state[data-state="deleted"] { color: var(--danger); }
  .path {
    color: var(--text-1);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .preview-path {
    margin: 0 0 var(--space-2);
    color: var(--text-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    overflow-wrap: anywhere;
  }
  .preview-text {
    margin: 0;
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    line-height: 1.55;
    overflow-x: auto;
    white-space: pre;
  }
  .note { margin: var(--space-2) 0 0; color: var(--text-3); font-size: var(--text-xs); }
</style>
