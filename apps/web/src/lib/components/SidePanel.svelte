<script lang="ts">
  /**
   * Inspector-style side panel — the shared detail surface for models, gates,
   * connectors, MCP servers, and files.
   *
   * Borrowed from the design-tool pattern of a persistent right-hand inspector:
   * the list stays on screen, and selecting a row fills the panel instead of
   * covering the page with a modal. It becomes a full-height sheet below the
   * tablet breakpoint, where a side-by-side split stops being readable.
   *
   * The panel is a complementary landmark, not a modal: focus moves into it on
   * open and returns to whatever opened it on close, and Escape closes it, but
   * Tab is deliberately not trapped — the list behind it stays reachable.
   */
  import type { Snippet } from "svelte";
  import Icon from "./Icon.svelte";

  let {
    open,
    title,
    subtitle = null,
    onclose,
    // Set where the panel stacks below its list rather than sitting beside it:
    // without this the panel can open off-screen and read as "nothing
    // happened". Honours the user's reduced-motion preference.
    scrollIntoViewOnOpen = false,
    children,
    footer,
  }: {
    open: boolean;
    title: string;
    subtitle?: string | null;
    onclose: () => void;
    scrollIntoViewOnOpen?: boolean;
    children: Snippet;
    footer?: Snippet;
  } = $props();

  let panel = $state<HTMLElement>();
  let closeButton = $state<HTMLButtonElement>();
  let returnFocusTo: HTMLElement | null = null;

  $effect(() => {
    if (!open) return;
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    queueMicrotask(() => {
      closeButton?.focus();
      if (scrollIntoViewOnOpen) panel?.scrollIntoView({ block: "nearest" });
    });
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
</script>

{#if open}
  <aside class="side-panel" aria-label={title} bind:this={panel}>
    <header>
      <div class="titles">
        <h2>{title}</h2>
        {#if subtitle}<p>{subtitle}</p>{/if}
      </div>
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        onclick={onclose}
        bind:this={closeButton}
        aria-label="Close details"
      >
        <Icon name="x" size={15} />
      </button>
    </header>
    <div class="body">{@render children()}</div>
    {#if footer}<footer>{@render footer()}</footer>{/if}
  </aside>
{/if}

<style>
  .side-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    align-self: start;
    position: sticky;
    top: 0;
    max-height: calc(100vh - var(--topbar-h) - var(--space-6));
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-1);
    padding: var(--space-4);
    overflow: auto;
  }
  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .titles h2 {
    margin: 0;
    font-size: 1rem;
    overflow-wrap: anywhere;
  }
  .titles p {
    margin: 0.15rem 0 0;
    color: var(--text-3);
    font-size: 0.78rem;
  }
  .body {
    display: grid;
    gap: var(--space-3);
    font-size: 0.86rem;
  }
  footer {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    border-top: 1px solid var(--border);
    padding-top: var(--space-3);
  }
  /* Below the split-view breakpoint the inspector becomes a sheet: a narrow
     column beside a list is unreadable, and the list is one tap away. */
  @media (max-width: 63.9rem) {
    .side-panel {
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
