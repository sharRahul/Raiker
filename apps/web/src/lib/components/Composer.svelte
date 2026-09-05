<script lang="ts">
  /**
   * The composer frame, once.
   *
   * Chat and Build each carried their own copy of this markup and roughly
   * thirty CSS selectors for it, and the two copies had already drifted: one
   * styled `.prompt-input`, the other `.composer-card textarea`; one let
   * `.bar-left` wrap and the other did not; the compact rules that keep the
   * model control legible below 1024px existed in Chat and nowhere else. None
   * of that is visible in review, and all of it is visible as two pages that
   * are *almost* the same shape.
   *
   * So the frame lives here and the controls stay with the view that owns them.
   * This component decides the card, the input, the two-row bar and every
   * breakpoint; a view decides what goes in `left`, `right` and `above`, which
   * is the part that genuinely differs — Build has a mode picker and a
   * repository, Design has a size and a count, Chat has neither.
   */
  import type { Snippet } from "svelte";
  import type { HTMLTextareaAttributes } from "svelte/elements";

  interface Props {
    /** The draft. Bindable: the view owns the text, this owns the box. */
    value: string;
    /** Names the group for a screen reader — "Message composer", "Build composer". */
    ariaLabel: string;
    /** An extra class on the card, so a surface with genuinely more controls
     *  can override a compact rule without reaching into `.composer-card`
     *  globally. Build carries six controls on the left where Chat has four,
     *  and needs them to wrap where Chat's must not. */
    cardClass?: string;
    /** Distinct per surface so two composers on one page cannot collide. */
    inputId: string;
    /** Visible-to-assistive-tech label for the textarea itself. */
    inputLabel?: string;
    /** Anything the textarea needs that this component does not decide: the
     *  placeholder, `disabled`, and the view's own key and selection handlers. */
    inputProps?: HTMLTextareaAttributes;
    /** The textarea element, for views that focus or measure it. */
    inputEl?: HTMLTextAreaElement | undefined;
    /** True while a file is being dragged over the card. */
    dropActive?: boolean;
    /** Drag handlers from the view's drop store, applied to the card. */
    dropHandlers?: Record<string, (event: DragEvent) => void>;
    onsubmit: () => void;
    /** Chips, readiness strips, slash menus — anything above the input. */
    above?: Snippet;
    /** The attach panel, which opens between the input and the bar. */
    below?: Snippet;
    /** A row of its own while a turn is running, for stop and steer. */
    turn?: Snippet;
    /** Whether that row is showing. Separate from `turn` because a snippet is
     *  always *provided*; without this the bar renders empty — a stray rule
     *  across the card whenever nothing is running. */
    turnActive?: boolean;
    left: Snippet;
    right: Snippet;
    /** Between the bar and the hint: a live-region line about *this* turn —
     *  which project it will run in, or why send is disabled. Its own slot
     *  rather than part of `hint`, because a status message is a block element
     *  with a `role` and the hint is one right-aligned line of key names. */
    footer?: Snippet;
    hint?: Snippet;
  }

  let {
    value = $bindable(),
    ariaLabel,
    cardClass = "",
    inputId,
    inputLabel = "Prompt",
    inputProps = {},
    inputEl = $bindable(undefined),
    dropActive = false,
    dropHandlers = {},
    onsubmit,
    above,
    below,
    turn,
    turnActive = false,
    left,
    right,
    footer,
    hint,
  }: Props = $props();
</script>

<form
  class="composer"
  onsubmit={(event) => {
    event.preventDefault();
    onsubmit();
  }}
