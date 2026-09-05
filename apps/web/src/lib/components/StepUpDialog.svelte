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

    <label class="field-label" for="stepup-reason">Reason (required)</label>
    <textarea
      id="stepup-reason"
      class="textarea"
      bind:value={reason}
      rows="2"
      placeholder="Why are you making this change?"
      disabled={busy}
    ></textarea>

    {#if requireToken}
      <label class="field-label token-label" for="stepup-token">
        Confirmation token (required to enable this capability)
      </label>
      <input
        id="stepup-token"
        class="input token-input"
        type="text"
        bind:value={token}
        disabled={busy}
        autocomplete="off"
      />
      <p class="hint">
        Type any phrase to confirm you intend this change. It is recorded with your decision.
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
      <button type="button" class="btn" onclick={onCancel} disabled={busy}>Cancel</button>
      <button type="button" class="btn btn-primary" onclick={confirm} disabled={blocked}>
        {busy ? "Applying…" : "Confirm change"}
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: var(--overlay);
    display: grid;
    place-items: center;
    z-index: 60;
  }
  .modal {
    background: var(--raised);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    box-shadow: var(--shadow-2);
    padding: var(--space-5);
    max-width: 30rem;
    width: calc(100% - 2rem);
  }
  .principal {
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .token-label {
    margin-top: 0.7rem;
  }
  .token-input {
    width: 100%;
  }
  label.ack {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    font-size: var(--text-sm);
    color: var(--text-1);
    margin-top: 0.8rem;
  }
  .hint {
    font-size: var(--text-xs);
    color: var(--text-3);
    margin: 0.25rem 0 0;
  }
  .error {
    color: var(--danger);
    font-size: var(--text-sm);
    margin-top: 0.6rem;
  }
  .actions {
    display: flex;
    gap: 0.6rem;
    justify-content: flex-end;
    margin-top: var(--space-4);
  }
</style>
