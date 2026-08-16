<script lang="ts">
  /**
   * The composer's own surface switch — Chat on the left, Build on the right.
   *
   * Chat and Build are two rooms for the same instrument: a conversation, and a
   * conversation that may change a repository. Deciding which one a half-typed
   * prompt belongs in used to mean abandoning the draft, walking the sidebar,
   * and typing it again. This is the same handoff the Workbench already
   * performs — `raiker:compose` / `raiker:build-compose`, carrying the text and
   * whatever files are staged — so switching surface never sends anything and
   * never loses what was written.
   *
   * It is deliberately not a mode. Neither surface's governance changes; the
   * prompt simply arrives at the other one's composer, unsent.
   */
  import type { ComposerAttachment } from "../composerAttachments.svelte";

  let {
    surface,
    draft = "",
    attachments = () => [],
    disabled = false,
  }: {
    /** Which surface this composer is. */
    surface: "chat" | "build";
    /** The text to carry across, if any. */
    draft?: string;
    /**
     * Called only when the owner switches, so the staged files are taken out of
     * this composer exactly once rather than left behind as a duplicate.
     */
    attachments?: () => ComposerAttachment[];
    disabled?: boolean;
  } = $props();

  const surfaces = [
    { id: "chat" as const, label: "Chat", hash: "#/new-chat", event: "raiker:compose" },
    { id: "build" as const, label: "Build", hash: "#/build", event: "raiker:build-compose" },
  ];

  function go(target: (typeof surfaces)[number]) {
    if (disabled || target.id === surface) return;
    const text = draft.trim();
    const staged = text === "" ? [] : attachments();
    window.location.hash = target.hash;
    if (text === "") return;
    // The destination view has to mount and claim its session before it can
    // accept a draft, exactly as the Workbench handoff does.
    window.setTimeout(
      () =>
        window.dispatchEvent(
          new CustomEvent(target.event, { detail: { text, attachments: staged } }),
        ),
      0,
    );
  }
</script>

<div class="surface-toggle" role="group" aria-label="Chat or Build">
  {#each surfaces as option (option.id)}
    <button
      type="button"
      class="surface-option"
      aria-pressed={surface === option.id}
      aria-current={surface === option.id ? "true" : undefined}
      {disabled}
      title={option.id === surface
        ? `This is the ${option.label} composer`
        : `Move this prompt to ${option.label} without sending it`}
      onclick={() => go(option)}
    >
      {option.label}
    </button>
  {/each}
</div>

<style>
  .surface-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.1rem;
    padding: 0.12rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-pill);
    background: var(--sunken);
  }
  .surface-option {
    font: inherit;
    font-size: 0.76rem;
    font-weight: 650;
    padding: 0.16rem 0.6rem;
    border: 1px solid transparent;
    border-radius: var(--r-pill);
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
  }
  .surface-option:hover:not(:disabled):not([aria-pressed="true"]) {
    color: var(--text-1);
  }
  .surface-option[aria-pressed="true"] {
    border-color: var(--border);
    background: var(--surface);
    color: var(--text-1);
    box-shadow: var(--shadow-0);
  }
  .surface-option:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
