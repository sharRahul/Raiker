<script lang="ts">
  /**
   * The composer's attach trigger — the control that reveals the ways in.
   *
   * Deliberately just the button: the panel it opens is a sibling
   * (`ComposerAttachPanel`) that the composer places *in flow*, between the
   * prompt and the control bar. A floating popover anchored to this button would
   * open upward over the text being typed, which is exactly the wrong thing to
   * cover; growing the card instead keeps the prompt readable while files are
   * being chosen.
   *
   * Shared by Chat, Build and the Workbench so all three offer the same
   * affordance in the same place. Every rule about what may be attached lives in
   * `composerAttachments.svelte.ts` and, for real, on the server.
   */
  import Icon from "./Icon.svelte";

  let {
    open = $bindable(false),
    disabled = false,
  }: { open?: boolean; disabled?: boolean } = $props();

  let root = $state<HTMLDivElement>();

  /** Clicking outside the trigger or its panel dismisses the panel. */
  export function handleOutsideClick(event: MouseEvent) {
    if (!open) return;
    const target = event.target as HTMLElement | null;
    if (root?.contains(target ?? null)) return;
    if (target?.closest?.("[data-attach-panel]")) return;
    open = false;
  }
</script>

<div class="composer-attach" bind:this={root}>
  <button
    type="button"
    class="round-btn"
    onclick={() => (open = !open)}
    aria-label="Add attachment"
    aria-expanded={open}
    title="Attach a workspace file, an image, or a document"
    {disabled}
  >
    <Icon name="file" size="sm" />
  </button>
</div>

<style>
  .composer-attach { display: inline-flex; }
  .round-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--surface);
    color: var(--text-2);
    cursor: pointer;
    padding: 0;
  }
  .round-btn:hover:not(:disabled) { border-color: var(--accent-border); color: var(--accent); }
  .round-btn[aria-expanded="true"] { border-color: var(--accent-border); color: var(--accent); background: var(--accent-soft); }
  .round-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .round-btn:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
</style>
