<script lang="ts">
  /**
   * The three ways a file gets into a prompt: a workspace path, an image, a
   * document.
   *
   * Rendered in flow inside the composer card rather than as a floating popover,
   * so opening it grows the card instead of covering the text being written.
   *
   * Nothing here decides anything. A path is resolved inside the workspace by
   * the prompt route and anything outside fails closed; an image and a document
   * are validated fail-closed on upload (allowlist, size cap, magic-byte sniff)
   * and re-validated on every read. The limits stated in the tooltips are the
   * server's, repeated here so a refusal is predictable rather than surprising.
   */
  import PathPicker from "./PathPicker.svelte";
  import {
    DOCUMENT_EXTENSIONS,
    DOCUMENT_MEDIA_TYPES,
    IMAGE_MEDIA_TYPES,
    type AttachmentStore,
  } from "../composerAttachments.svelte";

  let {
    store,
    disabled = false,
    /** Distinguishes the composers' file inputs when more than one is mounted. */
    idPrefix = "composer",
  }: { store: AttachmentStore; disabled?: boolean; idPrefix?: string } = $props();

  let pathDraft = $state("");
  // BUG-251 — the workspace path can be browsed to. It is resolved inside the
  // workspace either way; the picker only removes the need to know how to spell it.
  let browsing = $state(false);

  // The visible control is a <label>, and a label whose input is disabled does
  // nothing at all when clicked — while still looking exactly like a button
  // that would. Whatever disables the input has to disable the label's
  // appearance with it, or the panel reads as broken.
  const uploadsDisabled = $derived(disabled || store.uploading || store.full);

  function submitPath() {
    if (store.addPath(pathDraft)) pathDraft = "";
  }

  async function pickImage(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (file) await store.uploadImage(file);
  }

  async function pickDocument(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (file) await store.uploadDocument(file);
  }
</script>

<div class="attach-panel" data-attach-panel>
  <input
    class="attach-input"
    type="text"
    placeholder="Workspace file or folder path…"
    bind:value={pathDraft}
    onkeydown={(e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitPath();
      }
    }}
    disabled={disabled || store.full}
    aria-label="Attachment path"
  />
  <button
    type="button"
    class="btn btn-sm"
    onclick={() => (browsing = true)}
    disabled={disabled || store.full}
  >
    Browse…
  </button>
  <button
    type="button"
    class="btn btn-sm"
    onclick={submitPath}
    disabled={disabled || pathDraft.trim() === "" || store.full}
  >
    Attach
  </button>
  <input
    class="sr-only"
    id={`${idPrefix}-image-upload`}
    type="file"
    accept={IMAGE_MEDIA_TYPES.join(",")}
    onchange={pickImage}
    disabled={disabled || store.uploading || store.full}
    aria-label="Upload image"
  />
  <label
    class="btn btn-sm"
    class:is-disabled={uploadsDisabled}
    aria-disabled={uploadsDisabled}
    for={`${idPrefix}-image-upload`}
    title="Upload an image (PNG/JPEG/WebP/GIF, 5 MB max). Sent to the model only if the selected model supports vision."
  >
    {store.uploading ? "Uploading…" : "Image…"}
  </label>
  <input
    class="sr-only"
    id={`${idPrefix}-document-upload`}
    type="file"
    accept={[...DOCUMENT_MEDIA_TYPES, ...DOCUMENT_EXTENSIONS].join(",")}
    onchange={pickDocument}
    disabled={disabled || store.uploading || store.full}
    aria-label="Upload document"
  />
  <label
    class="btn btn-sm"
    class:is-disabled={uploadsDisabled}
    aria-disabled={uploadsDisabled}
    for={`${idPrefix}-document-upload`}
    title="Upload a document (plain text/Markdown/CSV/PDF/Word .docx/Excel .xlsx, 32 MB max). Its extracted text is added to context as untrusted data."
  >
    {store.uploading ? "Uploading…" : "Document…"}
  </label>
  {#if store.full}
    <span class="attach-limit">Attachment limit reached for this prompt.</span>
  {/if}
</div>

{#if browsing}
  <PathPicker
    title="Choose a workspace file or folder"
    mode="file"
    insideWorkspace
    onchoose={(path) => { browsing = false; if (store.addPath(path)) pathDraft = ""; }}
    onclose={() => (browsing = false)}
  />
{/if}

<style>
  .is-disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .attach-panel {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
  }
  .attach-input {
    flex: 1;
    min-width: 12rem;
    min-height: 32px;
    padding: 0 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: 0.82rem;
  }
  .attach-limit { color: var(--text-3); font-size: 0.74rem; }
</style>
