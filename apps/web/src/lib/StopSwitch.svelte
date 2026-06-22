<script lang="ts">
  // STOP switch (top bar). In M1 this is a no-op placeholder: it opens a confirm dialog
  // explaining the intended behavior, but the Confirm action is disabled. It is wired to the
  // governed interrupt path (cancel at next safe boundary) in Milestone 3.
  let open = $state(false);
  let dialogEl: HTMLDivElement | undefined = $state();

  function show() {
    open = true;
  }
  function close() {
    open = false;
  }
  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") close();
  }

  $effect(() => {
    if (open) dialogEl?.focus();
  });
</script>

<button class="stop-switch" aria-label="Stop all tasks" onclick={show}>
  <span class="stop-glyph" aria-hidden="true">■</span>
  <span class="stop-text">STOP</span>
</button>

{#if open}
  <div class="overlay">
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="stop-title"
      tabindex="-1"
      bind:this={dialogEl}
      onkeydown={onKeydown}
    >
      <h2 id="stop-title">Stop all tasks?</h2>
      <p>
        This requests cancellation of all active tasks <strong>at the next safe boundary</strong>. It
        is not an instant force-kill; in-flight safe operations finish first.
      </p>
      <p class="note">Not yet wired — this control is connected to the runtime in Milestone&nbsp;3.</p>
      <div class="actions">
        <button type="button" onclick={close}>Close</button>
        <button type="button" class="danger" disabled aria-disabled="true" title="Wired in M3">
          Confirm (disabled in M1)
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .stop-switch {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 3.25rem;
    height: 3.25rem;
    border-radius: 50%;
    border: 2px solid #b3261e;
    background: #2a0f0f;
    color: #ff8a80;
    cursor: pointer;
    font-weight: 700;
  }
  .stop-switch:hover {
    background: #3a1414;
  }
  .stop-switch:focus-visible {
    outline: 3px solid #ff8a80;
    outline-offset: 2px;
  }
  .stop-glyph {
    font-size: 1rem;
    line-height: 1;
  }
  .stop-text {
    font-size: 0.6rem;
    letter-spacing: 0.08em;
  }
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: grid;
    place-items: center;
    z-index: 50;
  }
  .modal {
    background: #15151a;
    border: 1px solid #3a3a40;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    max-width: 28rem;
    color: #d4d4da;
  }
  .modal:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 2px;
  }
  .modal h2 {
    margin-top: 0;
  }
  .note {
    color: #e6c66a;
    font-size: 0.85rem;
  }
  .actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
    margin-top: 1rem;
  }
  .actions button {
    padding: 0.4rem 0.9rem;
    border-radius: 6px;
    border: 1px solid #4a4a52;
    background: #1f1f25;
    color: #d4d4da;
    cursor: pointer;
  }
  .actions button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .actions .danger[disabled] {
    border-color: #5a2a2a;
    color: #8a6a6a;
    cursor: not-allowed;
  }
</style>