>
  <div
    class="composer-card {cardClass}"
    role="group"
    aria-label={ariaLabel}
    class:drop-active={dropActive}
    {...dropHandlers}
  >
    {@render above?.()}

    {#if dropActive}<p class="drop-note" role="status">Drop to attach</p>{/if}

    <label for={inputId} class="sr-only">{inputLabel}</label>
    <div class="composer-upper">
      <textarea
        id={inputId}
        class="prompt-input"
        bind:this={inputEl}
        bind:value
        rows="2"
        spellcheck="true"
        lang="en-US"
        {...inputProps}
      ></textarea>
    </div>

    {@render below?.()}

    {#if turnActive && turn}
      <!-- While a turn is running the composer's job changes: it is no longer
           where the next question is written, it is where this one is stopped
           or corrected. -->
      <div class="composer-bar">{@render turn()}</div>
    {/if}

    <div class="composer-bar">
      <div class="bar-left">{@render left()}</div>
      <div class="bar-right">{@render right()}</div>
    </div>

    {@render footer?.()}

    {#if hint}<p class="shortcut-hint">{@render hint()}</p>{/if}
  </div>
</form>

<style>
  .composer {
    padding-top: var(--space-3);
    background: var(--bg);
  }
  .composer-card {
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    box-shadow: var(--shadow-1);
    transition: border-color 120ms ease, box-shadow 120ms ease;
    /* Even padding all round: a tighter bottom makes the control bar look
       cropped against the card edge. */
    padding: 0.75rem 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  /* Typing is the primary act on every page that has one of these, so the card
     lifts while it has focus instead of only changing a border by one shade. */
  .composer-card:focus-within {
    border-color: var(--accent-border);
    box-shadow: var(--shadow-2);
  }
  @media (prefers-reduced-motion: reduce) {
    .composer-card { transition: none; }
  }
  /* Upper area: the prompt, and nothing else. Per-turn controls used to sit in
     a column to its right, which cost the prompt a third of the card's width
     and put the model chip somewhere no other composer keeps it. */
  .composer-upper {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .prompt-input {
    flex: 1;
    min-width: 0;
    width: 100%;
    border: none;
    outline: none;
    resize: vertical;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-md);
    min-height: 2.6rem;
  }
  .prompt-input::placeholder {
    color: var(--text-3);
  }
  .composer-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem 0.75rem;
    border-top: 1px solid var(--border);
    padding-top: 0.55rem;
    flex-wrap: wrap;
  }
  .bar-left {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    flex-wrap: wrap;
    min-width: 0;
  }
  /* Per-turn settings sit on the right of the bar, ending in the send action. */
  .bar-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.3rem;
    flex-wrap: wrap;
    min-width: 0;
    justify-content: flex-end;
  }
  .shortcut-hint {
    color: var(--text-3);
    font-size: var(--text-xs);
    line-height: 1.35;
    margin: 0;
    text-align: right;
  }
  /* The hint's content comes from the view's snippet, so it carries the view's
     scope and not this component's — these have to be global to reach it. */
  :global(.shortcut-hint code) {
    padding: 0 0.22rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    font-family: var(--font-mono);
    font-size: var(--text-2xs);
  }
  :global(.shortcut-hint .hint-link) {
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
    text-decoration: underline;
  }

  /* Kept after the base rules so compact declarations win without changing a
     single desktop selector. */
  @media (max-width: 63.9rem) {
    .composer { flex-shrink: 0; padding-top: var(--space-2); }
    .composer-card {
      gap: .3rem;
      padding: .55rem .6rem;
      border-radius: 1rem;
      box-shadow: none;
    }
    .prompt-input { min-height: 2.25rem; resize: none; }
    /* Wraps rather than drops: a control that gates or steers a turn moves to a
       second row instead of leaving the screen. */
    .composer-bar { flex-wrap: wrap; gap: .25rem; padding-top: .4rem; }
    .bar-left, .bar-right { flex-wrap: nowrap; gap: .2rem; }
    .bar-right { margin-left: auto; width: auto; justify-content: flex-end; }
    .shortcut-hint { display: none; }
    :global(.composer-card .composer-scope),
    :global(.composer-card .context-control) { display: none; }
    :global(.composer-card .send) {
      width: 2.75rem;
      height: 2.75rem;
      min-width: 2.75rem;
      margin-left: 0;
      padding: 0;
      border-radius: 50%;
    }
    :global(.composer-card .send-label) { display: none; }
    :global(.composer-card .model-trigger) {
      min-width: 2.75rem;
      width: 2.75rem;
      height: 2.75rem;
      padding: 0;
      justify-content: center;
    }
    /* `> span` hid the provider logo along with the label, because the logo is
       a span and not an svg — so below 1024px the model control was an empty
       circle and no window narrower than a laptop said which model would
       answer. The label and the effort chip go; the logo is the control. */
    :global(.composer-card .model-trigger > span:not(.provider-logo)),
    :global(.composer-card .model-trigger > svg:last-child),
    :global(.composer-card .approval-trigger > span),
    :global(.composer-card .approval-trigger > svg:last-child) { display: none; }
    :global(.composer-card .approval-trigger) {
      width: 2.75rem;
      height: 2.75rem;
      padding: 0;
      justify-content: center;
    }
  }
</style>
