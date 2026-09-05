<script lang="ts">
  import {
    capabilityLabel,
    DECISION_MODES,
    DECISION_MODE_COPY,
    isDecisionMode,
    isDeferred,
    type DecisionMode,
  } from "../capabilityModel";
  import type { CapabilityGate } from "../apiTypes";

  let {
    gates,
    onDecision,
    busyCapability = null,
    modes = {},
    showLabel = true,
  }: {
    gates: CapabilityGate[];
    onDecision: (capability: string, mode: DecisionMode) => void;
    /** Capability whose mode change is in flight (its buttons disable). */
    busyCapability?: string | null;
    /** Optimistic overrides applied after a confirmed set, keyed by capability. */
    modes?: Record<string, DecisionMode>;
    showLabel?: boolean;
  } = $props();

  // Decision controls exist only for real, changeable tools: a deferred
  // capability has no executor, and an unchangeable gate offers no lever.
  const actionable = $derived(gates.filter((gate) => !isDeferred(gate) && gate.can_current_principal_change));

  function modeFor(gate: CapabilityGate): DecisionMode | "unknown" {
    const override = modes[gate.capability];
    if (override !== undefined) return override;
    return isDecisionMode(gate.decision_mode) ? gate.decision_mode : "unknown";
  }
</script>

{#each actionable as gate (gate.capability)}
  <section class="tool">
    {#if showLabel}<strong>{capabilityLabel(gate.capability)}</strong>{/if}
    <div class="mode-seg" role="group" aria-label={`Decision mode for ${capabilityLabel(gate.capability)}`}>
      {#each DECISION_MODES as mode (mode)}
        <button
          type="button"
          class="mode-btn"
          class:selected={modeFor(gate) === mode}
          aria-pressed={modeFor(gate) === mode}
          title={DECISION_MODE_COPY[mode].hint}
          disabled={busyCapability === gate.capability}
          onclick={() => onDecision(gate.capability, mode)}
        >
          {DECISION_MODE_COPY[mode].label}
        </button>
      {/each}
    </div>
  </section>
{/each}

<style>
  .tool {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .mode-seg {
    display: inline-flex;
    gap: 2px;
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 3px;
    flex-shrink: 0;
  }
  .mode-btn {
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-2);
    background: transparent;
    border: none;
    border-radius: var(--r-pill);
    padding: 0.2rem 0.7rem;
    cursor: pointer;
  }
  .mode-btn:hover:not(:disabled):not(.selected) {
    color: var(--text-1);
  }
  .mode-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .mode-btn.selected {
    background: var(--accent-soft);
    color: var(--accent);
    box-shadow: var(--shadow-1);
  }
</style>
