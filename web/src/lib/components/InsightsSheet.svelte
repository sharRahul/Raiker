<script lang="ts">
  /**
   * TOOL-131 — `/insights`: what this conversation used and cost.
   *
   * A sheet over the composer, like the shortcuts sheet: read-only, built from
   * the turns on screen and the conversation's usage ledger. It changes nothing.
   */
  import type { ThreadInsights } from "../threadInsights";
  import Icon from "./Icon.svelte";

  let { insights, onclose }: { insights: ThreadInsights; onclose: () => void } = $props();
  const tokens = (value: number | null) => (value === null ? "Not reported" : value.toLocaleString());
</script>

<div class="sheet" role="region" aria-label="Conversation insights" data-testid="insights-sheet">
  <div class="sheet-head">
    <strong>This conversation</strong>
    <button type="button" class="sheet-close" aria-label="Close insights" onclick={onclose}>
      <Icon name="x" size="sm" />
    </button>
  </div>
  <dl>
    <div>
      <dt>Turns</dt>
      <dd>{insights.turns}{#if insights.modelCalls !== null && insights.modelCalls !== insights.turns}{` · ${insights.modelCalls} model calls`}{/if}</dd>
    </div>
    <div><dt>Model</dt><dd>{insights.model ?? "Not reported"}</dd></div>
    <div><dt>Tokens in · out</dt><dd>{tokens(insights.inputTokens)} · {tokens(insights.outputTokens)}</dd></div>
    <div><dt>Cost</dt><dd>{insights.cost ?? "Not priced"}</dd></div>
    <div>
      <dt>Tool calls</dt>
      <dd>
        {insights.toolCalls}{#if insights.asked > 0}{` · ${insights.asked} asked you`}{/if}{#if insights.notDone > 0}{` · ${insights.notDone} not done`}{/if}
      </dd>
    </div>
  </dl>
  {#if insights.topTools.length > 0}
    <p class="tools">
      Most used:
      {#each insights.topTools as tool, index (tool.label)}{index > 0 ? ", " : ""}{tool.label} ×{tool.count}{/each}
    </p>
  {/if}
</div>

<style>
  .sheet{margin:0 0 .45rem;border:1px solid var(--border);border-radius:var(--r-md);background:var(--surface);overflow:hidden}
  .sheet-head{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.4rem .6rem;border-bottom:1px solid var(--border);font-size:var(--text-sm)}
  .sheet-close{border:0;background:transparent;color:var(--text-3);cursor:pointer;padding:.1rem;line-height:0}
  .sheet-close:hover{color:var(--text-1)}
  dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.3rem 1rem;margin:0;padding:.5rem .6rem}
  dl div{display:grid;gap:.05rem}
  dt{font-size:var(--text-xs);color:var(--text-3)}
  dd{margin:0;font-size:var(--text-sm);color:var(--text-1);font-variant-numeric:tabular-nums}
  .tools{margin:0;padding:0 .6rem .5rem;font-size:var(--text-xs);color:var(--text-2)}
</style>
