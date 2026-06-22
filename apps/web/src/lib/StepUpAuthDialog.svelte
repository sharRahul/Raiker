<script lang="ts">
  // Step-up window shown before a runtime mutation. It re-confirms the acting human principal
  // (resolved from the session — the UI cannot change who you are) and COLLECTS the backend-required
  // inputs (reason, Tier-2 confirmation token, threat-model acknowledgement). It grants nothing the
  // backend wouldn't already require; it only collects and forwards to the existing control routes.
  export interface StepUpValues {
    reason: string;
    confirmationToken: string | null;
    threatAck: boolean;
  }

  let {
    title,
    principal,
    requireToken = false,
    requireThreatAck = false,
    busy = false,
    error = null,
    onConfirm,
    onCancel,
  }: {
    title: string;
    principal: string;
    requireToken?: boolean;
    requireThreatAck?: boolean;
    busy?: boolean;
    error?: string | null;
    onConfirm: (values: StepUpValues) => void;
    onCancel: () => void;
  } = $props();

  let reason = $state("");
  let token = $state("");
  let threatAck = $state(false);
  let dialogEl: HTMLDivElement | undefined = $state();

  const blocked = $derived(
    reason.trim() === "" ||
      (requireToken && token.trim() === "") ||
      (requireThreatAck && !threatAck) ||
      busy,
  );

  function confirm() {
    if (blocked) return;
    onConfirm({
      reason: reason.trim(),
      confirmationToken: requireToken ? token.trim() : null,
      threatAck,
    });
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") onCancel();
  }

  $effect(() => {
    dialogEl?.focus();
  });
</script>

<div class="overlay">
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="stepup-title"
    tabindex="-1"
    bind:this={dialogEl}
    onkeydown={onKeydown}
  >
    <h2 id="stepup-title">{title}</h2>
    <p class="principal">
      Acting as <strong>{principal}</strong>. This decision is recorded against your principal.
    </p>

    <label for="stepup-reason">Reason (required)</label>
    <textarea
      id="stepup-reason"
      bind:value={reason}
      rows="2"
      placeholder="Why are you making this change?"
      disabled={busy}
    ></textarea>

    {#if requireToken}
      <label for="stepup-token">Confirmation token (required for this Tier-2 change)</label>
      <input id="stepup-token" type="text" bind:value={token} disabled={busy} autocomplete="off" />
      <p class="hint">
        Tier-2 capabilities (shell, network, web-fetch, process) require a human confirmation token.
      </p>
    {/if}

    {#if requireThreatAck}
      <label class="ack">
        <input type="checkbox" bind:checked={threatAck} disabled={busy} />
        I have reviewed the threat model for this capability and accept the risk.
      </label>
    {/if}

    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <div class="actions">
      <button type="button" onclick={onCancel} disabled={busy}>Cancel</button>
      <button type="button" class="confirm" onclick={confirm} disabled={blocked}>
        {busy ? "Applying…" : "Confirm change"}
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: grid;
    place-items: center;
    z-index: 60;
  }
  .modal {
    background: #15151a;
    border: 1px solid #3a3a40;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    max-width: 30rem;
    width: calc(100% - 2rem);
    color: #d4d4da;
  }
  .modal:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 2px;
  }
  .modal h2 {
    margin-top: 0;
  }
  .principal {
    font-size: 0.85rem;
    color: #c2c2c9;
  }
  label {
    display: block;
    font-size: 0.78rem;
    color: #b0b0b6;
    margin: 0.6rem 0 0.2rem;
  }
  label.ack {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    font-size: 0.84rem;
    color: #d4d4da;
    margin-top: 0.8rem;
  }
  textarea,
  input[type="text"] {
    width: 100%;
    box-sizing: border-box;
    background: #0e0e11;
    border: 1px solid #33333a;
    color: #d6d6dc;
    border-radius: 6px;
    padding: 0.45rem 0.6rem;
    font: inherit;
    resize: vertical;
  }
  textarea:focus-visible,
  input:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .hint {
    font-size: 0.76rem;
    color: #8b8b93;
    margin: 0.25rem 0 0;
  }
  .error {
    color: #ef9a9a;
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
    font-weight: 600;
  }
  .actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .actions .confirm {
    border-color: #8a6d1f;
    color: #e6c66a;
  }
</style>
