<script lang="ts">
  /**
   * The model's own reasoning for this turn (BUG-207 slice C).
   *
   * What stood here before was a disclosure labelled "See what Raiker is
   * thinking" holding a subset of three fixed sentences, chosen by lifecycle
   * event type — the same words for a one-word question and a twenty-tool
   * build. Slice A removed it, because a careful placeholder labelled as the
   * model's thinking is still a false label. This is the real thing, and it
   * appears only when there is one.
   *
   * Three rules it exists to keep:
   *
   * 1. **Never a stand-in.** No reasoning means no block — not an empty one,
   *    not a hint that some was withheld.
   * 2. **Never the thing the eye lands on.** It is collapsed the moment the
   *    answer starts, so what a settled turn shows is the answer.
   * 3. **The provider's, not Raiker's.** Where the profile can return a
   *    *summary* of its reasoning, that is what the runtime asks for and what
   *    arrives here. The text is rendered as plain text rather than Markdown:
   *    it is the model's working, and giving it the same typographic weight as
   *    the answer would invite it to be read as one.
   */
  import Icon from "./Icon.svelte";

  let {
    text,
    streaming = false,
  }: {
    /** Reasoning received so far. Empty renders nothing at all. */
    text: string;
    /** True while this turn is still producing reasoning. */
    streaming?: boolean;
  } = $props();

  // Open while reasoning is the only thing happening; closed from the moment
  // the turn settles. The owner can still open it afterwards — it is their
  // record of how the answer was reached.
  let opened = $state<boolean | null>(null);
  const expanded = $derived(opened ?? streaming);
</script>

{#if text.trim() !== ""}
  <section class="reasoning" data-streaming={streaming ? "true" : "false"}>
    <button
      type="button"
      class="reasoning-toggle"
      aria-expanded={expanded}
      aria-controls="reasoning-body"
      onclick={() => (opened = !expanded)}
    >
      <Icon name={expanded ? "chevron-down" : "chevron-right"} size={13} />
      <span>Thinking</span>
      {#if streaming}<span class="reasoning-live" aria-hidden="true"></span>{/if}
    </button>
    {#if expanded}
      <p id="reasoning-body" class="reasoning-body">{text}</p>
    {/if}
  </section>
{/if}

<style>
  .reasoning {
    margin: 0 0 0.4rem;
    display: grid;
    gap: 0.3rem;
    justify-items: start;
  }
  .reasoning-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 0;
    background: transparent;
    color: var(--text-3);
    font: inherit;
    font-size: 0.76rem;
    font-weight: 650;
    letter-spacing: 0.02em;
    cursor: pointer;
    padding: 0;
  }
  .reasoning-toggle:hover { color: var(--text-2); }
  .reasoning-toggle:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
    border-radius: var(--r-sm);
  }
  .reasoning-live {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    animation: reasoning-live 1.4s ease-in-out infinite;
  }
  @keyframes reasoning-live {
    0%, 100% { opacity: 0.35; }
    50% { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .reasoning-live { animation: none; opacity: 0.8; }
  }
  /* Quieter than the answer on purpose: smaller, dimmer, and against the sunken
     surface, so a long chain of thought never competes with what it produced. */
  .reasoning-body {
    margin: 0;
    padding: 0.5rem 0.65rem;
    border-left: 2px solid var(--border);
    background: var(--sunken);
    border-radius: var(--r-sm);
    color: var(--text-3);
    font-size: 0.8rem;
    line-height: 1.55;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    max-height: 18rem;
    overflow-y: auto;
  }
</style>
