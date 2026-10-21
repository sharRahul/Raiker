<script lang="ts">
  /**
   * QUI-L03 — a form opens in a dialog, not inline. A settings page is a list
   * of rows (label, current value, one action); the action that needs fields —
   * change a password, set the vault key, create a grant — opens one of these.
   *
   * Rendered only while open (`{#if open}<FormDialog … />{/if}`): it opens as a
   * modal on mount, closes on Escape or the backdrop, and gives focus back to
   * the control that opened it.
   */
  import { onMount, type Snippet } from "svelte";
  import Icon from "./Icon.svelte";

  let {
    title,
    onclose,
    children,
  }: {
    title: string;
    onclose: () => void;
    children: Snippet;
  } = $props();

  let dialogElement = $state<HTMLDialogElement>();

  onMount(() => {
    const returnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
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
</script>

<dialog class="form-dialog" bind:this={dialogElement} aria-label={title} oncancel={cancel} onclick={backdrop}>
  <header>
    <h2>{title}</h2>
    <button type="button" class="btn btn-ghost btn-sm" aria-label="Close" onclick={onclose}>
      <Icon name="x" size="sm" />
    </button>
  </header>
  <div class="form-body">
    {@render children()}
  </div>
</dialog>

<style>
  .form-dialog::backdrop {
    background: var(--overlay);
  }
  .form-dialog {
    color: var(--text-1);
    width: min(560px, calc(100vw - 2rem));
    max-height: min(85vh, 48rem);
    overflow-y: auto;
    padding: var(--space-5);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }
  header h2 {
    margin: 0;
    font-size: var(--text-lg);
  }
  .form-body {
    display: grid;
    gap: var(--space-3);
  }
</style>
