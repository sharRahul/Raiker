<script lang="ts">
  import type { CapabilityGate } from "./apiTypes";
  import { explainCapability } from "./capabilityModel";

  let { gate }: { gate: CapabilityGate } = $props();
  const info = $derived(explainCapability(gate));
</script>

<div class="explainer">
  <p><span class="k">Status</span> <code>{info.status}</code></p>
  <p><span class="k">Why</span> {info.why}</p>
  <p><span class="k">To enable</span> {info.requirement}</p>
  <p>
    <span class="k">Type</span>
    {#if info.kind === "deferred"}Future / deferred (not implemented){:else if info.kind === "gated"}Implemented but gated{:else}Enabled{/if}
  </p>
</div>

<style>
  .explainer {
    border-left: 2px solid #33333a;
    padding: 0.25rem 0 0.25rem 0.75rem;
    margin: 0.25rem 0 0.5rem;
    font-size: 0.82rem;
    color: #b6b6bd;
  }
  .explainer p {
    margin: 0.15rem 0;
  }
  .k {
    color: #8b8b93;
    text-transform: uppercase;
    font-size: 0.66rem;
    letter-spacing: 0.05em;
    margin-right: 0.4rem;
  }
</style>
