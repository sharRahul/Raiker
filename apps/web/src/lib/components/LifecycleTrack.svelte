<script lang="ts">
  /**
   * The four extension facts, shown as four independent steps.
   *
   * Installed, connected, enabled, and usable are separate truths. A single
   * "available" badge would let metadata alone imply an extension works, so
   * each step is rendered with its own met/unmet state and the first unmet one
   * is named as the blocker.
   */
  export interface LifecycleStep { label: string; met: boolean; note: string }

  let { steps, blockedReason = null }: { steps: LifecycleStep[]; blockedReason?: string | null } =
    $props();

  const summary = $derived(
    steps.every((step) => step.met)
      ? "All four conditions are met."
      : `Blocked at “${steps.find((step) => !step.met)?.label ?? "unknown"}”.`,
  );
</script>

<div class="track">
  <ol aria-label="Extension readiness">
    {#each steps as step (step.label)}
      <li class:met={step.met}>
        <span class="marker" aria-hidden="true">{step.met ? "✓" : "○"}</span>
        <span class="text">
          <span class="name">{step.label}</span>
          <span class="note">{step.note}</span>
        </span>
        <span class="sr-only">{step.met ? "met" : "not met"}</span>
      </li>
    {/each}
  </ol>
  <p class="summary" class:blocked={blockedReason !== null}>{summary}</p>
</div>

<style>
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.3rem;
  }
  li {
    display: grid;
    grid-template-columns: 1.1rem 1fr;
    gap: 0.5rem;
    align-items: start;
    font-size: 0.82rem;
  }
  .marker {
    color: var(--text-3);
    font-weight: 700;
    line-height: 1.5;
  }
  li.met .marker { color: var(--ok); }
  .text { display: grid; gap: 0.05rem; }
  .name { color: var(--text-2); font-weight: 600; }
  li.met .name { color: var(--text-1); }
  .note { color: var(--text-3); font-size: 0.76rem; }
  .summary {
    margin: var(--space-2) 0 0;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--ok);
  }
  .summary.blocked { color: var(--warn); }
</style>
