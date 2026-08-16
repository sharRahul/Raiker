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
    notKeptChars = 0,
  }: {
    /** Reasoning received so far. Empty renders nothing at all. */
    text: string;
    /** True while this turn is still producing reasoning. */
    streaming?: boolean;
    /**
     * BUG-215 — how much working a *re-opened* turn produced when the text
     * itself was not retained. Greater than zero with an empty `text` is the
     * one case this component must not render as silence: the turn did think,
     * and the owner watched it. Saying so is the alternative to a transcript
     * that quietly shows less than it did five minutes earlier.
     */
    notKeptChars?: number;
  } = $props();

  // Open while reasoning is the only thing happening; closed from the moment
  // the turn settles. The owner can still open it afterwards — it is their
  // record of how the answer was reached.
  let opened = $state<boolean | null>(null);
  const expanded = $derived(opened ?? streaming);
</script>

{#if text.trim() === "" && notKeptChars > 0}
  <p class="reasoning-absent">
    <Icon name="shield" size={12} />
    <span>
      Raiker showed its working while this turn ran. It was not kept — retained
      working is off. <a href="#/settings">Turn it on in Settings → Privacy.</a>
    </span>
  </p>
{:else if text.trim() !== ""}
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
  /* The "it thought and that was not kept" line. Deliberately quieter than the
     block it stands in for, and deliberately present: an absent control is
     honest, an absent *fact* is not. */
  .reasoning-absent {
    display: flex;
    align-items: flex-start;
    gap: 0.35rem;
    margin: 0 0 0.4rem;
    color: var(--text-3);
    font-size: 0.74rem;
    line-height: 1.5;
  }
  .reasoning-absent a { color: var(--accent); }
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
