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
  const capacityNote = $derived(
    usage?.context_window_source === "provider"
      ? "reported by runtime"
      : usage?.context_window_source === "owner"
        ? "set by owner"
      : usage?.context_window_source === "config"
        ? "configured in Raiker"
        : null,
  );
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
  // BUG-21 — a billable provider with no exact rate in the registry says
  // **Unknown** and offers a way to fix it. The server decides this
  // (`price_unknown`), so the popover never has to infer a missing price from
  // an absent cost; the old `session_turns > 0` condition stayed silent before
  // the first turn, which read as "free" rather than "not yet known".
  const priceMissing = $derived(
    usage?.price_unknown ??
      ((usage?.billable ?? false) && usage !== null && usage.session_turns > 0 && sessionCost === null),
  );
  // The individual components behind the figure, exactly as the registry holds
  // them. A cache rate the provider never published stays absent rather than
  // being shown as equal to the input rate.
  const rateRows = $derived(
    [
      ["Input", usage?.price_input_per_mtok],
      ["Output", usage?.price_output_per_mtok],
      ["Cache write", usage?.price_cache_write_per_mtok],
      ["Cache read", usage?.price_cache_read_per_mtok],
    ].filter((row): row is [string, string] => typeof row[1] === "string" && row[1] !== ""),
  );
  const providerLabel = $derived(usage?.provider ? `${usage.provider}, all time` : "All time");
  // Backlog #16 — how much of the tool catalogue a turn carries. Absent on an
  // older server, which renders nothing rather than "0 deferred".
  const toolsProjected = $derived(usage?.tools_projected ?? 0);
  const toolsDeferred = $derived(usage?.tools_deferred ?? 0);
</script>

