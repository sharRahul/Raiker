<script lang="ts">
  /**
   * QUI-F16 — the task receipt: one expandable line at the end of a turn.
   *
   * Model · approximate cost · what was read · what changed or was sent, with
   * the approval time · what left this computer. Read from the receipt the
   * runtime builds from the turn's audit events, so it makes the governed
   * promise visible on every task without a word of it coming from the model.
   * A receipt that cannot be read is simply not shown: the outcome line and the
   * evidence below still say how the turn ended.
   */
  import { api } from "../api";
  import type { TurnReceipt } from "../generated/apiContract";
  import { receiptLine, receiptRows } from "../turnReceipt";

  let { sessionId, turnId }: { sessionId: string; turnId: string } = $props();

  let receipt = $state<TurnReceipt | null>(null);
  $effect(() => {
    let cancelled = false;
    void api
      .turnReceipt(sessionId, turnId)
      .then((value) => {
        if (!cancelled) receipt = value;
      })
      .catch(() => {
        if (!cancelled) receipt = null;
      });
    return () => {
      cancelled = true;
    };
  });
</script>

{#if receipt !== null}
  <details class="receipt" data-testid="turn-receipt">
    <summary><span class="sr-only">Receipt: </span>{receiptLine(receipt)}</summary>
    <dl>
      {#each receiptRows(receipt) as row (row.label)}
        <dt>{row.label}</dt>
        <dd>{row.value}</dd>
      {/each}
    </dl>
  </details>
{/if}

<style>
  .receipt{margin:var(--space-1) 0 0;font-size:var(--text-xs);color:var(--text-3)}
  .receipt summary{cursor:pointer;list-style:none;width:fit-content;max-width:100%}
  .receipt summary::-webkit-details-marker{display:none}
  .receipt summary::before{content:"▸";display:inline-block;margin-inline-end:.35rem;transition:transform var(--motion-fast) var(--ease)}
  .receipt[open] summary::before{transform:rotate(90deg)}
  .receipt summary:hover{color:var(--text-2)}
  dl{display:grid;grid-template-columns:max-content 1fr;gap:.2rem var(--space-3);margin:var(--space-2) 0 0;padding:var(--space-2) var(--space-3);border:1px solid var(--border);border-radius:var(--r-sm);background:var(--sunken)}
  dt{font-weight:600;color:var(--text-2)}
  dd{margin:0;color:var(--text-2)}
</style>
