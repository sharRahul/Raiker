<script lang="ts">
  /**
   * QUI-L06 — one permission, in the detail pane beside its category's list.
   *
   * The list row shows the current policy as text; the four-way choice (Ask me,
   * Allow, Automatic, Never) lives here, one control at a time instead of one
   * per row. Every fact comes from the one merged gate the page passes in, so
   * the row and this pane cannot disagree (NEW-PERM-02).
   */
  import ToolControlBoard from "./ToolControlBoard.svelte";
  import type { CapabilityGate } from "../apiTypes";
  import {
    canDisable,
    canEnable,
    capabilityDescription,
    capabilityLabel,
    isAvailable,
    isOnByDefault,
    sideEffectChip,
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
    review = null,
    busy = false,
    modes = {},
    onDecision,
    onEnable,
    onDisable,
  }: {
    gate: CapabilityGate;
    /** Why this permission wants a second look, when it does. */
    review?: string | null;
    /** A mutation is in flight somewhere on the page, so nothing here may start another. */
    busy?: boolean;
    modes?: Record<string, DecisionMode>;
    onDecision: (capability: string, mode: DecisionMode) => void;
    onEnable: (gate: CapabilityGate) => void;
    onDisable: (gate: CapabilityGate) => void;
  } = $props();

  const label = $derived(capabilityLabel(gate.capability));
  const available = $derived(isAvailable(gate));
  const why = $derived(unsetResolutionNote(gate));
  const reach = $derived(sideEffectChip(gate));
</script>

<article class="permission-detail" aria-label={label}>
  <header>
    <h2>{label}</h2>
    <p class="summary">{rowSummary(gate, available)}</p>
    <div class="chips">
      {#if gate.enabled_by_connection}
        <span class="chip-fact">On by connection</span>
      {:else if isOnByDefault(gate)}
        <span class="chip-fact">On by default</span>
      {/if}
      {#if reach}<span class="chip-fact" data-tone={reach.tone}>{reach.label}</span>{/if}
    </div>
  </header>

  {#if review}
    <p class="review" role="note"><strong>Needs review.</strong> {review}</p>
  {/if}

  <p class="description">{capabilityDescription(gate.capability)}</p>

  <section aria-label={BEHAVIOUR_QUESTION}>
    <h3>{BEHAVIOUR_QUESTION}</h3>
    <ToolControlBoard
      gates={[gate]}
      showLabel={false}
      {modes}
      busyCapability={busy ? gate.capability : null}
      onDecision={(capability, mode) => onDecision(capability, mode)}
    />
    <p class="note">{behaviourCopy(gate.decision_mode).hint}</p>
  </section>

  <section aria-label={AVAILABILITY_QUESTION}>
    <h3>{AVAILABILITY_QUESTION}</h3>
    <p class="note">{availabilityAnswer(gate, available)}</p>
    <div class="actions">
      {#if canEnable(gate)}
        <button type="button" class="btn btn-soft btn-sm" disabled={busy} onclick={() => onEnable(gate)}>
          Turn on
        </button>
      {/if}
      {#if canDisable(gate)}
        <button type="button" class="btn btn-danger btn-sm" disabled={busy} onclick={() => onDisable(gate)}>
          Turn off
        </button>
      {/if}
      {#if !gate.can_current_principal_change}
        <span class="note">{CANNOT_CHANGE_HERE}</span>
      {/if}
    </div>
  </section>

  {#if gate.ungoverned_consequence || gate.authority_requirement || gate.network_boundary || why}
    <dl class="facts">
      {#if gate.ungoverned_consequence}
        <dt>If it ran without you</dt>
        <dd>{gate.ungoverned_consequence}</dd>
      {/if}
      {#if gate.authority_requirement}
        <dt>What stands in the way</dt>
        <dd>{gate.authority_requirement}</dd>
      {/if}
      {#if gate.network_boundary}
        <dt>On this machine</dt>
        <dd data-testid="network-boundary">{gate.network_boundary}</dd>
      {/if}
      {#if why}
        <dt>Why</dt>
        <dd>{why}</dd>
      {/if}
    </dl>
  {/if}
</article>

<style>
  .permission-detail {
    display: grid;
    gap: var(--space-3);
  }
  header h2 {
    margin: 0;
    font-size: var(--text-lg);
  }
  .summary {
    margin: 0.2rem 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .chips:empty {
    display: none;
  }
  .chip-fact {
    font-size: var(--text-2xs);
    font-weight: 650;
    border-radius: var(--r-sm);
    padding: 0.05rem 0.4rem;
    color: var(--text-2);
    border: 1px solid var(--border);
  }
  .chip-fact[data-tone="warn"] {
    color: var(--warn-text);
    border-color: var(--warn-border);
  }
  .chip-fact[data-tone="hot"] {
    color: var(--danger);
    border-color: var(--danger-border);
  }
  .review {
    margin: 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--warn-border);
    border-radius: var(--r-sm);
    color: var(--text-1);
    font-size: var(--text-sm);
  }
  .description {
    margin: 0;
    color: var(--text-2);
    max-width: var(--prose-measure);
  }
  section {
    display: grid;
    gap: var(--space-2);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  h3 {
    margin: 0;
    font-size: var(--text-sm);
  }
  .note {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .actions:empty {
    display: none;
  }
  .facts {
    display: grid;
    grid-template-columns: minmax(9rem, auto) minmax(0, 1fr);
    gap: var(--space-2) var(--space-4);
    margin: 0;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  .facts dt {
    color: var(--text-2);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .facts dd {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
</style>
