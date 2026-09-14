<script lang="ts">
  /**
   * One permission, as a row in the registry.
   *
   * Extracted from `CapabilitiesView` in the 2026-09-14 overhaul. The view was
   * a thousand lines in which the row's markup, the row's styling, the page's
   * filters and the page's mutations were interleaved, and the row is the part
   * that repeats sixty-six times: it earns its own file, and the page above it
   * becomes readable.
   *
   * The row answers the page's two questions without being opened — REM-PERM-03
   * — and keeps the explanation for the detail, where an owner who wants it can
   * find it. What it must never do is answer them twice or differently: every
   * fact here comes from the one merged gate the page passes in.
   */
  import Icon from "./Icon.svelte";
  import ToolControlBoard from "./ToolControlBoard.svelte";
  import type { CapabilityGate } from "../apiTypes";
  import {
    canDisable,
    canEnable,
    capabilityDescription,
    capabilityLabel,
    isAvailable,
    isOnByDefault,
    unsetResolutionNote,
    type DecisionMode,
  } from "../capabilityModel";
  import {
    AVAILABILITY_QUESTION,
    BEHAVIOUR_QUESTION,
    CANNOT_CHANGE_HERE,
    availabilityAnswer,
    behaviourCopy,
    rowSummary,
  } from "../permissionLanguage";

  let {
    gate,
    open = false,
    selected = false,
    busy = false,
    modes = {},
    toggleId,
    onToggleOpen,
    onToggleSelect,
    onDecision,
    onEnable,
    onDisable,
  }: {
    gate: CapabilityGate;
    open?: boolean;
    selected?: boolean;
    /** A mutation is in flight somewhere on the page, so nothing here may start another. */
    busy?: boolean;
    modes?: Record<string, DecisionMode>;
    /** The row's own control, so a shortcut elsewhere can land focus on it. */
    toggleId: string;
    onToggleOpen: (capability: string) => void;
    onToggleSelect: (capability: string) => void;
    onDecision: (capability: string, mode: DecisionMode) => void;
    onEnable: (gate: CapabilityGate) => void;
    onDisable: (gate: CapabilityGate) => void;
  } = $props();

  const label = $derived(capabilityLabel(gate.capability));
  const available = $derived(isAvailable(gate));
  /**
   * The one contextual explanation the detail carries.
   *
   * REM-PERM-03 — the card used to stack up to three separate paragraphs of
   * prose about the same capability. They are answers to one question, so they
   * are one answer: what this switch really decides, said once.
   *
   * The `Governed elsewhere` / `No route yet` half of that explanation is not
   * read here any more, and not because it stopped mattering: a gate that does
   * not decide its own capability is no longer rendered as a row at all. It is
   * in the page's read-only **Not decided here** list, where the note is the
   * whole content rather than a caveat under a control that should not exist.
   */
  const why = $derived(unsetResolutionNote(gate));
</script>

