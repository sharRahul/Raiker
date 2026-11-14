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
    max-height: min(calc(100dvh - var(--space-6)), 48rem);
    overflow: hidden;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--dialog-bg);
    box-shadow: var(--shadow-2);
  }
  .form-dialog[open] { display: flex; flex-direction: column; }
  header {
    flex: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--border);
  }
  header h2 {
    margin: 0;
    font-size: var(--text-lg);
    min-width: 0;
    overflow-wrap: anywhere;
  }
  header button { flex: none; }
  .form-body {
    display: grid;
    gap: var(--space-3);
    padding: var(--space-5);
    min-height: 0;
    overflow: auto;
    overscroll-behavior: contain;
  }
  .form-body > :global(*) { min-width: 0; }
  /* FIXED-1408 — a button is as wide as its words; as a grid child it
     stretched across the dialog (Enroll in MFA, Check breach corpus) while
     every other dialog's actions are compact. */
  .form-body > :global(button) { justify-self: start; }
</style>
