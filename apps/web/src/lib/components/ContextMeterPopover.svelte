<script lang="ts">
  import { formatContextUsage, formatCost, sourceNote } from "../contextPresentation";
  import type { ContextUsage } from "../apiTypes";

  /**
   * Read-only context and spend for the active conversation.
   *
   * Two independent facts live here and are sourced independently: how full the
   * context window is, and what the conversation has cost. Either can be
   * unavailable without hiding the other, and neither is ever guessed — an
   * absent figure is stated as absent, because a fabricated "$0.00" or a
   * fabricated capacity is worse than an honest gap.
   */
  let {
    usedTokens = null,
    contextWindowTokens = null,
    estimated = false,
    usage = null,
    locale = undefined,
  }: {
    usedTokens?: number | null;
    contextWindowTokens?: number | null;
    estimated?: boolean;
    usage?: ContextUsage | null;
    locale?: string | undefined;
  } = $props();

  // Provider-reported prompt tokens beat the browser's transcript estimate; the
  // estimate stays as the pre-first-turn fallback and is labelled as such.
  const effectiveUsed = $derived(
    usage?.usage_source === "provider" && usage.used_tokens !== null
      ? usage.used_tokens
      : usedTokens,
  );
  const effectiveWindow = $derived(usage?.context_window_tokens ?? contextWindowTokens);
  const isEstimate = $derived(usage?.usage_source === "provider" ? false : estimated);

  const display = $derived(
    effectiveUsed !== null && effectiveUsed !== undefined && effectiveWindow
      ? formatContextUsage(effectiveUsed, effectiveWindow)
      : null,
  );
  const capacityNote = $derived(sourceNote(usage?.context_window_source));

  // Cost only ever applies to a provider Raiker authenticates with an API key.
  const sessionCost = $derived(
    usage?.billable ? formatCost(usage.session_cost, usage.currency, locale) : null,
  );
  const providerCost = $derived(
    usage?.billable ? formatCost(usage.provider_total_cost, usage.currency, locale) : null,
  );
  const priceNote = $derived(sourceNote(usage?.price_source, usage?.price_as_of));
  // A billable provider that has run turns but resolves no price is the one
  // case worth an explicit call to action rather than silence.
  const priceMissing = $derived(
    (usage?.billable ?? false) && usage !== null && usage.session_turns > 0 && sessionCost === null,
  );
  const providerLabel = $derived(usage?.provider ? `${usage.provider}, all time` : "All time");
</script>

<section class="context-popover" aria-label="Context window and cost details">
  <div class="context-heading"><strong>Context window</strong>{#if display}<span>{display.label}</span>{/if}</div>
  {#if display}
    <div class="meter" role="progressbar" aria-label="Context used" aria-valuemin="0" aria-valuemax="100" aria-valuenow={display.percent}>
      <span style={`width: ${display.percent}%`}></span>
    </div>
    <p>
      {#if isEstimate}Estimated from this chat’s text.{:else}Provider-reported usage.{/if}
      {#if capacityNote}<span class="dim">Capacity {capacityNote}.</span>{/if}
    </p>
  {:else}
    <p>Context capacity is not configured for this model.</p>
  {/if}

  {#if usage?.billable}
    <div class="cost" aria-label="API cost">
      {#if sessionCost}
        <div class="cost-row"><span>This chat</span><strong>{sessionCost}</strong></div>
        {#if providerCost}
          <div class="cost-row dim"><span>{providerLabel}</span><strong>{providerCost}</strong></div>
        {/if}
        {#if priceNote}<p class="price-note">{usage.model ? `${usage.model} — ` : ""}{priceNote}</p>{/if}
      {:else if priceMissing}
        <p class="price-note">
          No price is configured for {usage.model ?? "this model"}, so its cost cannot be shown.
          <a href="#/models">Set one in Models</a>
        </p>
      {:else}
        <p class="price-note">No billable usage recorded for this chat yet.</p>
      {/if}
    </div>
  {:else if usage}
    <div class="cost"><p class="price-note">Runs on this machine — no API cost.</p></div>
  {/if}
</section>

<style>
  .context-popover { position: absolute; right: 0; bottom: calc(100% + .55rem); width: min(32rem, calc(100vw - 2rem)); padding: .9rem 1rem; border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-lg); z-index: 5; }
  .context-heading { display:flex; justify-content:space-between; gap:1rem; color:var(--text-1); }
  p { color:var(--text-3); margin:.55rem 0 0; font-size:.8rem; }
  .meter { height:.36rem; overflow:hidden; margin-top:.55rem; border-radius:999px; background:var(--neutral-soft); }
  .meter span { display:block; height:100%; min-width:2px; border-radius:inherit; background:var(--raiker-teal, #268d91); }
  .cost { margin-top:.7rem; padding-top:.7rem; border-top:1px solid var(--border); }
  .cost-row { display:flex; justify-content:space-between; gap:1rem; font-size:.84rem; color:var(--text-1); }
  .cost-row + .cost-row { margin-top:.25rem; }
  .cost-row.dim, .dim { color:var(--text-3); }
  .price-note { margin:.4rem 0 0; font-size:.74rem; color:var(--text-3); }
  .price-note a { color:var(--accent); }
</style>
