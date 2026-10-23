<script lang="ts">
  /**
   * QUI-A07 — an ordered or dated sequence, on the path line.
   *
   * The path line (08, the companion layer) is a thin line through points:
   * only for sequences that exist, never decoration. An ordered list, so a
   * screen reader announces "1 of 4" without the line.
   */
  import type { Step } from "../answerBlocks";

  let { caption = "", steps }: { caption?: string; steps: Step[] } = $props();
</script>

<figure class="steps">
  {#if caption}<figcaption>{caption}</figcaption>{/if}
  <ol class="path">
    {#each steps as step, index (index)}
      <li>
        <span class="point" aria-hidden="true"></span>
        <p class="label">
          {step.label}{#if step.when}<span class="when">{step.when}</span>{/if}
        </p>
        {#if step.text}<p class="text">{step.text}</p>{/if}
      </li>
    {/each}
  </ol>
</figure>

<style>
  .steps { margin: 0; }
  figcaption { font-weight: 650; color: var(--text-1); margin-bottom: var(--space-2); }
  .path { list-style: none; margin: 0; padding: 0; }
  li { position: relative; padding: 0 0 var(--space-3) 1.6rem; }
  li:last-child { padding-bottom: 0; }
  /* The line runs from this point to the next; the last point has none. */
  li:not(:last-child)::before {
    content: "";
    position: absolute;
    left: 0.4rem;
    top: 0.85rem;
    bottom: -0.15rem;
    width: 2px;
    background: var(--accent-border);
  }
  .point {
    position: absolute;
    left: 0.1rem;
    top: 0.3rem;
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 50%;
    border: 2px solid var(--accent);
    background: var(--surface);
  }
  .label { margin: 0; font-weight: 600; color: var(--text-1); }
  .when { margin-inline-start: var(--space-2); color: var(--text-3); font-weight: 400; font-size: var(--text-sm); }
  .text { margin: 0.15rem 0 0; color: var(--text-2); font-size: var(--text-sm); }
</style>
