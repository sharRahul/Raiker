<script lang="ts">
  /**
   * What the next prompt is carrying, above the text you are typing.
   *
   * Shared by Chat, Build and the Workbench so a file reads the same way
   * everywhere. Each attachment renders as a real card — a picture shows the
   * picture, a document shows its type and size — rather than as a row of
   * identical grey pills that only differ by filename.
   */
  import AttachmentCard from "./AttachmentCard.svelte";
  import type { AttachmentStore } from "../composerAttachments.svelte";

  let { store, disabled = false, oninline }: { store: AttachmentStore; disabled?: boolean; oninline?: (text: string) => void } = $props();
</script>

{#if store.items.length > 0 || store.uploadingName !== null}
  <div class="attachment-row" aria-label="Attached to this prompt">
    {#each store.items as item, i (item.attachmentId ?? item.path ?? i)}
      <div class="attachment-with-action">
        <AttachmentCard attachment={item} {disabled} onremove={() => store.remove(i)} />
        {#if item.pastedText !== undefined && oninline}
          <button class="inline-paste" type="button" {disabled} aria-label={`Show ${item.label} inline`} onclick={() => {
            oninline?.(item.pastedText!);
            store.remove(i);
          }}>Show inline</button>
        {/if}
      </div>
    {/each}
    {#if store.uploadingName !== null}
      <!-- True stages only: the upload is in flight. Its text is read when the
           turn runs, so no "parsing" or "indexing" step is claimed here. -->
      <div class="uploading-chip" role="status">
        <span class="spinner" aria-hidden="true"></span>
        <span class="uploading-name">{store.uploadingName}</span>
        <span class="uploading-state">Uploading…</span>
      </div>
    {/if}
  </div>
{/if}
{#if store.error !== null}
  <p class="attach-error" role="alert">{store.error}</p>
{/if}

<style>
  .attachment-row {
    display: flex;
    flex-wrap: wrap;
    /* Room above for the remove control, which overhangs each card's corner. */
    gap: 0.75rem 0.5rem;
    padding-top: 0.35rem;
  }
  .attachment-with-action {
    display: grid;
    justify-items: start;
    gap: 0.25rem;
  }
  .inline-paste {
    appearance: none;
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--accent);
    font: inherit;
    font-size: var(--text-xs);
    cursor: pointer;
  }
  .inline-paste:hover:not(:disabled) { text-decoration: underline; }
  .inline-paste:disabled { cursor: default; opacity: 0.55; }
  .uploading-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    max-width: 15rem;
    padding: 0.45rem 0.6rem;
    border: 1px dashed var(--accent-border);
    border-radius: var(--r-md);
    background: var(--surface);
    font-size: var(--text-sm);
  }
  .uploading-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
  .uploading-state { color: var(--text-3); font-size: var(--text-2xs); white-space: nowrap; }
  .spinner {
    width: 0.8rem;
    height: 0.8rem;
    flex-shrink: 0;
    border: 2px solid var(--accent-border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.9s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }
  .attach-error { margin: 0; color: var(--danger); font-size: var(--text-sm); }
</style>
