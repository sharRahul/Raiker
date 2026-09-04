<script lang="ts">
  /**
   * The keyboard map for a composer (B19).
   *
   * Every binding a composer has, in one place, reachable with `/shortcuts`.
   * It documents the code rather than an intention: `shortcuts()` in
   * `composerCommands.ts` lists only bindings the handlers really implement, so
   * a row here that stops working is a failing test rather than a stale sheet.
   */
  import { shortcuts, type ComposerSurface } from "../composerCommands";
  import Icon from "./Icon.svelte";

  let { surface, onclose }: { surface: ComposerSurface; onclose: () => void } = $props();
  const rows = $derived(shortcuts(surface));
</script>

<div class="sheet" role="region" aria-label="Keyboard shortcuts">
  <div class="sheet-head">
    <strong>Keyboard shortcuts</strong>
    <button type="button" class="sheet-close" aria-label="Close shortcuts" onclick={onclose}>
      <Icon name="x" size="sm" />
    </button>
  </div>
  <dl>
    {#each rows as row (row.keys)}
      <div><dt><kbd>{row.keys}</kbd></dt><dd>{row.what}</dd></div>
    {/each}
  </dl>
</div>

<style>
  .sheet {
    margin: 0 0 0.45rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    overflow: hidden;
  }
  .sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.4rem 0.6rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.78rem;
  }
  .sheet-close {
    border: 0;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    padding: 0.1rem;
    line-height: 0;
  }
  .sheet-close:hover { color: var(--text-1); }
  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 0.3rem 1rem;
    margin: 0;
    padding: 0.5rem 0.6rem;
  }
  dl div { display: flex; align-items: baseline; gap: 0.5rem; min-width: 0; }
  dt { margin: 0; }
  dd { margin: 0; color: var(--text-2); font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; }
  kbd {
    display: inline-block;
    padding: 0.1rem 0.35rem;
    border: 1px solid var(--border);
    border-bottom-width: 2px;
    border-radius: var(--r-sm);
    background: var(--sunken);
    color: var(--text-2);
    font: 600 0.7rem var(--font-mono);
    white-space: nowrap;
  }
</style>
