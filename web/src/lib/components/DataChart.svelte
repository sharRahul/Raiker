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
   * Six kinds (Quiet UI 04): bar and line and area, plus horizontal bars for
   * rankings with long names (QUI-A01), 100% stacked bars for parts of a whole
   * instead of a pie (QUI-A02) and a scatter of two measures (QUI-A03).
   *
   * **The table is not optional.** A picture of numbers is unreadable to a
   * screen reader and to anyone who cannot distinguish the series colours, so
   * the same data is always in the page as a real table: visible when the
   * block toolbar's **Table** is chosen, and otherwise kept for assistive
   * technology. The SVG is `aria-hidden`; the table is the accessible content.
   */
  import DataTable from "./DataTable.svelte";
  import { figure } from "../answerBlocks";

  type Series = { name: string; values: number[] };

  let {
    kind = "bar",
    caption = "",
    yLabel = "",
    labels,
    series,
    view = "chart",
  }: {
    kind?: string;
    caption?: string;
    yLabel?: string;
    labels: string[];
    series: Series[];
    /** The block toolbar's choice: the drawing, or the numbers as a table. */
    view?: "chart" | "table";
  } = $props();

  // The width a chart is drawn at, in SVG units: near the width a transcript
  // bubble that holds a chart gives it, so 12-unit labels read at about 13 px.
  const W = 640;
  const PAD = { top: 16, right: 16, bottom: 34, left: 48 };
  const plotW = W - PAD.left - PAD.right;

  /** Horizontal kinds put the labels on the left, so the left margin is theirs. */
  const horizontal = $derived(kind === "hbar" || kind === "stacked");
  const ROW = 26;
  const longest = $derived(Math.max(0, ...labels.map((label) => label.length)));
  const hLeft = $derived(Math.min(180, Math.max(64, longest * 7 + 12)));
  const H = $derived(horizontal ? PAD.top + labels.length * ROW + 30 : 260);
  const plotH = $derived(H - PAD.top - PAD.bottom);

  const flat = $derived(series.flatMap((s) => s.values));
  /**
   * Zero is always in range for every bar and for area.
   *
   * A bar chart whose axis starts at 47 exaggerates every difference in it, and
   * a model choosing the data does not get to choose that too. A scatter is
   * two positions, not lengths, so its axes fit the points instead.
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

  // ── Horizontal kinds ──
  const hPlotW = $derived(W - hLeft - PAD.right);
  const hx = (value: number) => hLeft + ((value - min) / span) * hPlotW;
  const barH = $derived(Math.max(4, ((ROW * 0.7) / Math.max(series.length, 1))));
  /** Each label's parts as shares of its own total, for the 100% bars. */
  const shares = $derived(
    labels.map((_, index) => {
      const total = series.reduce((sum, s) => sum + s.values[index], 0) || 1;
      return series.map((s) => s.values[index] / total);
    }),
  );
  function offset(row: number[], upTo: number): number {
    return row.slice(0, upTo).reduce((sum, value) => sum + value, 0);
  }

  // ── Scatter ──
  /** Padded ranges, so a point never sits on the frame. */
  function range(values: number[]): [number, number] {
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
    return [lo - pad, hi + pad];
  }
  const xr = $derived(kind === "scatter" ? range(series[0]?.values ?? [0]) : [0, 1]);
  const yr = $derived(kind === "scatter" ? range(series[1]?.values ?? [0]) : [0, 1]);
  const sx = (value: number) => PAD.left + ((value - xr[0]) / (xr[1] - xr[0] || 1)) * plotW;
  const sy = (value: number) => PAD.top + plotH - ((value - yr[0]) / (yr[1] - yr[0] || 1)) * plotH;
  const scatterTicks = (r: number[]) => Array.from({ length: 5 }, (_, i) => r[0] + ((r[1] - r[0]) * i) / 4);

  function tidy(value: number): string {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  function percent(share: number): string {
    return `${Math.round(share * 100)}%`;
  }

  // The same numbers, as the table that is the accessible version of this.
  const columns = $derived(
    kind === "stacked"
      ? ["", ...series.flatMap((s) => [s.name || "Value", `${s.name || "Value"} share`])]
      : [kind === "scatter" ? "Point" : "", ...series.map((s) => s.name || "Value")],
  );
  const rows = $derived(
    labels.map((label, index) =>
      kind === "stacked"
        ? [label, ...series.flatMap((s, si) => [figure(s.values[index]), percent(shares[index][si])])]
        : [label, ...series.map((s) => tidy(s.values[index]))],
    ),
  );
  const axisNote = $derived(
    kind === "scatter" && series.length === 2
      ? `${series[0].name || "x"} across, ${series[1].name || "y"} up`
      : yLabel,
  );
</script>

<figure class="data-chart" data-kind={kind}>
  <figcaption>
    {caption || "Chart"}
    {#if axisNote}<span class="axis">{axisNote}</span>{/if}
  </figcaption>

  {#if view === "table"}
    <DataTable caption="Values" {columns} {rows} />
  {:else}
  <svg viewBox={`0 0 ${W} ${H}`} role="presentation" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
    {#if kind === "scatter"}
      {#each scatterTicks(yr) as tick, index (index)}
        <line class="grid" x1={PAD.left} x2={W - PAD.right} y1={sy(tick)} y2={sy(tick)} />
        <text class="tick" x={PAD.left - 6} y={sy(tick) + 4} text-anchor="end">{tidy(tick)}</text>
      {/each}
      {#each scatterTicks(xr) as tick, index (index)}
        <text class="tick" x={sx(tick)} y={H - 10} text-anchor="middle">{tidy(tick)}</text>
      {/each}
      {#each labels as label, index (index)}
        <circle class="dot" data-series="0" cx={sx(series[0].values[index])} cy={sy(series[1].values[index])} r="5" />
        {#if labels.length <= 12}
          <!-- A point on the right half is labelled on its left, so the label
               never runs past the frame. -->
          {@const right = sx(series[0].values[index]) > PAD.left + plotW / 2}
          <text
            class="point-label"
            x={sx(series[0].values[index]) + (right ? -8 : 8)}
            y={sy(series[1].values[index]) + 4}
            text-anchor={right ? "end" : "start"}>{label}</text
          >
        {/if}
      {/each}
    {:else if horizontal}
      {#if kind === "hbar"}
        {#each ticks as tick, index (index)}
          <line class="grid" x1={hx(tick)} x2={hx(tick)} y1={PAD.top} y2={H - 26} />
          <text class="tick" x={hx(tick)} y={H - 10} text-anchor="middle">{tidy(tick)}</text>
        {/each}
      {:else}
        {#each [0, 0.25, 0.5, 0.75, 1] as tick, index (index)}
          <line class="grid" x1={hLeft + tick * hPlotW} x2={hLeft + tick * hPlotW} y1={PAD.top} y2={H - 26} />
          <text class="tick" x={hLeft + tick * hPlotW} y={H - 10} text-anchor="middle">{percent(tick)}</text>
        {/each}
      {/if}
      {#each labels as label, index (index)}
        <text class="tick row-label" x={hLeft - 8} y={PAD.top + index * ROW + ROW / 2 + 4} text-anchor="end">{label}</text>
        {#if kind === "hbar"}
          {#each series as s, si (si)}
            <rect
              class="mark"
              data-series={si % 6}
              x={Math.min(hx(s.values[index]), hx(0))}
              y={PAD.top + index * ROW + (ROW - barH * series.length) / 2 + si * barH}
              width={Math.max(1, Math.abs(hx(s.values[index]) - hx(0)))}
              height={barH}
            />
          {/each}
        {:else}
          {#each [...series.keys()] as si (si)}
            <rect
              class="mark"
              data-series={si % 6}
              x={hLeft + offset(shares[index], si) * hPlotW}
              y={PAD.top + index * ROW + ROW * 0.15}
              width={shares[index][si] * hPlotW}
              height={ROW * 0.7}
            />
            {#if shares[index][si] * hPlotW > 34}
              <text class="share" x={hLeft + (offset(shares[index], si) + shares[index][si] / 2) * hPlotW} y={PAD.top + index * ROW + ROW / 2 + 4} text-anchor="middle">{percent(shares[index][si])}</text>
            {/if}
          {/each}
        {/if}
      {/each}
    {:else}
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
    {/if}
  </svg>

  {#if series.length > 1 && kind !== "scatter"}
    <ul class="legend">
      {#each series as s, si (si)}
        <li><span class="swatch" data-series={si % 6}></span>{s.name || `Series ${si + 1}`}</li>
      {/each}
    </ul>
  {/if}

  <!-- Always in the page: the drawing is decorative, this is the content. Its
       own caption, not the figure's: two headings reading the same words is
       how a screen reader ends up announcing the chart twice. -->
  <div class="sr-only"><DataTable caption="Values" {columns} {rows} /></div>
  {/if}
</figure>

<style>
  .data-chart {
    margin: 0;
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
    font-size: 12px;
  }
  /* Six series colours from the shared chart ramp, so a transcript, a dashboard
     and an export all use the same vocabulary of colour. */
  .mark[data-series="0"], .stroke[data-series="0"], .swatch[data-series="0"] { --c: var(--chart-1); }
  .mark[data-series="1"], .stroke[data-series="1"], .swatch[data-series="1"] { --c: var(--chart-2); }
  .mark[data-series="2"], .stroke[data-series="2"], .swatch[data-series="2"] { --c: var(--chart-3); }
  .mark[data-series="3"], .stroke[data-series="3"], .swatch[data-series="3"] { --c: var(--chart-4); }
  .mark[data-series="4"], .stroke[data-series="4"], .swatch[data-series="4"] { --c: var(--chart-5); }
  .mark[data-series="5"], .stroke[data-series="5"], .swatch[data-series="5"] { --c: var(--chart-6); }
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
  .row-label { fill: var(--text-2); }
  .point-label { fill: var(--text-2); font-size: 12px; }
  .dot { fill: var(--chart-1); stroke: var(--surface); stroke-width: 1.5; }
  /* A share printed on its own segment, in the surface colour so it reads on
     every series colour from the ramp, in either theme. */
  .share { fill: var(--text-inverse); font-size: 11px; font-weight: 650; }
</style>
