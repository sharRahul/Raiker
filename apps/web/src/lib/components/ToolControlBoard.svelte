<script lang="ts">
  import { DECISION_MODES, DECISION_MODE_COPY, isDeferred, type DecisionMode } from "../capabilityModel";
  import type { CapabilityGate } from "../apiTypes";
  let { gates, onDecision }: { gates: CapabilityGate[]; onDecision: (capability: string, mode: DecisionMode) => void } = $props();
  const actionable = $derived(gates.filter((gate) => !isDeferred(gate) && gate.can_current_principal_change));
</script>

{#each actionable as gate (gate.capability)}
  <section class="tool" aria-label={gate.capability}>
    <strong>{gate.capability}</strong>
    <div role="group" aria-label={`Decision mode for ${gate.capability}`}>
      {#each DECISION_MODES as mode}
        <button type="button" aria-pressed={gate.decision_mode === mode} title={DECISION_MODE_COPY[mode].hint} onclick={() => onDecision(gate.capability, mode)}>{DECISION_MODE_COPY[mode].label}</button>
      {/each}
    </div>
  </section>
{/each}
