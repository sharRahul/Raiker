<script lang="ts">
  /**
   * QUI-F16 for a task — the receipt of everything its own conversation did.
   *
   * A routine runs many turns; this adds up their receipts on the server (the
   * same per-turn records Chat's receipt reads). Read only when the owner opens
   * it, so a long Tasks list does not ask for every receipt at once.
   */
  import { contract } from "../generated/apiContract";
  import type { TaskReceipt } from "../generated/apiContract";
  import { taskReceiptLine, taskReceiptRows } from "../turnReceipt";

  let { taskId }: { taskId: string } = $props();

  let receipt = $state<TaskReceipt | null>(null);
  let failed = $state(false);
  // Drawn only once opened: a closed receipt holds no "Reading…" line that a
  // reader (or a page-settled check) could take for a page still loading.
  let opened = $state(false);

  async function read(event: Event) {
    opened = (event.currentTarget as HTMLDetailsElement).open;
    if (!opened || receipt !== null) return;
    failed = false;
    try {
      receipt = await contract.getTaskReceipt(taskId);
    } catch {
      failed = true;
    }
  }
</script>

<details class="receipt" ontoggle={read} data-testid="task-receipt">
  <summary>Receipt</summary>
  {#if !opened}
    <!-- Nothing until asked for. -->
  {:else if receipt !== null}
    <p class="line">{taskReceiptLine(receipt)}</p>
    <dl>
      {#each taskReceiptRows(receipt) as row (row.label)}
        <dt>{row.label}</dt>
        <dd>{row.value}</dd>
      {/each}
    </dl>
  {:else if failed}
    <p class="line">The receipt could not be read. The task's history still shows each run.</p>
  {:else}
    <p class="line">Reading this task's records…</p>
  {/if}
</details>

<style>
  .receipt{margin:var(--space-2) 0 0;font-size:var(--text-xs);color:var(--text-3)}
  .receipt summary{cursor:pointer;list-style:none;width:fit-content}
  .receipt summary::-webkit-details-marker{display:none}
  .receipt summary::before{content:"▸";display:inline-block;margin-inline-end:.35rem;transition:transform var(--motion-fast) var(--ease)}
  .receipt[open] summary::before{transform:rotate(90deg)}
  .receipt summary:hover{color:var(--text-2)}
  .line{margin:var(--space-1) 0 0;color:var(--text-2)}
  dl{display:grid;grid-template-columns:max-content 1fr;gap:.2rem var(--space-3);margin:var(--space-2) 0 0;padding:var(--space-2) var(--space-3);border:1px solid var(--border);border-radius:var(--r-sm);background:var(--sunken)}
  dt{font-weight:600;color:var(--text-2)}
  dd{margin:0;color:var(--text-2)}
</style>
