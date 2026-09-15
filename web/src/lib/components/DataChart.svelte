<script lang="ts">
  /**
   * A series a turn declared, drawn.
   *
   * BUG-288. Raiker had no chart at all, so a turn whose answer was genuinely a
   * shape had to describe the shape in words. This is the other half of the
   * typed channel: the runtime validates the payload — every series the length
   * of the labels, every value a real number, all of it bounded — and this draws
   * it, so nothing here has to guess or repair.
   *
   * Inline SVG and no library, for the same reason the Markdown renderer is
   * hand-written: the built UI makes no external requests, and a chart is not a
   * good enough reason to change that.
   *
   * **The table is not optional.** A picture of numbers is unreadable to a
   * screen reader and to anyone who cannot distinguish the series colours, so
   * the same data is always available as a real table underneath. The SVG is
   * `aria-hidden`; the table is the accessible content.
   */
  import DataTable from "./DataTable.svelte";

  type Series = { name: string; values: number[] };

  let {
    kind = "bar",
    caption = "",
    yLabel = "",
    labels,
    series,
  }: {
    kind?: string;
    caption?: string;
    yLabel?: string;
    labels: string[];
    series: Series[];
  } = $props();

  const W = 640;
  const H = 260;
  const PAD = { top: 16, right: 16, bottom: 34, left: 48 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const flat = $derived(series.flatMap((s) => s.values));
  /**
   * Zero is always in range for bar and area.
   *
   * A bar chart whose axis starts at 47 exaggerates every difference in it, and
   * a model choosing the data does not get to choose that too.
   */
  const min = $derived(Math.min(0, ...flat));
  const max = $derived(Math.max(0, ...flat, min + 1));
  const span = $derived(max - min || 1);

  const x = (index: number) =>
    labels.length === 1
      ? PAD.left + plotW / 2
      : PAD.left + (index * plotW) / (labels.length - 1);
  const y = (value: number) => PAD.top + plotH - ((value - min) / span) * plotH;

  /** Five reference lines: enough to read a value off, few enough to stay quiet. */
  const ticks = $derived(
    Array.from({ length: 5 }, (_, i) => min + (span * i) / 4),
  );

  function line(values: number[]): string {
    return values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i)} ${y(v)}`).join(" ");
  }

  function area(values: number[]): string {
    const base = y(Math.max(min, 0));
    return `${line(values)} L${x(values.length - 1)} ${base} L${x(0)} ${base} Z`;
  }

  /** Bars share each label's slot, so two series never draw over one another. */
  const barWidth = $derived(
    Math.max(2, (plotW / Math.max(labels.length, 1) / Math.max(series.length, 1)) * 0.7),
  );
  const slot = $derived(plotW / Math.max(labels.length, 1));

  function tidy(value: number): string {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }

  // The same numbers, as the table that is the accessible version of this.
  const columns = $derived(["", ...series.map((s) => s.name || "Value")]);
  const rows = $derived(
    labels.map((label, index) => [label, ...series.map((s) => tidy(s.values[index]))]),
  );
</script>

<figure class="data-chart">
  <figcaption>
    {caption || "Chart"}
    {#if yLabel}<span class="axis">{yLabel}</span>{/if}
  </figcaption>

  <svg viewBox={`0 0 ${W} ${H}`} role="presentation" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
    {#each ticks as tick, index (index)}
      <line class="grid" x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} />
      <text class="tick" x={PAD.left - 6} y={y(tick) + 4} text-anchor="end">{tidy(tick)}</text>
    {/each}

    {#if kind === "bar"}
      {#each series as s, si (si)}
        {#each s.values as value, i (i)}
          <rect
            class="mark"
            data-series={si % 6}
            x={PAD.left + i * slot + slot / 2 - (series.length * barWidth) / 2 + si * barWidth}
            y={Math.min(y(value), y(Math.max(min, 0)))}
            width={barWidth}
            height={Math.max(1, Math.abs(y(value) - y(Math.max(min, 0))))}
          />
        {/each}
      {/each}
    {:else}
      {#each series as s, si (si)}
        {#if kind === "area"}
          <path class="fill" data-series={si % 6} d={area(s.values)} />
        {/if}
        <path class="stroke" data-series={si % 6} d={line(s.values)} />
      {/each}
    {/if}

    {#each labels as label, index (index)}
      {#if labels.length <= 12 || index % Math.ceil(labels.length / 12) === 0}
        <text
          class="tick"
          x={kind === "bar" ? PAD.left + index * slot + slot / 2 : x(index)}
          y={H - 10}
          text-anchor="middle">{label}</text
        >
      {/if}
    {/each}
  </svg>

  {#if series.length > 1}
    <ul class="legend">
      {#each series as s, si (si)}
        <li><span class="swatch" data-series={si % 6}></span>{s.name || `Series ${si + 1}`}</li>
      {/each}
    </ul>
  {/if}

  <details class="values">
    <summary>The numbers behind this chart</summary>
    <!-- Its own caption, not the figure's: two headings reading the same
         words is how a screen reader ends up announcing the chart twice. -->
    <DataTable caption="Values" {columns} {rows} />
  </details>
</figure>

<style>
  .data-chart {
    margin: var(--space-3) 0;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  figcaption {
    font-weight: 650;
    color: var(--text-1);
    margin-bottom: var(--space-2);
  }
  .axis {
    font-weight: 400;
    color: var(--text-3);
    font-size: var(--text-xs);
    margin-inline-start: var(--space-2);
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .grid {
    stroke: var(--border);
    stroke-width: 1;
  }
  .tick {
    fill: var(--text-3);
    font-size: 11px;
  }
  /* Six series colours from the shared chart ramp, so a transcript, a dashboard
     and an export all use the same vocabulary of colour. */
  .mark[data-series="0"], .stroke[data-series="0"] { --c: var(--chart-1); }
  .mark[data-series="1"], .stroke[data-series="1"] { --c: var(--chart-2); }
  .mark[data-series="2"], .stroke[data-series="2"] { --c: var(--chart-3); }
  .mark[data-series="3"], .stroke[data-series="3"] { --c: var(--chart-4); }
  .mark[data-series="4"], .stroke[data-series="4"] { --c: var(--chart-5); }
  .mark[data-series="5"], .stroke[data-series="5"] { --c: var(--chart-6); }
  .fill[data-series="0"] { --c: var(--chart-1); }
  .fill[data-series="1"] { --c: var(--chart-2); }
  .fill[data-series="2"] { --c: var(--chart-3); }
  .fill[data-series="3"] { --c: var(--chart-4); }
  .fill[data-series="4"] { --c: var(--chart-5); }
  .fill[data-series="5"] { --c: var(--chart-6); }
  .mark { fill: var(--c); }
  .stroke { fill: none; stroke: var(--c); stroke-width: 2; stroke-linejoin: round; }
  .fill { fill: var(--c); opacity: 0.18; }
  .swatch {
    display: inline-block;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 2px;
    background: var(--c);
    margin-inline-end: 0.35rem;
  }
  .legend {
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin: var(--space-2) 0 0;
    padding: 0;
    font-size: var(--text-xs);
    color: var(--text-2);
  }
  .legend li { display: flex; align-items: center; }
  /* Folded, because the chart is the answer and the table is how to check it —
     but present always, because the chart alone is not readable to everyone. */
  .values summary {
    cursor: pointer;
    color: var(--text-2);
    font-size: var(--text-sm);
    margin-top: var(--space-2);
  }
  .values summary:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
</style>
