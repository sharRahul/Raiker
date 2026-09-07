<script lang="ts">
  /**
   * One attached file, shown the way an attached file should be shown.
   *
   * It used to be a small grey pill with a generic paper icon and a filename —
   * the same shape whether you had attached a photograph, a spreadsheet or a
   * folder path. That tells you nothing you did not already know from typing
   * the name, and it makes a composer carrying three files look like a row of
   * tags rather than like work you are about to hand over.
   *
   * So: a picture shows the picture. Everything else shows what it actually is
   * — a coloured type badge, its name, and its size — because those are the two
   * facts you check before sending something ("did I pick the right file", "is
   * it the big one or the small one").
   *
   * The same card does both jobs. In a composer it carries a remove control; in
   * a transcript it is a button that opens the inspector. Neither variant
   * fetches anything: an image the owner just picked shows the local file back,
   * and a stored one shows a blob the caller already resolved.
   */
  import Icon from "./Icon.svelte";
  import {
    formatBytes,
    typeLabel,
    type ComposerAttachment,
  } from "../composerAttachments.svelte";

  let {
    attachment,
    /** A blob URL for a stored image, when the caller has resolved one. */
    thumbnail = null,
    onremove = null,
    onopen = null,
    expanded = false,
    disabled = false,
  }: {
    attachment: ComposerAttachment;
    thumbnail?: string | null;
    onremove?: (() => void) | null;
    onopen?: (() => void) | null;
    expanded?: boolean;
    disabled?: boolean;
  } = $props();

  const image = $derived(thumbnail ?? attachment.previewUrl ?? null);
  const isImage = $derived(attachment.kind === "image");
  const size = $derived(formatBytes(attachment.byteSize));
  const badge = $derived(typeLabel(attachment));
  // A workspace path is not a file the owner uploaded; naming its type "PATH"
  // and showing its folder is the honest description of what it is.
  const subtitle = $derived(
    attachment.kind === "path"
      ? (attachment.path ?? attachment.detail)
      : [badge, size].filter(Boolean).join(" · "),
  );
</script>

{#snippet body()}
  {#if isImage && image !== null}
    <span class="thumb"><img src={image} alt="" /></span>
  {:else}
    <span class="glyph" data-kind={attachment.kind} aria-hidden="true">
      {#if attachment.kind === "path"}
        <Icon name="folder" size="md" />
      {:else if isImage}
        <Icon name="eye" size="md" />
      {:else}
        <Icon name="file" size="md" />
      {/if}
    </span>
  {/if}
  <span class="text">
    <span class="name">{attachment.label}</span>
    <span class="meta">{subtitle}</span>
  </span>
{/snippet}

<div class="attachment-card" class:with-image={isImage && image !== null} class:openable={onopen !== null}>
  {#if onopen !== null}
    <button
      type="button"
      class="surface"
      onclick={onopen}
      aria-label={`Open ${attachment.label}`}
      aria-expanded={expanded}
      title={attachment.detail}
    >
      {@render body()}
    </button>
  {:else}
    <span class="surface" title={attachment.detail}>{@render body()}</span>
  {/if}

  {#if onremove !== null}
    <button
      type="button"
      class="remove"
      onclick={onremove}
      aria-label={`Remove attachment ${attachment.label}`}
      {disabled}
    >
      <Icon name="x" size="sm" />
    </button>
  {/if}
</div>

<style>
  .attachment-card {
    position: relative;
    display: inline-flex;
    max-width: 15rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .attachment-card.openable:hover { border-color: var(--accent-border); }
  .surface {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
    width: 100%;
    padding: 0.35rem 0.6rem 0.35rem 0.35rem;
    border: 0;
    border-radius: var(--r-md);
    background: transparent;
    color: var(--text-1);
    font: inherit;
    text-align: left;
  }
  button.surface { cursor: pointer; }
  button.surface:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }

  /* A picture shows the picture. Square-cropped so a portrait photo and a wide
     screenshot sit on the same line without one of them setting the height. */
  .thumb {
    display: block;
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: var(--r-sm);
    overflow: hidden;
    background:
      repeating-conic-gradient(var(--neutral-soft) 0% 25%, transparent 0% 50%) 50% / 10px 10px;
  }
  .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }

  .glyph {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: var(--r-sm);
    background: var(--neutral-soft);
    color: var(--text-2);
  }
  .glyph[data-kind="document"] { background: var(--accent-soft); color: var(--accent); }

  .text { display: grid; gap: 0.05rem; min-width: 0; }
  .name {
    font-size: var(--text-sm);
    font-weight: 600;
    line-height: 1.25;
    /* One line, ellipsised: a composer that rewraps as files are added moves
       the thing you are typing into. */
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta {
    color: var(--text-3);
    font-size: var(--text-2xs);
    letter-spacing: 0.02em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .remove {
    position: absolute;
    top: -6px;
    right: -6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--surface);
    color: var(--text-2);
    cursor: pointer;
    padding: 0;
    box-shadow: var(--shadow-1);
  }
  .remove:hover:not(:disabled) { border-color: var(--danger); color: var(--danger); }
  .remove:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
  .remove:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