<section class="context-popover" aria-label="Context window and cost details">
  <div class="context-heading"><strong>Context window</strong>{#if percentLabel}<span>{percentLabel}</span>{/if}</div>
  {#if display}
    <div class="usage-figure"><strong>{number.format(effectiveUsed ?? 0)} tokens used</strong><span>of {number.format(effectiveWindow ?? 0)} available</span></div>
    <!-- BUG-37 — the shared meter primitive rather than this component's own
         bar. It is a proportion of a fixed capacity, which is exactly what a
         meter means, and its tones now come from the same tokens the badge
         beside it uses instead of a private `--raiker-teal` fallback. -->
    <div
      class="meter {exactPercent !== null && exactPercent >= 90 ? 'tone-danger' : exactPercent !== null && exactPercent >= 75 ? 'tone-warn' : ''}"
      style={`--meter-value: ${exactPercent ?? 0}`}
      role="progressbar"
      aria-label="Context used"
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={Math.round(exactPercent ?? 0)}
    >
      <span class="meter-fill" data-value={Math.round(exactPercent ?? 0)}></span>
    </div>
    <div class="remaining"><span>{number.format(remaining ?? 0)} tokens remaining</span><span>{number.format(usage?.session_input_tokens ?? 0)} input · {number.format(usage?.session_output_tokens ?? 0)} output</span></div>
    <p class="reported">
      {#if isEstimate}
        Estimated from this chat
      {:else}
        Reported by {usage?.provider ?? "provider"}
      {/if}
      {#if capacityNote}<span class="capacity-source">· Capacity {capacityNote}</span>{/if}
      <span class="info" title={`Usage is ${isEstimate ? "estimated from visible chat text" : "reported by the selected provider"}. Context capacity is ${capacityNote ?? "configured by Raiker"}.`} aria-label="About context usage sources">i</span>
    </p>
  {:else}
    <p>Context capacity is not configured for this model.</p>
  {/if}
  <!-- Backlog #16 — a turn carries the core tool schemas and fetches the rest
       on request. Stated because a tool missing from a request is not a tool
       withheld, and an owner reading a context figure should be able to see
       where part of it went. One line: the counts are the whole story. -->
  {#if toolsDeferred > 0}
    <p class="tool-budget">
      {toolsProjected} tool schemas sent · {toolsDeferred} fetched on request
      <span
        class="info"
        title="Raiker sends the tools a turn usually needs and lets the model ask for any of the others by name. Nothing is withheld: a fetched tool passes the same permission, policy and approval checks."
        aria-label="About deferred tool schemas">i</span
      >
    </p>
  {/if}

  {#if usage?.latest_compaction}
    <div
      class="compaction {usage.latest_compaction.status}"
      aria-label="Automatic context compaction status"
    >
      {#if usage.latest_compaction.status === "completed"}
        <strong>Earlier context compacted</strong>
        <span>
          {number.format(usage.latest_compaction.estimated_input_tokens_before)} â†’
          {number.format(usage.latest_compaction.estimated_summary_tokens)} tokens
        </span>
        <p>Chat transcript is unchanged; only the context sent to the model was summarised.</p>
      {:else}
        <strong>Recent history retained</strong>
        <span>Compaction was unavailable, so this turn continued with bounded recent context.</span>
      {/if}
    </div>
  {/if}

  {#if usage?.billable}
    <div class="cost" aria-label="API pricing and cost">
      {#if priceMissing}
        <!-- Stated, not implied. A billable model with no exact rate reads
             "Unknown", never "$0.00", and the fix is one click away. -->
        <div class="cost-row"><span>This chat</span><strong>Unknown</strong></div>
        <p class="price-note">
          No rate is recorded for <strong>{usage.model ?? "this model"}</strong> in the price
          registry, so its cost cannot be shown.
          <a class="configure" href="#/models?tab=pricing">Configure →</a>
        </p>
      {:else if sessionCost}
        <div class="cost-row"><span>This chat</span><strong>{sessionCost}</strong></div>
        {#if providerCost}
          <div class="cost-row dim"><span>{providerLabel}</span><strong>{providerCost}</strong></div>
        {/if}
        {#if rateRows.length > 0}
          <dl class="rates" aria-label="Rate components, per million tokens">
            {#each rateRows as [label, rate] (label)}
              <div><dt>{label}</dt><dd>{rate}</dd></div>
            {/each}
          </dl>
        {/if}
        {#if priceNote}
          <p class="price-note">
            {usage.model ? `${usage.model} — ` : ""}{priceNote}{#if usage.price_effective_from}
              · effective {usage.price_effective_from.slice(0, 10)}{/if}
          </p>
        {/if}
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
  /* Geometry and tone now come from the shared `.meter` primitive in app.css;
     this only places it. */
  .meter { margin-top:.75rem; }
  .remaining { display:flex; justify-content:space-between; flex-wrap:wrap; gap:.5rem; margin-top:.7rem; color:var(--text-2); font-size:.76rem; }
  .tool-budget { display:flex; align-items:center; flex-wrap:wrap; gap:.3rem; margin:.35rem 0 0; color:var(--text-3); font-size:.72rem; }
  .reported { display:flex; align-items:center; flex-wrap:wrap; gap:.3rem; } .capacity-source { color:var(--text-2); } .info { width:1rem; height:1rem; display:inline-grid; place-items:center; border:1px solid var(--border-strong); border-radius:50%; font-size:.65rem; color:var(--text-2); cursor:help; }
  .compaction { display:grid; grid-template-columns:1fr auto; gap:.2rem .9rem; margin-top:1rem; padding:.75rem .85rem; border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:.5rem; background:var(--sunken); }
  .compaction strong { color:var(--text-1); font-size:.8rem; }
  .compaction > span { color:var(--text-2); font-size:.74rem; font-variant-numeric:tabular-nums; }
  .compaction p { grid-column:1 / -1; margin:.05rem 0 0; font-size:.72rem; }
  .compaction.failed { border-left-color:var(--warning, #a86b17); }
  .compaction.failed > span { grid-column:1 / -1; }
  .cost { margin:1.2rem -1.5rem -1.35rem; padding:.9rem 1.5rem; border-top:1px solid var(--border); border-radius:0 0 .75rem .75rem; background:var(--sunken); }
  .cost-row { display:flex; justify-content:space-between; gap:1rem; font-size:.84rem; color:var(--text-1); }
  .cost-row + .cost-row { margin-top:.25rem; }
  .cost-row.dim, .dim { color:var(--text-3); }
  .price-note { margin:.4rem 0 0; font-size:.74rem; color:var(--text-3); }
  /* Each rate component on its own row: input, output, and the cache rates a
     provider bills separately. Absent ones are simply not listed. */
  .rates { display:grid; gap:.15rem; margin:.5rem 0 0; }
  .rates div { display:flex; justify-content:space-between; gap:1rem; font-size:.74rem; }
  .rates dt { color:var(--text-3); margin:0; }
  .rates dd { color:var(--text-2); margin:0; font-variant-numeric:tabular-nums; }
  .price-note a,.configure { color:var(--accent); font-weight:650; }
</style>
