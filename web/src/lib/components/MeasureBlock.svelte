<script lang="ts">
  /**
   * QUI-A06 — one value on a known scale: 4.2 of 5, 72% of budget, 31 of 40
   * checks.
   *
   * The runtime refused a value off its scale, so the bar is never drawn full
   * for a number past the end. The words carry the reading ("31 of 40"); the
   * native `<meter>` gives assistive technology the same three numbers.
   */
  import { figure } from "../answerBlocks";

  let {
    label,
    value,
    min = 0,
    max,
    unit = "",
    source = "",
    estimate = false,
  }: {
    label: string;
    value: number;
    min?: number;
    max: number;
    unit?: string;
    source?: string;
    estimate?: boolean;
  } = $props();

  const share = $derived(Math.max(0, Math.min(1, (value - min) / (max - min || 1))));
  const reading = $derived(
    `${figure(value, unit)} of ${min === 0 ? "" : `${figure(min)}–`}${figure(max, unit)}`,
  );
</script>

<div class="measure">
  <p class="head">
    <span class="label">{label}</span>
    <span class="reading">{reading}{#if estimate}<span class="estimate"> · ≈ estimate</span>{/if}</span>
  </p>
  <meter {min} {max} {value} aria-label={`${label}: ${reading}`}></meter>
  <span class="track" aria-hidden="true"><span class="fill" style={`width: ${share * 100}%`}></span></span>
  {#if source}<p class="source">Source: {source}</p>{/if}
</div>

<style>
  .head { display: flex; justify-content: space-between; gap: var(--space-3); margin: 0 0 var(--space-2); }
  .label { font-weight: 650; color: var(--text-1); }
  .reading { color: var(--text-1); font-variant-numeric: tabular-nums; }
  .estimate { color: var(--text-3); font-size: var(--text-xs); }
  /* The native meter is the accessible one; its look differs on every engine,
     so it is kept for assistive technology and the bar below is drawn. */
  meter { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
  .track { display: block; height: 0.6rem; border-radius: var(--r-sm); background: var(--border); overflow: hidden; }
  .fill { display: block; height: 100%; background: var(--chart-1); }
  .source { margin: var(--space-2) 0 0; color: var(--text-3); font-size: var(--text-xs); }
</style>
