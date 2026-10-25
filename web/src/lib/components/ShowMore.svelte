<script lang="ts">
  /**
   * QUI-L12 — a Work list shows 50 rows, then says how many more there are.
   *
   * Long lists never become long pages: the owner sees the first page and the
   * count of what is left, and asks for the next page when they want it.
   */
  import { PAGE_SIZE } from "../pagination";

  let { total, shown, noun = "items", onmore }: { total: number; shown: number; noun?: string; onmore: () => void } = $props();
  const next = $derived(Math.min(PAGE_SIZE, total - shown));
</script>

{#if total > shown}
  <div class="show-more">
    <span class="count">Showing {shown} of {total} {noun}</span>
    <button type="button" class="btn btn-ghost btn-sm" onclick={onmore}>Show {next} more</button>
  </div>
{/if}

<style>
  .show-more {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) 0;
  }
  .count {
    color: var(--text-3);
    font-size: var(--text-sm);
    font-variant-numeric: tabular-nums;
  }
</style>
