<script lang="ts">
  /**
   * COMPOSER-06 — the turn's context as one line you can open.
   *
   * The composer said the same things with separate permanent controls: a
   * project `<select>`, an execution-environment badge, a context ring, and in
   * Build a repository label — four controls, three of which change on a
   * timescale of weeks, all occupying the row under every message the owner
   * ever types. Between them they answered one question, "what is this turn
   * going to see", and answered it in four places at four weights.
   *
   * One line states it:
   *
   *     Project Raiker · 4 files · main · 62%
   *
   * and opening it gives the same facts with room to breathe, plus the one
   * control that changes each. What is *not* here is management: renaming a
   * project, connecting a repository and editing memory are page-level actions
   * (COMPOSER-18) and the line links to them rather than reproducing them.
   *
   * Only what is true appears. A Chat turn with no project and no attachments
   * has nothing to say, so the control is absent rather than rendering "No
   * project · 0 files" — a line that reports emptiness is still a line.
   */
  import Icon from "./Icon.svelte";
  import type { Snippet } from "svelte";

  export interface ContextFact {
    /** What this fact is, in the owner's words. */
    label: string;
    /** The fact. Rendered in the inspector, never abbreviated. */
    value: string;
    /** The compact form for the one-line summary. Omit to keep it out. */
    short?: string;
    /** Where the owner goes to change it. */
    href?: string;
    /** What that link says. */
    action?: string;
  }

  let {
    facts,
    /** Percent of the model's context window this turn is estimated to use. */
    usedPercent = null,
    disabled = false,
    detail,
    onopen,
    open = $bindable(false),
  }: {
    facts: ContextFact[];
    usedPercent?: number | null;
    disabled?: boolean;
    /**
     * Anything the surface wants inside the inspector that is not a `label:
     * value` pair — Chat and Build pass the context meter, which counts tokens,
     * names the window and says when a conversation was compacted. Those facts
     * did not become less true when the ring came off the bar; what changed is
     * that reading them is a deliberate act rather than a permanent control.
     */
    detail?: Snippet;
    /** Called when the inspector opens, so a surface can refresh a live read. */
    onopen?: () => void;
    /**
     * Bindable so the composer's `/context` command opens this rather than a
     * second inspector of its own. The slash command is an accelerator to a
     * control, not a parallel way of showing the same facts.
     */
    open?: boolean;
  } = $props();
  let root = $state<HTMLDivElement>();
  let trigger = $state<HTMLButtonElement>();

  const summary = $derived(
    [
      ...facts.filter((fact) => fact.short).map((fact) => fact.short as string),
      ...(usedPercent === null ? [] : [`${Math.round(usedPercent)}%`]),
    ].join(" · "),
  );

  $effect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (root !== undefined && !root.contains(event.target as Node)) open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      open = false;
      trigger?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  });
</script>

{#if summary !== ""}
  <div class="context-line" bind:this={root}>
    <button
      type="button"
      class="context-summary"
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-label={`Context for this turn: ${summary}`}
      title="What this turn will see"
      {disabled}
      bind:this={trigger}
      onclick={() => {
        open = !open;
        if (open) onopen?.();
      }}
    >
      <span class="summary-text">{summary}</span>
    </button>

    {#if open}
      <div class="inspector" role="dialog" aria-label="Context for this turn">
        <p class="inspector-heading">This turn will see</p>
        <dl>
          {#each facts as fact (fact.label)}
            <div>
              <dt>{fact.label}</dt>
              <dd>
                <span class="fact-value">{fact.value}</span>
                {#if fact.href && fact.action}
                  <a href={fact.href} onclick={() => (open = false)}>{fact.action}</a>
                {/if}
              </dd>
            </div>
          {/each}
          {#if usedPercent !== null}
            <div>
              <dt>Estimated context</dt>
              <dd>
                <span class="fact-value">
                  {Math.round(usedPercent)}% of this model's window
                </span>
              </dd>
            </div>
          {/if}
        </dl>
        {#if detail}<div class="inspector-detail">{@render detail()}</div>{/if}

        <p class="inspector-note">
          <Icon name="info" size="sm" />
          Everything here rides the next turn. Nothing leaves this machine
          except what the model itself is sent.
        </p>
      </div>
    {/if}
  </div>
{/if}

<style>
  .context-line {
    position: relative;
    display: inline-flex;
    min-width: 0;
  }
  /* VIS2-16 — this is information, not attention. It stays the quietest thing
     on the bar until it is opened. */
  .context-summary {
    max-width: 100%;
    min-height: 28px;
    padding: 0.2rem 0.5rem;
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-3);
    font: inherit;
    font-size: var(--text-xs);
    cursor: pointer;
    text-align: left;
  }
  .context-summary:hover:not(:disabled) {
    background: var(--sunken);
    color: var(--text-2);
  }
  .context-summary:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
  .summary-text {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .inspector {
    position: absolute;
    left: 0;
    bottom: calc(100% + 6px);
    z-index: 70;
    width: min(23rem, calc(100vw - 2rem));
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .inspector-heading {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-2xs);
    font-weight: 650;
  }
  dl {
    display: grid;
    gap: 0.35rem;
    margin: 0;
  }
  dl > div {
    display: grid;
    grid-template-columns: minmax(5.5rem, auto) minmax(0, 1fr);
    gap: 0.5rem;
    align-items: baseline;
  }
  dt {
    color: var(--text-3);
    font-size: var(--text-2xs);
  }
  dd {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.4rem;
    min-width: 0;
  }
  .fact-value {
    color: var(--text-1);
    font-size: var(--text-xs);
    overflow-wrap: anywhere;
  }
  dd a {
    font-size: var(--text-2xs);
  }
  .inspector-detail {
    display: grid;
    gap: var(--space-2);
  }
  .inspector-note {
    display: flex;
    align-items: flex-start;
    gap: 0.35rem;
    margin: 0;
    padding-top: var(--space-2);
    border-top: 1px solid var(--border);
    color: var(--text-3);
    font-size: var(--text-2xs);
  }
  @media (max-width: 47.9rem) {
    .inspector {
      position: fixed;
      inset: auto var(--space-3) calc(var(--space-3) + 3.5rem) var(--space-3);
      width: auto;
      max-height: 60vh;
      overflow-y: auto;
    }
  }
</style>
