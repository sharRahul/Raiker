<script lang="ts">
  /**
   * What the next prompt is carrying, above the text you are typing.
   *
   * Shared by Chat and Build so a file reads the same way in both. The chip
   * shows the name; the full path or the stored media type and size stay in the
   * tooltip, because a composer that wraps to three lines of absolute paths is
   * unusable and the detail is one hover away.
   */
  import Icon from "./Icon.svelte";
  import type { AttachmentStore } from "../composerAttachments.svelte";

  let { store, disabled = false }: { store: AttachmentStore; disabled?: boolean } = $props();

  const ICONS = { path: "folder", image: "eye", document: "file" } as const;
</script>

{#if store.items.length > 0}
  <div class="attach-chips">
    {#each store.items as item, i (item.attachmentId ?? item.path ?? i)}
      <span class="attach-chip" title={item.detail}>
        <Icon name={ICONS[item.kind]} size={13} />
        {item.label}
        <button
          type="button"
          class="attach-remove"
          onclick={() => store.remove(i)}
          aria-label={`Remove attachment ${item.detail}`}
          {disabled}
        >
          <Icon name="x" size={12} />
        </button>
      </span>
    {/each}
  </div>
{/if}
{#if store.error !== null}
  <p class="attach-error" role="alert">{store.error}</p>
{/if}

<style>
  .attach-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .attach-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    max-width: 18rem;
    padding: 0.2rem 0.3rem 0.2rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--sunken);
    color: var(--text-2);
    font-size: 0.75rem;
    overflow-wrap: anywhere;
  }
  .attach-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    padding: 0;
  }
  .attach-remove:hover:not(:disabled) { background: var(--neutral-soft); color: var(--text-1); }
  .attach-error { margin: 0; color: var(--danger); font-size: 0.78rem; }
</style>
