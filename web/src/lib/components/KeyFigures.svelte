<script lang="ts">
  /**
   * QUI-A04 — up to four headline numbers, each with its unit, label and what
   * it is of.
   *
   * The runtime has already refused a figure with no unit and turned a block
   * with no source into text, so everything drawn here has both. A guess says
   * "≈ estimate" in words beside its number, never only in a lighter colour.
   * A description list, so a screen reader reads each label with its value.
   */
  import { PREFIX_UNITS, displayFigure, type Figure } from "../answerBlocks";

  let {
    caption = "",
    items,
    source = "",
    estimate = false,
  }: { caption?: string; items: Figure[]; source?: string; estimate?: boolean } = $props();
</script>

<figure class="key-figures">
  {#if caption}<figcaption>{caption}</figcaption>{/if}
  <dl class="tiles" style={`--count: ${items.length}`}>
    {#each items as item, index (index)}
      <div class="tile">
        <dt>{item.label}</dt>
        <dd>
          {#if PREFIX_UNITS.has(item.unit)}
            <span class="value">{displayFigure(item.value, item.unit)}</span>
          {:else}
            <span class="value">{displayFigure(item.value)}</span>
            <span class="unit">{item.unit}</span>
          {/if}
        </dd>
        {#if item.of}<dd class="of">{item.of}</dd>{/if}
        {#if item.estimate || estimate}<dd class="estimate">≈ estimate</dd>{/if}
      </div>
    {/each}
  </dl>
  {#if source}<p class="source">Source: {source}</p>{/if}
</figure>

<style>
  .key-figures { margin: 0; }
  figcaption { font-weight: 650; color: var(--text-1); margin-bottom: var(--space-2); }
  .tiles {
    display: grid;
    grid-template-columns: repeat(var(--count), minmax(0, 1fr));
    gap: var(--space-2);
    margin: 0;
  }
  .tile {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--bg);
    min-width: 0;
  }
  dt { color: var(--text-2); font-size: var(--text-sm); }
  dd { margin: 0; }
  .value { font-size: var(--text-2xl); font-weight: 650; color: var(--text-1); font-variant-numeric: tabular-nums; }
  .unit { color: var(--text-2); margin-inline-start: 0.2rem; }
  .of { color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .estimate { color: var(--text-3); font-size: var(--text-xs); }
  .source { margin: var(--space-2) 0 0; color: var(--text-3); font-size: var(--text-xs); }
</style>
