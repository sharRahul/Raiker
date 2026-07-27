<script lang="ts">
  /**
   * View-only inspector for a file attached to the current chat (BUG-07).
   *
   * The pane is a reading surface and nothing else: it has no upload, no edit,
   * no delete, and no download control, and it renders only what the
   * session-authorized preview endpoint returned.
   *
   * Nothing here executes document content. Markdown goes through the shared
   * escape-first renderer (`Markdown.svelte`), which turns `<script>` in a file
   * into visible characters rather than a tag; plain text and spreadsheet cells
   * are interpolated as text, so Svelte escapes them; a PDF is handed to the
   * browser's own viewer as a same-origin blob URL fetched with the session
   * token. An unsupported or unreadable file states that in words instead of
   * showing an empty pane.
   *
   * Landmark, not modal: it is a `complementary` region so the transcript stays
   * reachable behind it. Escape closes it and focus returns to the chip that
   * opened it. Wide layouts place it beside the conversation; below the split
   * breakpoint it becomes a dismissible sheet (see the media query).
   */
  import Icon from "./Icon.svelte";
  import Markdown from "./Markdown.svelte";
  import type { AttachmentPreview } from "../apiTypes";

  let {
    preview,
    filename,
    loading = false,
    error = null,
    pdfObjectUrl = null,
    onclose,
  }: {
    preview: AttachmentPreview | null;
    filename: string;
    loading?: boolean;
    error?: string | null;
    pdfObjectUrl?: string | null;
    onclose: () => void;
  } = $props();

  let closeButton = $state<HTMLButtonElement>();
  let returnFocusTo: HTMLElement | null = null;

  $effect(() => {
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    queueMicrotask(() => closeButton?.focus());
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      onclose();
    };
    window.addEventListener("keydown", onKeydown);
    return () => {
      window.removeEventListener("keydown", onKeydown);
      returnFocusTo?.focus();
      returnFocusTo = null;
    };
  });

  // Stated in the user's terms. An unknown code still surfaces, verbatim, so a
  // reason is never swallowed — it is only ever additional detail.
  const UNAVAILABLE_TEXT: Record<string, string> = {
    unsupported_for_preview: "Raiker cannot preview this kind of file yet.",
    unreadable: "This file could not be read.",
    content_does_not_match_media_type:
      "This file's contents do not match the type it was uploaded as, so it was not opened.",
    pdf_encrypted: "This PDF is encrypted, so it was not opened.",
    pdf_unreadable: "This PDF could not be read.",
    pdf_extraction_unavailable: "PDF reading is not available on this install.",
    docx_too_large: "This document is too large to preview safely.",
    xlsx_too_large: "This spreadsheet is too large to preview safely.",
  };

  const unavailableText = $derived(
    preview === null
      ? ""
      : (UNAVAILABLE_TEXT[preview.unavailable_reason ?? ""] ?? "This file cannot be previewed."),
  );
</script>

<aside class="file-inspector" aria-label="File preview">
  <header>
    <div class="titles">
      <h2>{preview?.filename || filename}</h2>
      {#if preview !== null}
        <p>{preview.media_type}</p>
      {/if}
    </div>
    <button
      type="button"
      class="btn btn-ghost btn-sm"
      onclick={onclose}
      bind:this={closeButton}
      aria-label="Close file preview"
    >
      <Icon name="x" size={15} />
    </button>
  </header>

  <div class="body">
    {#if loading}
      <p class="muted" role="status">Opening {filename}…</p>
    {:else if error !== null}
      <p class="error-line" role="alert">{error}</p>
    {:else if preview === null}
      <p class="muted">Nothing to show.</p>
    {:else if preview.kind === "unavailable"}
      <p class="muted">{unavailableText}</p>
      {#if preview.unavailable_reason}
        <p class="reason-code">{preview.unavailable_reason}</p>
      {/if}
    {:else if preview.kind === "markdown"}
      <Markdown text={preview.text} />
    {:else if preview.kind === "text"}
      <pre class="text-preview">{preview.text}</pre>
    {:else if preview.kind === "table"}
      <div class="table-scroll">
        <table>
          <tbody>
            {#each preview.rows as row, r (r)}
              <tr>
                {#each row as cell, c (c)}
                  <td>{cell}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if preview.kind === "pdf"}
      {#if pdfObjectUrl !== null}
        <object class="pdf-frame" data={pdfObjectUrl} type="application/pdf" aria-label={`${preview.filename} (PDF)`}>
          <p class="muted">This browser cannot display the PDF inline.</p>
        </object>
      {:else}
        <p class="muted" role="status">Loading the PDF…</p>
      {/if}
    {/if}

    {#if preview !== null && preview.truncated}
      <p class="muted truncation">Showing the beginning of this file only.</p>
    {/if}
  </div>
</aside>

<style>
  .file-inspector {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-1);
    padding: var(--space-4);
    overflow: hidden;
  }
  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .titles h2 {
    margin: 0;
    font-size: 0.95rem;
    overflow-wrap: anywhere;
  }
  .titles p {
    margin: 0.15rem 0 0;
    color: var(--text-3);
    font-size: 0.72rem;
    overflow-wrap: anywhere;
  }
  .body {
    flex: 1;
    min-height: 0;
    overflow: auto;
    font-size: 0.84rem;
  }
  .muted {
    color: var(--text-3);
  }
  .truncation {
    margin-top: var(--space-3);
    font-size: 0.75rem;
  }
  .reason-code {
    margin: 0.35rem 0 0;
    color: var(--text-3);
    font-family: var(--font-mono, monospace);
    font-size: 0.7rem;
  }
  .text-preview {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: var(--font-mono, monospace);
    font-size: 0.78rem;
    line-height: 1.5;
  }
  /* A wide sheet is unreadable if it forces the whole page sideways, so the
     table scrolls inside its own box. */
  .table-scroll {
    overflow-x: auto;
  }
  table {
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  td {
    border: 1px solid var(--border);
    padding: 0.2rem 0.45rem;
    vertical-align: top;
    white-space: pre-wrap;
  }
  /* First row of a spreadsheet is nearly always a header; weight it without
     claiming a semantic <th> the file never actually declared. */
  tr:first-child td {
    font-weight: 600;
    background: var(--neutral-soft);
  }
  .pdf-frame {
    width: 100%;
    height: min(70vh, 40rem);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
  }
  .error-line {
    color: var(--danger);
    margin: 0;
  }
  /* Below the split breakpoint a column beside the transcript is too narrow to
     read, so the inspector becomes a dismissible sheet over the conversation. */
  @media (max-width: 63.9rem) {
    .file-inspector {
      position: fixed;
      inset: auto 0 0 0;
      z-index: 80;
      max-height: 82vh;
      border-radius: var(--r-lg) var(--r-lg) 0 0;
      box-shadow: var(--shadow-2);
      padding-bottom: calc(var(--space-4) + env(safe-area-inset-bottom));
    }
  }
</style>
