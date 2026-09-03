<script lang="ts">
  /**
   * Browse to a folder instead of spelling one (BUG-251).
   *
   * Four fields asked the owner to *type* an absolute filesystem location:
   * attaching an existing project folder, approving a models folder, naming a
   * workspace file in the task composer, and picking a Build repository. None of
   * them could be browsed, so all four required knowing exactly how a directory
   * is written on this machine.
   *
   * A browser cannot fix that on its own — `<input type="file">` gives contents,
   * `webkitdirectory` gives relative names, and the File System Access API gives
   * an opaque handle and only in Chromium. The host answers instead
   * (`GET /api/host/paths`), listing directory **names** and nothing else, and
   * this dialog is the single place that reads it.
   *
   * Choosing here changes nothing. It fills a field. Whatever the field does
   * next — attach, approve, index — is still governed exactly as it was, which is
   * why a picker that can reach outside the workspace is correct: these fields
   * exist precisely to name a folder that is not in it.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { HostPathListing } from "../apiTypes";
  import Icon from "./Icon.svelte";

  let {
    /** Where to open. Empty starts at the top of the machine. */
    start = "",
    /** Whether a file is a valid answer, or only a folder. */
    mode = "folder",
    /**
     * For a field that wants a location *inside* the workspace. The picker opens
     * at the workspace root, will not go above it, and answers with a path
     * relative to it — which is the only thing such a field can accept.
     */
    insideWorkspace = false,
    title = "Choose a folder",
    onchoose,
    onclose,
  }: {
    start?: string;
    mode?: "folder" | "file";
    insideWorkspace?: boolean;
    title?: string;
    onchoose: (path: string) => void;
    onclose: () => void;
  } = $props();

  let listing = $state<HostPathListing | null>(null);
  let loading = $state(true);
  let failure = $state<string | null>(null);
  let selected = $state<string | null>(null);
  let dialogElement = $state<HTMLDialogElement>();

  // At the top of the machine there is nothing to choose — a drive letter is
  // somewhere to go, not somewhere to attach. Everywhere else the folder being
  // looked at is the default answer, so "open it, press Use" works without
  // having to select a folder from inside itself.
  const current = $derived(listing?.path ?? "");
  // A folder that could not be read is not a folder the owner may choose. It
  // still has a path — that is what makes it worth guarding: without this, the
  // default answer for a location that is gone is the location that is gone.
  const readable = $derived(listing !== null && !listing.missing && failure === null);
  const chosen = $derived(
    readable ? (selected ?? (mode === "folder" ? current : null)) : null,
  );
  const separator = $derived(listing?.separator ?? "/");
  const root = $derived(insideWorkspace ? (listing?.workspace_root ?? "") : "");
  /** At the confine's own root there is nowhere above to go. */
  const atRoot = $derived(root !== "" && current === root);

  /**
   * What the field actually receives. A workspace field gets a relative path,
   * because an absolute one is exactly what it refuses; everything else gets the
   * absolute path, because that is the thing a browser could not produce.
   */
  function forField(path: string): string {
    if (root === "") return path;
    if (path === root) return "";
    return path.startsWith(root + separator) ? path.slice(root.length + separator.length) : path;
  }

  onMount(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (dialogElement) {
      if (typeof dialogElement.showModal === "function") dialogElement.showModal();
      else dialogElement.setAttribute("open", "");
    }
    return () => returnFocus?.focus();
  });

  async function go(path: string) {
    loading = true;
    failure = null;
    selected = null;
    try {
      const next = await api.hostPaths(path, mode === "file");
      // A workspace field opens at the workspace, not at the top of the machine
      // — the top would only offer places the field cannot accept. The host is
      // the only thing that knows where the workspace is, so the first listing
      // is what makes the second one possible.
      if (insideWorkspace && path === "" && next.workspace_root !== "") {
        listing = await api.hostPaths(next.workspace_root, mode === "file");
      } else {
        listing = next;
      }
    } catch (error) {
      failure =
        error instanceof ApiError
          ? "That location could not be read."
          : "Could not reach the local runtime.";
    } finally {
      loading = false;
    }
  }

  function activate(entry: { path: string; is_directory: boolean }) {
    if (entry.is_directory) void go(entry.path);
    else selected = entry.path;
  }

  function confirm() {
    if (chosen === null || chosen === "") return;
    onchoose(forField(chosen));
  }

  $effect(() => {
    void go(start);
  });
