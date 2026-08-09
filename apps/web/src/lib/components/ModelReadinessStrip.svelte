<script lang="ts">
  import type { ModelReadinessView } from "../apiTypes";
  import { openModelSetup } from "../modelReadiness.svelte";

  let {
    readiness,
    draftPreserved = false,
  }: {
    readiness: ModelReadinessView | null;
    draftPreserved?: boolean;
  } = $props();
</script>

{#if readiness && !readiness.ready}
  <div class="readiness-strip" role="status">
    <span class="indicator" aria-hidden="true"></span>
    <div class="copy">
      <strong>{readiness.summary}</strong>
      <span>{readiness.remediation}</span>
      {#if draftPreserved}<span class="draft">Your draft is preserved.</span>{/if}
    </div>
    <button type="button" onclick={() => openModelSetup(null, readiness)}>Set up model</button>
  </div>
{/if}

<style>
  .readiness-strip { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: .65rem; padding: .62rem .72rem; border: 1px solid var(--warn-border, var(--neutral-border)); border-radius: var(--r-md); background: var(--warn-soft, var(--sunken)); color: var(--text-2); }
  .indicator { width: .52rem; height: .52rem; border-radius: 50%; background: var(--warn, #d58b19); box-shadow: 0 0 0 .2rem color-mix(in srgb, var(--warn, #d58b19) 16%, transparent); }
  .copy { min-width: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: .2rem .5rem; font-size: .74rem; }
  .copy strong { color: var(--text-1); }
  .draft { color: var(--text-3); }
  button { border: 1px solid var(--accent-border); border-radius: var(--r-pill); padding: .3rem .62rem; background: var(--surface); color: var(--text-1); font: inherit; font-size: .72rem; font-weight: 750; cursor: pointer; }
  @media (max-width: 639px) { .readiness-strip { grid-template-columns: auto 1fr; } button { grid-column: 2; justify-self: start; } }
</style>
