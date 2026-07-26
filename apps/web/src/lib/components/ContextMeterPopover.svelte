<script lang="ts">
  import { formatContextUsage } from "../contextPresentation";

  let {
    usedTokens = null,
    contextWindowTokens = null,
    estimated = false,
  }: { usedTokens?: number | null; contextWindowTokens?: number | null; estimated?: boolean } = $props();

  const display = $derived(
    usedTokens !== null && contextWindowTokens !== null
      ? formatContextUsage(usedTokens, contextWindowTokens)
      : null,
  );
</script>

<section class="context-popover" aria-label="Context window details">
  <div class="context-heading"><strong>Context window</strong>{#if display}<span>{display.label}</span>{/if}</div>
  {#if display}
    <div class="meter" role="progressbar" aria-label="Context used" aria-valuemin="0" aria-valuemax="100" aria-valuenow={display.percent}>
      <span style={`width: ${display.percent}%`}></span>
    </div>
    {#if estimated}<p>Estimated from this chat’s text.</p>{/if}
  {:else}
    <p>Context capacity is not configured for this model.</p>
  {/if}
</section>

<style>
  .context-popover { position: absolute; right: 0; bottom: calc(100% + .55rem); width: min(32rem, calc(100vw - 2rem)); padding: .9rem 1rem; border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-lg); z-index: 5; }
  .context-heading { display:flex; justify-content:space-between; gap:1rem; color:var(--text-1); }
  p { color:var(--text-3); margin:.55rem 0 0; font-size:.8rem; }
  .meter { height:.36rem; overflow:hidden; margin-top:.55rem; border-radius:999px; background:var(--neutral-soft); }
  .meter span { display:block; height:100%; min-width:2px; border-radius:inherit; background:var(--raiker-teal, #268d91); }
</style>