</script>

<dialog
  class="dialog"
  bind:this={dialogElement}
  aria-labelledby="path-picker-title"
  oncancel={(event) => { event.preventDefault(); onclose(); }}
  onclick={(event) => { if (event.target === event.currentTarget) onclose(); }}
>
  <header>
    <h2 id="path-picker-title">{title}</h2>
    <button type="button" class="icon-btn" aria-label="Close" onclick={onclose}>×</button>
  </header>

  <div class="crumb">
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      disabled={loading || listing === null || listing.parent === null || atRoot}
      onclick={() => void go(listing?.parent ?? "")}
      aria-label="Up one level"
    >
      <Icon name="folder-up" size={14} />
    </button>
    <span class="here" title={current}>{current || "This computer"}</span>
  </div>

  {#if failure !== null}
    <p class="error" role="alert">{failure}</p>
  {:else if loading}
    <p class="muted" role="status">Reading…</p>
  {:else if listing !== null && listing.missing}
    <p class="error" role="alert">That location is gone, or Raiker cannot read it.</p>
  {:else if listing !== null && listing.entries.length === 0}
    <p class="muted">Nothing here.</p>
  {:else if listing !== null}
    <ul class="entries">
      {#each listing.entries as entry (entry.path)}
        <li>
          <button
            type="button"
            class="entry"
            class:selected={selected === entry.path}
            aria-current={selected === entry.path ? "true" : undefined}
            onclick={() => activate(entry)}
          >
            <Icon name={entry.is_directory ? "folder" : "file"} size={14} />
            <span>{entry.name}</span>
          </button>
        </li>
      {/each}
    </ul>
    {#if listing.truncated}
      <p class="muted">Showing the first {listing.entries.length}. Open a subfolder to narrow it.</p>
    {/if}
  {/if}

  <footer>
    <span class="picked" title={chosen ?? ""}>{chosen || "Nothing selected"}</span>
    <button type="button" class="btn btn-ghost btn-sm" onclick={onclose}>Cancel</button>
    <button
      type="button"
      class="btn btn-primary btn-sm"
      disabled={chosen === null || chosen === ""}
      onclick={confirm}
    >
      Use
    </button>
  </footer>
</dialog>

<style>
  .dialog::backdrop { background: color-mix(in srgb, #0b1417 55%, transparent); }
  .dialog {
    color: var(--text-1);
    width: min(30rem, 100%);
    max-height: min(80vh, 40rem);
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr) auto;
    gap: var(--space-3);
    padding: var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
  header h2 { margin: 0; font-size: 1.05rem; }
  .icon-btn {
    border: 0; background: transparent; color: var(--text-3);
    font-size: 1.2rem; line-height: 1; cursor: pointer; padding: 0.1rem 0.35rem;
  }
  .icon-btn:hover { color: var(--text-1); }
  .crumb { display: flex; align-items: center; gap: var(--space-2); min-width: 0; }
  /* A path is long by nature and its tail is the part that identifies the
     folder, so it truncates from the front rather than wrapping the dialog. */
  .here {
    flex: 1; min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: var(--text-xs); color: var(--text-2);
  }
  .entries { list-style: none; margin: 0; padding: 0; overflow-y: auto; display: grid; gap: 1px; }
  .entry {
    display: flex; align-items: center; gap: 0.45rem; width: 100%;
    padding: 0.32rem 0.45rem;
    border: 1px solid transparent; border-radius: var(--r-sm);
    background: transparent; color: var(--text-1);
    font: inherit; font-size: var(--text-sm); text-align: left; cursor: pointer;
  }
  .entry span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .entry:hover { background: var(--sunken); }
  .entry.selected { border-color: var(--accent-border); background: var(--accent-soft); }
  .entry:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
  footer { display: flex; align-items: center; gap: var(--space-2); }
  .picked {
    flex: 1; min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: var(--text-xs); color: var(--text-3);
  }
  .muted { margin: 0; color: var(--text-3); font-size: var(--text-xs); }
  .error { margin: 0; color: var(--danger, var(--text-1)); font-size: var(--text-xs); }
</style>
