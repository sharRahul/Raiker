<script lang="ts">
  /**
   * QUI-A05 — items as columns, criteria as rows, the best value per row
   * marked "Best" in words.
   *
   * The runtime computed `best` from the row's stated rule (higher or lower is
   * better); the model only sent the values, so it never chose the winner. A
   * row with no rule, or where every item ties, has no mark at all. "Best" is a
   * word in the cell as well as a tint, because a tint alone is not a channel
   * everyone has.
   */
  import Icon from "./Icon.svelte";
  import { figure, type CompareRow } from "../answerBlocks";

  let {
    caption = "",
    items,
    rows,
    source = "",
    estimate = false,
  }: {
    caption?: string;
    items: string[];
    rows: CompareRow[];
    source?: string;
    estimate?: boolean;
  } = $props();

  function rule(row: CompareRow): string {
    if (row.better === "higher") return "higher is better";
    if (row.better === "lower") return "lower is better";
    return "";
  }
</script>

<div class="comparison">
  <table>
    {#if caption}<caption>{caption}{#if estimate}<span class="estimate"> · ≈ estimate</span>{/if}</caption>{/if}
    <thead>
      <tr>
        <td></td>
        {#each items as item, index (index)}<th scope="col">{item}</th>{/each}
      </tr>
    </thead>
    <tbody>
      {#each rows as row, r (r)}
        <tr>
          <th scope="row">
            {row.label}{#if row.unit}<span class="unit"> ({row.unit})</span>{/if}
            {#if rule(row)}<span class="rule">{rule(row)}</span>{/if}
          </th>
          {#each row.values as value, index (index)}
            <td class:best={row.best.includes(index)}>
              {typeof value === "number" ? figure(value) : value}
              {#if row.best.includes(index)}
                <span class="best-mark"><Icon name="check" size="sm" />Best</span>
              {/if}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
  {#if source}<p class="source">Source: {source}</p>{/if}
</div>

<style>
  .comparison { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
  caption { text-align: start; font-weight: 650; color: var(--text-1); margin-bottom: var(--space-2); font-size: var(--text-md); }
  th, td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border); text-align: start; vertical-align: top; }
  thead th { color: var(--text-1); font-weight: 650; }
  tbody th { font-weight: 600; color: var(--text-1); }
  td { font-variant-numeric: tabular-nums; color: var(--text-1); }
  .unit, .rule { color: var(--text-3); font-weight: 400; }
  .rule { display: block; font-size: var(--text-xs); }
  td.best { background: var(--ok-soft); }
  .best-mark {
    display: inline-flex;
    align-items: center;
    gap: 0.15rem;
    margin-inline-start: 0.35rem;
    color: var(--ok);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .estimate { color: var(--text-3); font-weight: 400; font-size: var(--text-xs); }
  .source { margin: var(--space-2) 0 0; color: var(--text-3); font-size: var(--text-xs); }
</style>
