<script lang="ts">
  /**
   * Export this conversation (BUG-22).
   *
   * The order matters and is the whole design: **review, then choose, then
   * download**. The manifest is fetched first and shown in full — how many
   * messages, which files, and the redaction policy in words — so the owner
   * knows what is about to leave the machine before a format exists. Nothing
   * here decides scope; the server authorises the export by the session the
   * dialog was opened from.
   *
   * Printing is a first-class peer of downloading rather than an afterthought:
   * `window.print()` against the dedicated print stylesheet in ChatView/BuildView
   * is what makes the browser's own Save as PDF produce a document instead of a
   * screenshot of the application chrome.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { TranscriptExportManifest } from "../apiTypes";
  import Icon from "./Icon.svelte";

  let {
    sessionId,
    onclose,
    onprint,
  }: { sessionId: string; onclose: () => void; onprint?: () => void } = $props();

  type Format = "html" | "markdown" | "pdf";

  const FORMATS: Array<{ id: Format; label: string; detail: string }> = [
    { id: "html", label: "HTML", detail: "One self-contained page. No scripts, nothing fetched." },
    { id: "markdown", label: "Markdown", detail: "Plain text you can edit or commit anywhere." },
    { id: "pdf", label: "PDF", detail: "A paginated document for filing or sending on." },
  ];

  let manifest = $state<TranscriptExportManifest | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let format = $state<Format>("html");
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let fieldError = $state<string | null>(null);
  let dialogElement = $state<HTMLDialogElement>();

  onMount(() => {
    const returnFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    if (dialogElement) {
      if (typeof dialogElement.showModal === "function") dialogElement.showModal();
      else dialogElement.setAttribute("open", "");
    }
    return () => returnFocus?.focus();
  });

  function cancel(event: Event) {
    event.preventDefault();
    onclose();
  }

  function backdrop(event: MouseEvent) {
    if (event.target === event.currentTarget) onclose();
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      manifest = await api.sessionExportManifest(sessionId);
    } catch (error) {
      loadError =
        error instanceof ApiError && error.status === 404
          ? "This conversation is no longer available to export."
          : "Could not read what this conversation contains.";
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void sessionId;
    void load();
  });

  function downloadName(): string {
    const slug = (manifest?.title ?? "")
      .replace(/[^A-Za-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase()
      .slice(0, 60);
    const extension = format === "markdown" ? "md" : format;
    return `${slug || `conversation-${sessionId.slice(0, 12)}`}.${extension}`;
  }

  async function run() {
    if (busy) return;
    busy = true;
    notice = null;
    fieldError = null;
    try {
      await api.exportSession(sessionId, format, downloadName());
      notice = `Exported as ${downloadName()}. Check your downloads.`;
    } catch (error) {
      // Field-level rather than generic: the owner needs to know whether the
      // format was refused, the conversation vanished, or the runtime is down.
      if (error instanceof ApiError && error.reasonCode === "export_format_unsupported") {
        fieldError = "That format is not available. Choose HTML, Markdown, or PDF.";
      } else if (error instanceof ApiError && error.status === 404) {
        fieldError = "This conversation is no longer available to export.";
      } else {
        fieldError = "The export did not complete — could not reach the local runtime.";
      }
    } finally {
      busy = false;
    }
  }
</script>

<dialog
  class="dialog"
  bind:this={dialogElement}
  aria-labelledby="export-title"
  oncancel={cancel}
  onclick={backdrop}
>
    <header>
      <h2 id="export-title">Export conversation</h2>
      <button type="button" class="icon-btn" aria-label="Close" onclick={onclose}>×</button>
    </header>

    {#if loading}
      <p class="muted" role="status">Reading what this conversation contains…</p>
    {:else if loadError !== null}
      <p class="error" role="alert">{loadError}</p>
      <button type="button" class="btn btn-sm" onclick={() => void load()}>Try again</button>
    {:else if manifest !== null}
      <div class="review">
        <h3>What will be included</h3>
        <ul class="facts">
          <li><strong>{manifest.message_count}</strong> messages</li>
          <li><strong>{manifest.file_count}</strong> attached files</li>
          <li class="title-fact">Titled <strong>{manifest.title}</strong></li>
        </ul>
        {#if manifest.files.length > 0}
          <ul class="files">
            {#each manifest.files as file (file.filename + file.byte_size)}
              <li>
                <Icon name="file" size="sm" />
                <span class="file-name">{file.filename}</span>
                <span class="file-meta">{file.media_type} · {file.byte_size} bytes</span>
              </li>
            {/each}
          </ul>
        {/if}
        <p class="policy">{manifest.redaction_policy}</p>
      </div>

      <fieldset class="formats">
        <legend>Format</legend>
        {#each FORMATS as option (option.id)}
          <label class="format" class:selected={format === option.id}>
            <input type="radio" name="export-format" value={option.id} bind:group={format} />
            <span class="format-label">{option.label}</span>
            <span class="format-detail">{option.detail}</span>
          </label>
        {/each}
      </fieldset>

      {#if fieldError !== null}<p class="error" role="alert">{fieldError}</p>{/if}
      {#if notice !== null}<p class="ok" role="status">{notice}</p>{/if}

      <footer>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => onprint?.()}>
          <Icon name="file" size="sm" /> Print / Save as PDF
        </button>
        <span class="spacer"></span>
        <button type="button" class="btn btn-ghost btn-sm" onclick={onclose}>Close</button>
        <button type="button" class="btn btn-primary btn-sm" disabled={busy} onclick={() => void run()}>
          {busy ? "Exporting…" : "Export"}
        </button>
      </footer>
    {/if}
</dialog>

<style>
  .dialog::backdrop {
    background: var(--overlay);
  }
  .dialog {
    color:var(--text-1);
    width: min(34rem, 100%);
    max-height: min(85vh, 46rem);
    overflow-y: auto;
    display: grid;
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
  h3 { margin: 0 0 0.35rem; font-size: 0.86rem; }
  .review {
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .facts { display: flex; flex-wrap: wrap; gap: 0.9rem; list-style: none; margin: 0; padding: 0; font-size: 0.82rem; color: var(--text-2); }
  .title-fact { overflow-wrap: anywhere; }
  .files { list-style: none; margin: 0.6rem 0 0; padding: 0; display: grid; gap: 0.25rem; }
  .files li { display: flex; align-items: center; gap: 0.4rem; font-size: var(--text-sm); color: var(--text-2); }
  .file-name { font-weight: 600; overflow-wrap: anywhere; }
  .file-meta { color: var(--text-2); }
  .policy {
    margin: 0.7rem 0 0; padding-left: 0.6rem;
    border-left: 3px solid var(--accent-border);
    color: var(--text-2); font-size: var(--text-sm); line-height: 1.45;
  }
  .formats { display: grid; gap: 0.4rem; border: 0; padding: 0; margin: 0; }
  .formats legend { font-size: 0.82rem; font-weight: 650; padding: 0; margin-bottom: 0.3rem; }
  .format {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: baseline;
    gap: 0.2rem 0.55rem;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    cursor: pointer;
  }
  .format.selected { border-color: var(--accent-border); background: var(--accent-soft); }
  .format input { grid-row: 1 / 3; align-self: center; }
  .format-label { font-weight: 650; font-size: 0.86rem; }
  .format-detail { grid-column: 2; color: var(--text-2); font-size: var(--text-sm); }
  footer { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
  .spacer { flex: 1; }
  .muted { color: var(--text-2); font-size: var(--text-sm); margin: 0; }
  .error { color: var(--danger); font-size: 0.82rem; margin: 0; }
  .ok { color: var(--ok); font-size: 0.82rem; margin: 0; font-weight: 600; }
</style>
