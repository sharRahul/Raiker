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
   * * **Summarise** — replaces everything up to and including this turn with a
   *   summary, in what the *model* is sent. The transcript is not touched:
   *   every turn stays on screen, stays exportable, and stays what a branch is
   *   taken from. Absent, rather than disabled, where the surface cannot
   *   compact.
   * * **Rewind** (B18) — the one action here that can change a file, and the
   *   reason it is the last item rather than a fourth button: it opens the
   *   governed preflight for the checkpoint this turn wrote. Nothing is
   *   restored by opening it, and nothing is restored without an approval.
   *
   * Only Copy, Edit and Retry sit in the row. Branch, Summarise and Rewind are
   * used rarely and read as long labels, so they live behind **More** — the row
   * under every message stays three short words instead of six long ones, at
   * every window size, and each of the three keeps the sentence that says what
   * it means where there is room to read it.
   *
   * None of them re-runs a tool, re-uses an approval, or replays a governed
   * action on its own. They put text in a box, send text, open a second
   * conversation, shorten what the next turn carries, or *ask* for a rewind:
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
    oncompact,
    compacting = false,
    onrewind,
    rewinding = false,
  }: {
    text: string;
    disabled?: boolean;
    onedit: (text: string) => void;
    onretry: (text: string) => void;
    /** Omitted where branching is not possible, so the control is absent. */
    onbranch?: () => void;
    branching?: boolean;
    /** Omitted where compaction is not possible, so the control is absent. */
    oncompact?: () => void;
    compacting?: boolean;
    /** Omitted where there is no checkpoint to rewind to. */
    onrewind?: () => void;
    rewinding?: boolean;
  } = $props();

  let copied = $state<"idle" | "copied" | "failed">("idle");
  let moreOpen = $state(false);
  let moreEl = $state<HTMLDivElement | undefined>();
  const hasMore = $derived(onbranch !== undefined || oncompact !== undefined || onrewind !== undefined);

  function closeMore() {
    moreOpen = false;
  }

  function onWindowClick(event: MouseEvent) {
    if (!moreOpen) return;
    if (event.target instanceof Node && moreEl?.contains(event.target)) return;
    moreOpen = false;
  }

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

<svelte:window onclick={onWindowClick} />

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
  {#if hasMore}
    <div class="more" bind:this={moreEl}>
      <button
        type="button"
        class="msg-action"
        {disabled}
        aria-haspopup="menu"
        aria-expanded={moreOpen}
        aria-label="More actions for this message"
        onclick={() => (moreOpen = !moreOpen)}
      >
        <Icon name="more" size={13} /><span class="sr-only">More</span>
      </button>
      {#if moreOpen}
        <div class="more-menu" role="menu">
          {#if onbranch}
            <button
              type="button"
              role="menuitem"
              disabled={disabled || branching}
              onclick={() => {
                closeMore();
                onbranch();
              }}
            >
              <Icon name="branch" size={13} />
              <span>
                <strong>{branching ? "Branching…" : "Branch"}</strong>
                <em>A second conversation from here. This one keeps every turn.</em>
              </span>
            </button>
          {/if}
          {#if oncompact}
            <button
              type="button"
              role="menuitem"
              disabled={disabled || compacting}
              onclick={() => {
                closeMore();
                oncompact();
              }}
            >
              <Icon name="fit" size={13} />
              <span>
                <strong>{compacting ? "Summarising…" : "Summarise up to here"}</strong>
                <em>Shortens what the model is sent. Nothing leaves this transcript.</em>
              </span>
            </button>
          {/if}
          {#if onrewind}
            <button
              type="button"
              role="menuitem"
              disabled={disabled || rewinding}
              onclick={() => {
                closeMore();
                onrewind();
              }}
            >
              <Icon name="checkpoints" size={13} />
              <span>
                <strong>{rewinding ? "Reading checkpoint…" : "Rewind to before this"}</strong>
                <em>Previews the file changes, then asks for approval.</em>
              </span>
            </button>
          {/if}
        </div>
      {/if}
    </div>
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
  .more {
    position: relative;
    display: inline-flex;
  }
  /* Anchored to the handle rather than to the viewport: the row sits under a
     message that can be anywhere in a long transcript, and a fixed sheet would
     open away from the thing it belongs to. */
  .more-menu {
    position: absolute;
    top: calc(100% + 0.2rem);
    left: 0;
    z-index: 30;
    min-width: 15rem;
    max-width: min(20rem, calc(100vw - 2rem));
    display: grid;
    gap: 0.1rem;
    padding: 0.25rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    box-shadow: var(--shadow-2);
  }
  .more-menu button {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: start;
    gap: 0.45rem;
    width: 100%;
    padding: 0.35rem 0.45rem;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-1);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .more-menu button:hover:not(:disabled) { background: var(--sunken); }
  .more-menu button:disabled { opacity: 0.45; cursor: not-allowed; }
  .more-menu button:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
  .more-menu strong {
    display: block;
    font-size: 0.78rem;
    font-weight: 650;
  }
  .more-menu em {
    display: block;
    font-style: normal;
    font-size: 0.7rem;
    color: var(--text-3);
  }
  .copy-error { margin: 0.15rem 0 0; color: var(--danger); font-size: 0.7rem; }
</style>