<div class="cap card" class:open>
  <div class="cap-row">
    <input
      type="checkbox"
      class="cap-check"
      disabled={busy || !gate.can_current_principal_change}
      checked={selected}
      onchange={() => onToggleSelect(gate.capability)}
      aria-label={`Select ${label}`}
    />
    <button
      type="button"
      class="cap-toggle"
      id={toggleId}
      aria-expanded={open}
      onclick={() => onToggleOpen(gate.capability)}
    >
      <span class="chev" aria-hidden="true">
        <Icon name={open ? "chevron-down" : "chevron-right"} size="sm" />
      </span>
      <span class="cap-name">
        <span class="cap-label">{label}</span>
        <!-- Being on because nothing is stored is a different fact from being
             switched on (BUG-239), and the row says which it is rather than
             leaving the summary to contradict a chip beside it. -->
        {#if isOnByDefault(gate)}
          <span class="cap-reality cap-default-on">On by default</span>
        {/if}
      </span>
      <!-- Availability and behaviour, on the closed row: a permission list that
           has to be opened row by row to learn what is on cannot be scanned. -->
      <span class="cap-summary">{rowSummary(gate, available)}</span>
    </button>

    <ToolControlBoard
      gates={[gate]}
      showLabel={false}
      {modes}
      busyCapability={busy ? gate.capability : null}
      onDecision={(capability, mode) => onDecision(capability, mode)}
    />
  </div>

  {#if open}
    <div class="cap-detail">
      <p class="cap-desc">{capabilityDescription(gate.capability)}</p>
      <dl class="cap-facts">
        <div>
          <dt>{AVAILABILITY_QUESTION}</dt>
          <dd>
            <span>{availabilityAnswer(gate, available)}</span>
            <span class="cap-actions">
              {#if canEnable(gate)}
                <button
                  type="button"
                  class="btn btn-soft btn-sm"
                  disabled={busy}
                  onclick={() => onEnable(gate)}>Turn on</button
                >
              {/if}
              {#if canDisable(gate)}
                <button
                  type="button"
                  class="btn btn-danger btn-sm"
                  disabled={busy}
                  onclick={() => onDisable(gate)}>Turn off</button
                >
              {/if}
              {#if !gate.can_current_principal_change}
                <span class="muted">{CANNOT_CHANGE_HERE}</span>
              {/if}
            </span>
          </dd>
        </div>
        <div>
          <dt>{BEHAVIOUR_QUESTION}</dt>
          <!-- NEW-PERM-03 — an unrecognised mode is answered as Unknown rather
               than by dropping the row's behaviour half in silence. -->
          <dd>{behaviourCopy(gate.decision_mode).hint}</dd>
        </div>
        {#if why}
          <div>
            <!-- GEP-04 — a switch that does not decide whether its own
                 capability runs says so, and names what does. -->
            <dt>Why</dt>
            <dd>{why}</dd>
          </div>
        {/if}
      </dl>
    </div>
  {/if}
</div>

<style>
  /* A row in a list, not a card in a stack of cards.
     Fifty bordered, rounded, shadowed cards inside a bordered panel is three
     nested frames around one line of text, and it is most of what made this
     page look busy. The panel is the surface; a hairline is the separator. The
     `card` class stays because the row is addressed by it from outside. */
  .cap.card {
    padding: 0;
    overflow: hidden;
    border: 0;
    border-radius: 0;
    box-shadow: none;
    background: transparent;
    border-bottom: 1px solid var(--border);
  }
  .cap.card:hover {
    background: var(--sunken);
  }
  .cap.card.open {
    background: var(--sunken);
    border-radius: var(--r-md);
  }
  /* Three zones on one line — select, identity, control — so fifty rows read as
     a list rather than as fifty differently ragged flex rows. */
  .cap-row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--row-y) var(--space-4);
  }
  .cap-check {
    accent-color: var(--accent);
  }
  .cap-toggle {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    min-width: 0;
    font: inherit;
    text-align: left;
    background: transparent;
    border: none;
    padding: 0.15rem 0;
    cursor: pointer;
    color: var(--text-1);
  }
  .cap-toggle:hover .cap-label {
    color: var(--accent);
  }
  .chev {
    color: var(--text-3);
    display: grid;
    place-items: center;
  }
  .cap-name {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    min-width: 0;
    flex-wrap: wrap;
  }
  .cap-label {
    font-weight: 600;
  }
  /* BUG-239 — being on because nothing is stored is a different fact from being
     switched on, so it is said rather than left to contradict the summary. */
  .cap-default-on {
    font-size: var(--text-2xs);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    border-radius: var(--r-sm);
    padding: 0.05rem 0.35rem;
    white-space: nowrap;
    color: var(--accent);
    border: 1px solid var(--accent-border);
  }
  /* The row's answer, at metadata weight and in its own column, so the eye can
     run down it instead of hunting for it after a name of varying length. */
  .cap-summary {
    color: var(--text-3);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    justify-self: end;
  }
  .cap-detail {
    border-top: 1px solid var(--border);
    padding: var(--space-3) var(--space-4) var(--space-4);
    /* Indented to the name it belongs to, so an open row reads as one thing. */
    padding-inline-start: calc(var(--space-4) + 1.6rem);
  }
  .cap-desc {
    font-size: var(--text-md);
    color: var(--text-2);
    margin: 0 0 var(--space-3);
    max-width: var(--prose-measure);
  }
  /* One shape for every explanation the card has: question, answer. The card
     used to stack four paragraphs that each looked like a different kind of
     thing. */
  .cap-facts {
    display: grid;
    gap: var(--space-2) var(--space-4);
    margin: 0;
    grid-template-columns: minmax(10rem, auto) minmax(0, 1fr);
  }
  .cap-facts > div {
    display: contents;
  }
  .cap-facts dt {
    color: var(--text-2);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .cap-facts dd {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
    max-width: var(--prose-measure);
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .cap-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .muted {
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  @media (max-width: 860px) {
    /* The control drops to its own line rather than squeezing the name into two
       characters; the summary goes with the name it describes. */
    .cap-row {
      grid-template-columns: auto minmax(0, 1fr);
      row-gap: var(--space-2);
      align-items: start;
    }
    /* On the first line, beside the name it selects — not floating in the
       middle of a three-line row. */
    .cap-check {
      margin-top: 0.3rem;
    }
    .cap-row :global(.tool) {
      grid-column: 2;
    }
    .cap-toggle {
      grid-template-columns: auto minmax(0, 1fr);
    }
    .cap-summary {
      grid-column: 2;
      justify-self: start;
    }
    .cap-detail {
      padding-inline-start: var(--space-4);
    }
    .cap-facts {
      grid-template-columns: minmax(0, 1fr);
      gap: var(--space-1);
    }
    .cap-facts > div {
      display: block;
      margin-bottom: var(--space-2);
    }
  }
</style>
