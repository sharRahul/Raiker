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

  let { store, disabled = false }: { store: AttachmentStore; disabled?: boolean } = $props();
</script>

{#if store.items.length > 0}
  <div class="attachment-row" aria-label="Attached to this prompt">
    {#each store.items as item, i (item.attachmentId ?? item.path ?? i)}
      <AttachmentCard attachment={item} {disabled} onremove={() => store.remove(i)} />
    {/each}
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
  .attach-error { margin: 0; color: var(--danger); font-size: var(--text-sm); }
</style>
