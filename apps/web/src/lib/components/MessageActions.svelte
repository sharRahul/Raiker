<script lang="ts">
  /**
   * Per-message actions on the owner's own prompt (C14 / B19).
   *
   * Editing a prompt and re-running it is the most-used control in an assistant
   * of this kind, and neither composer had it: correcting a typo meant retyping
   * the whole prompt, and asking for a second attempt meant the same. Three
   * actions, and no more, because each one has to mean something exact:
   *
   * * **Copy** — the prompt text, to the clipboard. Says when the browser
   *   refuses; a copy button that silently does nothing is worse than none.
   * * **Edit** — puts the prompt back in the composer to change and send again.
   *   It does **not** rewrite history: the original turn stays in the
   *   transcript, and the edited one is a new turn. A transcript that quietly
   *   changes what was asked is not a record.
   * * **Retry** — sends the same prompt again, unchanged, as a new turn.
   * * **Branch** — starts a *second* conversation from this point, seeded from
   *   this turn's checkpoint. The conversation you are in keeps every turn it
   *   had; nothing after the branch point is discarded. Absent, rather than
   *   disabled, when the surface cannot branch — a Build workspace conversation
   *   has nowhere to open a branch as itself, and a turn with no checkpoint has
   *   no point to branch from.
   *
   * None of them re-runs a tool, re-uses an approval, or replays a governed
   * action. They put text in a box, send text, or open a second conversation:
   * everything that follows is governed exactly as it was the first time.
   */
  import Icon from "./Icon.svelte";

  let {
    text,
    disabled = false,
    onedit,
    onretry,
    onbranch,
    branching = false,
  }: {
    text: string;
    disabled?: boolean;
    onedit: (text: string) => void;
    onretry: (text: string) => void;
    /** Omitted where branching is not possible, so the control is absent. */
    onbranch?: () => void;
    branching?: boolean;
  } = $props();

  let copied = $state<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      copied = "copied";
    } catch {
      copied = "failed";
    }
    setTimeout(() => (copied = "idle"), 2000);
  }
</script>

<div class="message-actions">
  <button type="button" class="msg-action" onclick={() => void copy()} aria-label="Copy this message">
    <Icon name={copied === "copied" ? "check" : "copy"} size={13} />
    <span>{copied === "copied" ? "Copied" : copied === "failed" ? "Blocked" : "Copy"}</span>
  </button>
  <button
    type="button"
    class="msg-action"
    {disabled}
    onclick={() => onedit(text)}
    aria-label="Edit this message and send it again"
  >
    <Icon name="file-edit" size={13} /><span>Edit</span>
  </button>
  <button
    type="button"
    class="msg-action"
    {disabled}
    onclick={() => onretry(text)}
    aria-label="Send this message again"
  >
    <Icon name="refresh" size={13} /><span>Retry</span>
  </button>
  {#if onbranch}
    <button
      type="button"
      class="msg-action"
      disabled={disabled || branching}
      onclick={() => onbranch()}
      aria-label="Branch a second conversation from this point"
    >
      <Icon name="branch" size={13} /><span>{branching ? "Branching…" : "Branch"}</span>
    </button>
  {/if}
</div>
{#if copied === "failed"}
  <p class="copy-error" role="status">Could not copy — your browser blocked clipboard access.</p>
{/if}

<style>
  /* Quiet until the message is hovered or something inside is focused, so a
     long transcript is not a wall of buttons. Always reachable by keyboard. */
  .message-actions {
    display: flex;
    gap: 0.15rem;
    margin-top: 0.15rem;
    opacity: 0;
    transition: opacity 0.12s ease;
  }
  :global(.message-group:hover) .message-actions,
  :global(.turn:hover) .message-actions,
  .message-actions:focus-within {
    opacity: 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .message-actions { transition: none; }
  }
  @media (hover: none) {
    /* No hover to reveal them on a touch screen, so they stay visible. */
    .message-actions { opacity: 1; }
  }
  .msg-action {
    display: inline-flex;
    align-items: center;
    gap: 0.22rem;
    padding: 0.14rem 0.34rem;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-3);
    font: inherit;
    font-size: 0.7rem;
    cursor: pointer;
  }
  .msg-action:hover:not(:disabled) { background: var(--sunken); color: var(--text-1); }
  .msg-action:disabled { opacity: 0.45; cursor: not-allowed; }
  .msg-action:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
  .copy-error { margin: 0.15rem 0 0; color: var(--danger); font-size: 0.7rem; }
</style>
