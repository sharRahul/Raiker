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
   * repository, while Design exposes a compact image workflow.
   *
   * 2026-11-07 — the frame is a floating glass capsule (owner decision, 03
   * Composer control deck): a translucent, blurred card with margins that the
   * work above can pass beneath, solid where blur is unavailable or reduced
   * transparency is asked for. The input grows to five lines first (`promptCapPx`).
   */
  import type { Snippet } from "svelte";
  import type { HTMLTextareaAttributes } from "svelte/elements";
  import { promptCapPx } from "../composerCommands";

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
    /** Let the surface above pass beneath the capsule's top edge. Only for a
     *  view whose scroller pads its end by `--composer-overlap`. */
    overlap?: boolean;
    /** A context guardrail sentence; the card turns amber while it is set. */
    contextWarning?: string | null;
    /** What a drop adds, said inside the dashed drop zone. */
    dropLabel?: string;
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
    overlap = false,
    contextWarning = null,
    dropLabel = "Drop documents, data files or images here to add them as context",
  }: Props = $props();

  // Re-measure on draft changes, including restored or programmatically populated drafts.
  $effect(() => {
    if (!inputEl || typeof value !== "string") return;
    const cap = promptCapPx(inputEl);
    inputEl.style.maxHeight = `${cap}px`;
    inputEl.style.height = "auto";
    inputEl.style.height = `${Math.min(inputEl.scrollHeight, cap)}px`;
  });
</script>

<form
  class="composer"
  class:overlap
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
    class:context-warn={contextWarning !== null}
    {...dropHandlers}
  >
    {@render above?.()}

    {#if dropActive}
      <!-- A drop is a place, not an invisible listener: the zone says what it takes. -->
      <div class="drop-zone" role="status"><span>{dropLabel}</span></div>
    {/if}

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

    {#if contextWarning !== null}
      <p class="context-warning" role="status"><span aria-hidden="true">⚠</span> {contextWarning}</p>
    {/if}

    {@render footer?.()}

    {#if hint}<p class="shortcut-hint">{@render hint()}</p>{/if}
  </div>
</form>

<style>
  .composer {
    --composer-overlap: var(--space-6);
    position: relative;
    z-index: 2;
    padding-top: var(--space-3);
    /* The capsule floats: margin below and at the sides, never flush to the edge. */
    padding-bottom: var(--space-4);
    width: min(calc(100% - 2 * var(--space-4)), 47.5rem);
    margin-inline: auto;
    background: transparent;
  }
  /* The transcript passes beneath the capsule's top edge. */
  .composer.overlap { margin-top: calc(-1 * var(--composer-overlap)); padding-top: 0; }
  .composer-card {
    position: relative;
    /* A stacking context for the glass layer below, without a containing
       block: `backdrop-filter` on the card itself would make every
       `position: fixed` menu inside it (the phone bottom sheets) position
       against the card instead of the viewport. */
    isolation: isolate;
    /* A clearer edge against the workspace in dark (2026-11-07). */
    border: 1px solid var(--composer-edge);
    border-radius: var(--r-xl);
    background: transparent;
    box-shadow: var(--shadow-2);
    transition: border-color 120ms ease, box-shadow 120ms ease;
    /* Even padding all round: a tighter bottom makes the control bar look
       cropped against the card edge. */
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  /* Typing is the primary act on every page that has one of these, so the card
     lifts while it has focus instead of only changing a border by one shade. */
  .composer-card:focus-within {
    border-color: var(--accent-border);
    box-shadow: var(--shadow-3);
  }
  /* The glass itself: a layer behind the card's content. */
  .composer-card::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    background: var(--glass-surface);
    -webkit-backdrop-filter: var(--glass-blur);
    backdrop-filter: var(--glass-blur);
    pointer-events: none;
  }
  /* Solid where glass cannot be drawn or is not wanted. */
  @supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
    .composer-card::before { background: var(--surface); }
  }
  @media (prefers-reduced-transparency: reduce) {
    .composer-card::before { background: var(--surface); -webkit-backdrop-filter: none; backdrop-filter: none; }
  }
  .composer-card.context-warn,
  .composer-card.context-warn:focus-within { border-color: var(--warn-border); animation: warn-pulse 1.6s ease-out 1; }
  @keyframes warn-pulse {
    0% { box-shadow: 0 0 0 0 var(--warn-border); }
    100% { box-shadow: 0 0 0 6px transparent; }
  }
  .context-warning { margin: 0; color: var(--warn); font-size: var(--text-xs); }
  .drop-zone {
    position: absolute;
    inset: var(--space-1);
    z-index: 3;
    display: grid;
    place-items: center;
    padding: var(--space-3);
    border: 2px dashed var(--accent-border);
    border-radius: var(--r-lg);
    background: var(--surface);
    color: var(--text-1);
    font-size: var(--text-sm);
    text-align: center;
    pointer-events: none;
  }
  .composer-card.drop-active { min-height: 9rem; }
  @media (prefers-reduced-motion: reduce) {
    .composer-card { transition: none; }
    .composer-card.context-warn { animation: none; }
  }
  /* Upper area: the prompt, and nothing else — the per-turn controls sit below,
     where every composer keeps the model chip. */
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
    resize: none;
    overflow-y: auto;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-md);
    min-height: 2.6rem;
  }
  .prompt-input:focus-visible { outline: none; box-shadow: none; }
  .prompt-input::placeholder {
    color: var(--text-3);
  }
  .composer-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem 0.75rem;
    padding-top: 0.25rem;
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

  /* Keep the controls on a common baseline and touch target across surfaces. */
  :global(.composer-card .action-trigger),
  :global(.composer-card .mode-trigger),
  :global(.composer-card .profile .chip),
  :global(.composer-card .model-trigger),
  :global(.composer-card .voice-button) { min-height: 2.5rem; height: 2.5rem; box-sizing: border-box; }
  :global(.composer-card .action-trigger:not(.is-tools)),
  :global(.composer-card .voice-button) { width: 2.5rem; }

  :global(.design-composer .send), :global(.chat-composer .send), :global(.composer-build .send) { width: 2.5rem; height: 2.5rem; min-width: 2.5rem; padding: 0; border-radius: 50%; }
  :global(.design-composer .send-label), :global(.chat-composer .send-label), :global(.composer-build .send-label) { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

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
    :global(.design-composer .model-scope) { display: flex; }
    :global(.design-composer .model-scope select) { max-width: 8rem; }
    :global(.composer-card .send) {
      width: 2.75rem;
      height: 2.75rem;
      min-width: 2.75rem;
      margin-left: 0;
      padding: 0;
      border-radius: 50%;
    }
    /* Visually hidden, never `display: none`: the label is the button's
       accessible name, and hiding it that way left every composer's primary
       action nameless at phone width — found by the 2026-10-03 live round,
       where Build's Run could not be found by its name at 390 px. */
    :global(.composer-card .send-label) {
      position: absolute;
      width: 1px;
      height: 1px;
      margin: -1px;
      padding: 0;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
      border: 0;
    }
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
