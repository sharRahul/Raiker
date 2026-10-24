<script lang="ts">
  /**
   * QUI-F10 — the one confirmation dialog. Mounted once by the shell; asked
   * through `askConfirm` (`confirm.svelte.ts`). Enter confirms, Esc and the
   * backdrop cancel, and focus starts on the action so Enter means it.
   */
  import { onMount } from "svelte";
  import { answerConfirm, confirmState, hostConfirm } from "../confirm.svelte";

  onMount(() => hostConfirm());

  let dialogElement = $state<HTMLDialogElement>();
  let confirmButton = $state<HTMLButtonElement>();
  let returnFocus: HTMLElement | null = null;
  const request = $derived(confirmState.current);

  $effect(() => {
    if (request === null || !dialogElement) return;
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (!dialogElement.open) {
      if (typeof dialogElement.showModal === "function") dialogElement.showModal();
      else dialogElement.setAttribute("open", "");
    }
    queueMicrotask(() => confirmButton?.focus());
  });

  function finish(answer: boolean): void {
    if (dialogElement?.open) {
      if (typeof dialogElement.close === "function") dialogElement.close();
      else dialogElement.removeAttribute("open");
    }
    answerConfirm(answer);
    returnFocus?.focus();
    returnFocus = null;
  }

  function onkeydown(event: KeyboardEvent): void {
    if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      finish(true);
    }
  }
</script>

{#if request !== null}
  <dialog
    class="confirm-dialog"
    bind:this={dialogElement}
    aria-labelledby="confirm-title"
    aria-describedby={request.body ? "confirm-body" : undefined}
    oncancel={(event) => {
      event.preventDefault();
      finish(false);
    }}
    onclick={(event) => {
      if (event.target === event.currentTarget) finish(false);
    }}
    {onkeydown}
  >
    <h2 id="confirm-title">{request.title}</h2>
    {#if request.body}<p id="confirm-body">{request.body}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-ghost" onclick={() => finish(false)}>Cancel</button>
      <button
        type="button"
        class="btn"
        class:btn-danger={request.danger}
        class:btn-primary={!request.danger}
        bind:this={confirmButton}
        onclick={() => finish(true)}
      >{request.confirmLabel}</button>
    </div>
  </dialog>
{/if}

<style>
  .confirm-dialog::backdrop{background:var(--overlay)}
  .confirm-dialog{color:var(--text-1);width:min(440px,calc(100vw - 2rem));padding:var(--space-5);border:1px solid var(--border);border-radius:var(--r-lg);background:var(--surface);box-shadow:var(--shadow-2)}
  h2{margin:0;font-size:var(--text-md)}
  p{margin:var(--space-2) 0 0;color:var(--text-2);font-size:var(--text-sm)}
  .actions{display:flex;justify-content:flex-end;gap:var(--space-2);margin-top:var(--space-5)}
</style>
