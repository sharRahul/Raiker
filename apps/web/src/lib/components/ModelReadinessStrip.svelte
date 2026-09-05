<script lang="ts">
  import type { ModelReadinessView } from "../apiTypes";
  import { blocksSending, openModelSetup } from "../modelReadiness.svelte";

  let {
    readiness,
    draftPreserved = false,
  }: {
    readiness: ModelReadinessView | null;
    draftPreserved?: boolean;
  } = $props();

  // BUG-238 — a model whose observation aged out is set up; Raiker is
  // confirming it, and the turn runs either way. Saying "Set up model" there
  // asked the owner to redo work they had already done, and disabled Send while
  // they thought about it. A real failure still gets the full strip.
  // Aged out, or never looked at: either way the server takes the check before
  // it admits the turn, so this is a note rather than a job for the owner.
  const confirming = $derived(!blocksSending(readiness));
</script>

{#if readiness && !readiness.ready}
  {#if confirming}
    <p class="rechecking" role="status">Checking this model — you can still send.</p>
  {:else}
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
{/if}

<style>
  .rechecking { margin: 0; font-size: var(--text-xs); color: var(--text-3); }
  .readiness-strip { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: .65rem; padding: .62rem .72rem; border: 1px solid var(--warn-border, var(--neutral-border)); border-radius: var(--r-md); background: var(--warn-soft, var(--sunken)); color: var(--text-2); }
  .indicator { width: .52rem; height: .52rem; border-radius: 50%; background: var(--warn); box-shadow: 0 0 0 .2rem color-mix(in srgb, var(--warn) 16%, transparent); }
  .copy { min-width: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: .2rem .5rem; font-size: var(--text-xs); }
  .copy strong { color: var(--text-1); }
  .draft { color: var(--text-3); }
  button { border: 1px solid var(--accent-border); border-radius: var(--r-pill); padding: .3rem .62rem; background: var(--surface); color: var(--text-1); font: inherit; font-size: var(--text-xs); font-weight: 750; cursor: pointer; }
  @media (max-width: 63.9rem) {
    /* Revalidation does not block sending, so compact composers omit this
       informational line. A real failure keeps the full actionable strip. */
    .rechecking { display: none; }
    .readiness-strip { grid-template-columns: auto minmax(0, 1fr) auto; gap: .45rem; padding: .45rem .5rem; }
    .copy > span { display: none; }
    button { grid-column: auto; justify-self: end; white-space: nowrap; }
  }
</style>
