<script lang="ts">
  /**
   * The inspector: one pane for looking at a file, and at where something came
   * from (BUG-07, BUG-26, BUG-27, BUG-28).
   *
   * It renders only what the session-authorized endpoints returned, and it
   * executes nothing. Markdown goes through the shared escape-first renderer
   * (`Markdown.svelte`), which turns `<script>` in a file into visible
   * characters rather than a tag; plain text, source excerpts and spreadsheet
   * cells are interpolated as text, so Svelte escapes them; a PDF or an image is
   * handed to the browser as a same-origin blob URL fetched with the session
   * token — never a remote URL, and never bytes the server has not just
   * re-validated. An unsupported or unreadable file states that in words instead
   * of showing an empty pane.
   *
   * Three things it does beyond reading, each deliberately narrow:
   *
   * * **Image inspection** (BUG-26) is a CSS transform on the picture already on
   *   screen. `ImageViewport` owns it; the stored artifact is never touched.
   * * **A source passage** (BUG-27) is bounded plain text plus two integers
   *   naming the run to mark. The highlight is applied by *slicing that text*,
   *   never by rendering markup the source supplied.
   * * **Download** (BUG-28) is the one action here that produces something
   *   outside the pane, and it is still a read: the same authorization as
   *   preview, bytes the server serves as `application/octet-stream`, and a
   *   stated state for every outcome including refusal.
   *
   * Landmark, not modal: it is a `complementary` region so the transcript stays
   * reachable behind it. Escape closes it and focus returns to the control that
   * opened it. Wide layouts place it beside the conversation; below the split
   * breakpoint it becomes a dismissible sheet (see the media query).
   */
  import Icon from "./Icon.svelte";
  import ImageViewport from "./ImageViewport.svelte";
  import Markdown from "./Markdown.svelte";
  import SourceAnchorLinks from "./SourceAnchorLinks.svelte";
  import { splitExcerpt } from "../citations";
  import type { AttachmentPreview, SourceExcerptView } from "../apiTypes";

  let {
    preview,
    filename,
    loading = false,
    error = null,
    objectUrl = null,
    source = null,
    sourceLoading = false,
    onclose,
    ondownload = null,
    downloadState = "idle",
    downloadError = null,
  }: {
    preview: AttachmentPreview | null;
    filename: string;
    loading?: boolean;
    error?: string | null;
    /** Blob URL for the bytes of a PDF or image preview; null until fetched. */
    objectUrl?: string | null;
    /** BUG-27 — a resolved source passage to show alongside (or instead of) a file. */
    source?: SourceExcerptView | null;
    sourceLoading?: boolean;
    onclose: () => void;
    /** BUG-28 — omitted when this pane has nothing downloadable. */
    ondownload?: (() => void | Promise<void>) | null;
    downloadState?: "idle" | "working" | "done";
    downloadError?: string | null;
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

  // BUG-27 — every state this resolution can be in, said plainly. None of these
  // is an error: "the conversation was deleted" is a fact the owner is entitled
  // to, and a dead **View source** that silently did nothing was worse than all
  // of them.
  const SOURCE_STATUS_TEXT: Record<string, string> = {
    resolved: "",
    no_provenance: "This record did not store where it came from, so there is no source to open.",
    source_deleted: "The conversation this came from has been deleted, so its source cannot be shown.",
    source_changed: "The source no longer contains this passage, so it is shown without a highlight.",
    unsupported_source: "This source has no text passage to open at — it can be opened as a file instead.",
    not_authorized: "This account cannot read the source this came from.",
  };
  const sourceNote = $derived(
    source === null ? "" : (SOURCE_STATUS_TEXT[source.status] ?? "This source could not be resolved."),
  );

  // How the passage on screen was located. Each phrasing states exactly what
  // was checked, because "verified" and "found by searching for the words" are
  // genuinely different guarantees and a reader is entitled to know which one
  // they have. C6/C4 adds the two the citation ledger produces.
  const RESOLUTION_TEXT: Record<string, string> = {
    stored_coordinates: "Verified from stored coordinates",
    matching_text: "Located by matching text",
    answer_quote: "Located by matching this answer's own words",
    recorded_passage: "Exactly what this turn received",
    whole_source: "The whole of this source was read",
  };

  /** The excerpt split into before / passage / after, so the marked run is a
   *  slice of the text rather than markup the source got to choose. */
  const sourceParts = $derived(
    source === null
      ? null
      : splitExcerpt(source.excerpt, source.highlight_start, source.highlight_length),
  );

  // Only a *conversation* source gets a link, because opening a conversation is
  // the only thing this link does. A file source is already open — the pane is
  // the document — so offering "Open document" there would send the owner back
  // to the chat they are standing in (found while verifying C6/C4).
  const sourceHref = $derived(
    source === null || source.session_id === "" || source.kind !== "conversation"
      ? null
      : `#/new-chat?session=${encodeURIComponent(source.session_id)}`,
  );

  const sizeLabel = $derived.by(() => {
    const bytes = preview?.byte_size ?? 0;
    if (bytes <= 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  });
</script>

<aside class="file-inspector" aria-label="File preview">
  <header>
    <div class="titles">
      <h2>{preview?.filename || source?.title || filename}</h2>
      {#if preview !== null}
        <p>{preview.media_type}{sizeLabel ? ` · ${sizeLabel}` : ""}</p>
      {:else if source !== null && source.kind !== ""}
        <p>{source.kind === "conversation" ? "Conversation source" : "File source"}</p>
      {/if}
    </div>
    <div class="header-actions">
      {#if ondownload !== null}
        <!-- BUG-28 — distinct from Preview and from conversation export: this
             is the file itself, as bytes, saved where the owner wants it. -->
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          onclick={() => void ondownload?.()}
          disabled={downloadState === "working"}
          aria-label={`Download ${preview?.filename || filename}`}
        >
          <Icon name="download" size="sm" />
          {downloadState === "working" ? "Downloading…" : downloadState === "done" ? "Downloaded" : "Download"}
        </button>
      {/if}
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        onclick={onclose}
        bind:this={closeButton}
        aria-label="Close file preview"
      >
        <Icon name="x" size="sm" />
      </button>
    </div>
  </header>

  {#if downloadError !== null}
    <p class="error-line" role="alert">{downloadError}</p>
  {/if}

  <div class="body">
    {#if loading}
      <p class="muted" role="status">Opening {filename}…</p>
    {:else if error !== null}
      <p class="error-line" role="alert">{error}</p>
    {:else if preview === null && source === null}
      <p class="muted">Nothing to show.</p>
    {:else if preview !== null}
      {#if preview.kind === "unavailable"}
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
        {#if objectUrl !== null}
          <object class="pdf-frame" data={objectUrl} type="application/pdf" aria-label={`${preview.filename} (PDF)`}>
            <p class="muted">This browser cannot display the PDF inline.</p>
          </object>
        {:else}
          <p class="muted" role="status">Loading the PDF…</p>
        {/if}
      {:else if preview.kind === "image"}
        {#if objectUrl !== null}
          <!-- The alt text is the filename: this is the picture the owner
               attached, so naming it is the honest description available. -->
          <ImageViewport src={objectUrl} alt={preview.filename} />
        {:else}
          <p class="muted" role="status">Loading the image…</p>
        {/if}
      {/if}

      {#if preview.truncated}
        <p class="muted truncation">Showing the beginning of this file only.</p>
      {/if}
    {/if}

    {#if sourceLoading}
      <p class="muted" role="status">Opening the source…</p>
    {:else if source !== null}
      <section class="source" aria-label="Source passage">
        <div class="source-head">
          <span class="source-eyebrow"><Icon name="quote" size="sm" /> Source</span>
          {#if source.title}<strong>{source.title}</strong>{/if}
        </div>
        {#if source.status === "resolved" && source.resolution_method}
          <span class="resolution-badge" class:verified={source.resolution_method === "stored_coordinates"}>
            {RESOLUTION_TEXT[source.resolution_method] ?? "Located by matching text"}
          </span>
        {/if}
        {#if sourceNote}<p class="muted source-note">{sourceNote}</p>{/if}
        {#if sourceParts !== null && source.excerpt !== ""}
          <blockquote class="source-excerpt">
            {sourceParts.before}<mark>{sourceParts.passage}</mark>{sourceParts.after}
          </blockquote>
          {#if source.truncated}
            <p class="muted truncation">Showing the passage and the text around it only.</p>
          {/if}
        {/if}
        <!-- BUG-245 — a search that returned ten exchanges now names all ten
             as links. The single "Open conversation" below lands at the top of
             a conversation and is kept only for a source that has no exchange
             coordinates of its own to offer. -->
        <SourceAnchorLinks anchors={source.anchors ?? []} />
        {#if sourceHref !== null && (source.anchors ?? []).length === 0}
          <a class="btn btn-ghost btn-sm" href={sourceHref}>Open conversation</a>
        {/if}
      </section>
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
  .header-actions { display: flex; align-items: center; gap: var(--space-1, 0.35rem); flex-shrink: 0; }
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
  /* BUG-27 — the passage, in its own surrounding text. The mark is a slice of
     the excerpt, so nothing the source wrote can style or escape it. */
  .source {
    display: grid;
    gap: var(--space-2);
    justify-items: start;
    margin-top: var(--space-4);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  /* `justify-items: start` sizes each row to its content, so a child that
     cannot wrap widens the whole pane. Every row is capped instead. */
  .source > :global(*) { max-width: 100%; min-width: 0; }
  .source-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    min-width: 0;
  }
  .source-head strong { overflow-wrap: anywhere; }
  .source-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--accent);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .resolution-badge { color:var(--text-3); font-size:.7rem; font-weight:650; }
  .resolution-badge.verified { color:var(--ok); }
  .source-note { margin: 0; font-size: 0.78rem; }
  .source-excerpt {
    margin: 0;
    padding: 0.55rem 0.75rem;
    width: 100%;
    border-left: 3px solid var(--border-strong);
    background: var(--sunken);
    border-radius: 0 var(--r-sm) var(--r-sm) 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.5;
  }
  .source-excerpt mark {
    background: var(--warn-soft, color-mix(in srgb, var(--accent) 22%, transparent));
    color: inherit;
    border-radius: 2px;
    padding: 0.05em 0.1em;
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
