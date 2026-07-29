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
  const exactPercent = $derived(effectiveUsed !== null && effectiveUsed !== undefined && effectiveWindow ? Math.min(100, Math.max(0, (effectiveUsed / effectiveWindow) * 100)) : null);
  const percentLabel = $derived(exactPercent === null ? null : exactPercent > 0 && exactPercent < 0.01 ? "<0.01%" : `${exactPercent.toFixed(2).replace(/\.00$/, "")}%`);
  const remaining = $derived(effectiveUsed !== null && effectiveUsed !== undefined && effectiveWindow ? Math.max(0, effectiveWindow - effectiveUsed) : null);
  const number = $derived(new Intl.NumberFormat(locale));

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
  <div class="context-heading"><strong>Context window</strong>{#if percentLabel}<span>{percentLabel}</span>{/if}</div>
  {#if display}
    <div class="usage-figure"><strong>{number.format(effectiveUsed ?? 0)} tokens used</strong><span>of {number.format(effectiveWindow ?? 0)} available</span></div>
    <div class="meter {exactPercent !== null && exactPercent >= 90 ? 'critical' : exactPercent !== null && exactPercent >= 75 ? 'warning' : ''}" role="progressbar" aria-label="Context used" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(exactPercent ?? 0)}>
      <span style={`width: ${exactPercent ?? 0}%`}></span>
    </div>
    <div class="remaining"><span>{number.format(remaining ?? 0)} tokens remaining</span><span>{number.format(usage?.session_input_tokens ?? 0)} input · {number.format(usage?.session_output_tokens ?? 0)} output</span></div>
    <p class="reported">{#if isEstimate}Estimated from this chat{:else}Reported by {usage?.provider ?? "provider"}{/if}<span class="info" title={`Usage is ${isEstimate ? "estimated from visible chat text" : "reported by the selected provider"}. Context capacity is ${capacityNote ?? "configured by Raiker"}.`} aria-label="About context usage sources">i</span></p>
  {:else}
    <p>Context capacity is not configured for this model.</p>
  {/if}

  {#if usage?.billable}
    <div class="cost" aria-label="API pricing and cost">
      {#if sessionCost}
        <div class="cost-row"><span>This chat</span><strong>{sessionCost}</strong></div>
        {#if providerCost}
          <div class="cost-row dim"><span>{providerLabel}</span><strong>{providerCost}</strong></div>
        {/if}
        {#if priceNote}<p class="price-note">{usage.model ? `${usage.model} — ` : ""}{priceNote}</p>{/if}
      {:else if priceMissing}
        <p class="price-note">
          No price is configured for {usage.model ?? "this model"}, so its cost cannot be shown.
          <a class="configure" href="#/models">Configure →</a>
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
  .context-popover { position: absolute; right: 0; bottom: calc(100% + .55rem); width: min(35rem, calc(100vw - 2rem)); padding: 1.35rem 1.5rem; border: 1px solid var(--neutral-border); border-radius: .75rem; background: var(--surface); box-shadow: 0 14px 40px color-mix(in srgb, #17262c 15%, transparent); z-index: 5; }
  .context-heading { display:flex; justify-content:space-between; gap:1rem; color:var(--text-1); } .context-heading span { color:var(--text-2); font-size:.82rem; font-weight:650; }
  .usage-figure { display:grid; gap:.15rem; margin-top:1rem; } .usage-figure strong { font-size:1.2rem; color:var(--text-1); } .usage-figure span { color:var(--text-3); font-size:.82rem; }
  p { color:var(--text-3); margin:.75rem 0 0; font-size:.8rem; }
  .meter { height:.5rem; overflow:hidden; margin-top:.75rem; border-radius:999px; background:var(--neutral-soft); }
  .meter span { display:block; height:100%; min-width:2px; border-radius:inherit; background:var(--raiker-teal, #268d91); }
  .meter.warning span { background:var(--warning); } .meter.critical span { background:var(--danger); }
  .remaining { display:flex; justify-content:space-between; flex-wrap:wrap; gap:.5rem; margin-top:.7rem; color:var(--text-2); font-size:.76rem; }
  .reported { display:flex; align-items:center; gap:.4rem; } .info { width:1rem; height:1rem; display:inline-grid; place-items:center; border:1px solid var(--border-strong); border-radius:50%; font-size:.65rem; color:var(--text-2); cursor:help; }
  .cost { margin:1.2rem -1.5rem -1.35rem; padding:.9rem 1.5rem; border-top:1px solid var(--border); border-radius:0 0 .75rem .75rem; background:var(--sunken); }
  .cost-row { display:flex; justify-content:space-between; gap:1rem; font-size:.84rem; color:var(--text-1); }
  .cost-row + .cost-row { margin-top:.25rem; }
  .cost-row.dim, .dim { color:var(--text-3); }
  .price-note { margin:.4rem 0 0; font-size:.74rem; color:var(--text-3); }
  .price-note a,.configure { color:var(--accent); font-weight:650; }
</style>
