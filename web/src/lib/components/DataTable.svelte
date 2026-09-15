<script lang="ts">
  /**
   * A table a turn declared, rendered as a table.
   *
   * BUG-288. The renderer could already draw a GFM table, and that is a
   * different thing: it is characters that happened to parse. Nothing knew the
   * result *was* a table, so nothing could sort it, announce it as one, or say
   * how many rows it had. This gets the validated payload — rectangular by
   * construction, because the runtime refuses a row that is not the width of
   * the header rather than padding it — so all three are possible.
   *
   * Sorting is client-side and stable, and the original order is a state the
   * owner can get back to: a table they have sorted three ways and cannot
   * un-sort is a table they have lost the answer in.
   */
  import Icon from "./Icon.svelte";

  let {
    caption = "",
    columns,
    rows,
  }: { caption?: string; columns: string[]; rows: string[][] } = $props();

  /** `null` is the order the turn sent, which is itself an answer. */
  let sortBy = $state<number | null>(null);
  let ascending = $state(true);

  /**
   * Numeric where every cell in the column is a number, textual otherwise.
   *
   * Decided per column rather than per comparison, so one stray label cannot
   * make a column of numbers sort as strings for some pairs and not others.
   */
  const numericColumns = $derived(
    columns.map((_, index) =>
      rows.length > 0 &&
      rows.every((row) => row[index].trim() !== "" && !Number.isNaN(Number(row[index].replace(/[$,%\s]/g, "")))),
    ),
  );

  const sorted = $derived.by(() => {
    if (sortBy === null) return rows;
    const index = sortBy;
    const numeric = numericColumns[index];
    const direction = ascending ? 1 : -1;
    // A copy, and an index tie-break, so the sort is stable and the source
    // array the turn sent is never mutated.
    return rows
      .map((row, position) => ({ row, position }))
      .sort((a, b) => {
        const left = a.row[index];
        const right = b.row[index];
        const result = numeric
          ? Number(left.replace(/[$,%\s]/g, "")) - Number(right.replace(/[$,%\s]/g, ""))
          : left.localeCompare(right);
        return result !== 0 ? result * direction : a.position - b.position;
      })
      .map((entry) => entry.row);
  });

  function toggle(index: number) {
    if (sortBy === index) {
      if (ascending) ascending = false;
      else {
        // Third press returns the turn's own order rather than cycling forever.
        sortBy = null;
        ascending = true;
      }
      return;
    }
    sortBy = index;
    ascending = true;
  }

  function ariaSort(index: number): "ascending" | "descending" | "none" {
    if (sortBy !== index) return "none";
    return ascending ? "ascending" : "descending";
  }
</script>

<div class="data-table">
  <table>
    <caption>
      {caption || "Table"}
      <span class="count">{rows.length} row{rows.length === 1 ? "" : "s"}</span>
      {#if sortBy !== null}
        <span class="count">sorted by {columns[sortBy]}, {ascending ? "ascending" : "descending"}</span>
      {/if}
    </caption>
    <thead>
      <tr>
        {#each columns as column, index (index)}
          <th scope="col" aria-sort={ariaSort(index)} class:numeric={numericColumns[index]}>
            <button type="button" onclick={() => toggle(index)}>
              <span>{column}</span>
              <span class="arrow" aria-hidden="true">
                {#if sortBy === index}
                  <Icon name={ascending ? "chevron-up" : "chevron-down"} size="sm" />
                {/if}
              </span>
            </button>
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each sorted as row, rowIndex (rowIndex)}
        <tr>
          {#each row as cell, cellIndex (cellIndex)}
            <td class:numeric={numericColumns[cellIndex]}>{cell}</td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  /* Its own scroll container, so a wide table never widens the transcript. */
  .data-table {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    margin: var(--space-3) 0;
    background: var(--surface);
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: var(--text-sm);
  }
  caption {
    caption-side: top;
    text-align: left;
    padding: var(--space-2) var(--space-3);
    font-weight: 650;
    color: var(--text-1);
    border-bottom: 1px solid var(--border);
  }
  .count {
    font-weight: 400;
    color: var(--text-3);
    font-size: var(--text-xs);
    margin-inline-start: var(--space-2);
  }
  th {
    text-align: left;
    padding: 0;
    border-bottom: 1px solid var(--border);
    background: var(--sunken);
    white-space: nowrap;
  }
  th button {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    font: inherit;
    font-weight: 650;
    color: var(--text-2);
    background: transparent;
    border: 0;
    cursor: pointer;
    text-align: inherit;
  }
  th button:hover {
    color: var(--accent);
  }
  th button:focus-visible {
    outline: 3px solid var(--focus-ring);
    outline-offset: -3px;
  }
  th.numeric button {
    justify-content: flex-end;
  }
  .arrow {
    display: inline-grid;
    place-items: center;
    width: 1rem;
    color: var(--accent);
  }
  td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--border);
    color: var(--text-1);
    vertical-align: top;
  }
  td.numeric {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  tbody tr:last-child td {
    border-bottom: 0;
  }
</style>
