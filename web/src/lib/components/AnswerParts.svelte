<script lang="ts">
  /**
   * A turn's answer, rendered from the parts it declared.
   *
   * BUG-288. Before this, an answer was one string and everything in it was
   * inferred from the characters. A turn can now declare that a section *is* a
   * table or a series, the runtime validates the payload the way it validates
   * any other model-proposed argument, and this renders each part as the thing
   * it says it is.
   *
   * Three properties this component exists to keep:
   *
   * 1. **An ordinary answer is unchanged.** A turn that declares nothing has
   *    exactly one text part, which goes through the same Markdown renderer,
   *    with the same citation chips and the same read-aloud behaviour.
   * 2. **A refusal is visible.** A declared block the runtime would not accept
   *    is shown as refused, with its reason. A part that vanished would be a
   *    turn whose answer silently lost a section — a model able to make a
   *    section disappear by writing bad JSON is a worse failure than a message
   *    the owner can see and act on.
   * 3. **The parts are the runtime's, not the browser's.** Nothing here parses
   *    the answer; the split arrives already made. That is the difference
   *    between a typed channel and a renderer guessing at pipes and dashes.
   */
  import DataChart from "./DataChart.svelte";
  import DataTable from "./DataTable.svelte";
  import Markdown from "./Markdown.svelte";
  import type { ContentPart } from "../apiTypes";

  let {
    text,
    parts = [],
    citations,
    oncite,
  }: {
    /** The whole answer. Rendered as-is when the runtime declared no parts. */
    text: string;
    parts?: ContentPart[];
    citations?: ReadonlySet<string>;
    oncite?: (sourceId: string) => void;
  } = $props();

  /**
   * Only take the typed route when there is something typed in it.
   *
   * A streaming turn has text and no parts yet; so does an older transcript,
   * and so does any client talking to a build that predates the channel. All
   * three want the renderer that has always been here.
   */
  const typed = $derived(parts.some((part) => part.type === "table" || part.type === "chart" || part.type === "refused"));

  /** Reasons an owner can act on. Anything unlisted still shows its code. */
  const REFUSALS: Record<string, string> = {
    too_many_parts: "This answer declared more tables and charts than Raiker will render.",
    table_not_an_object: "Raiker could not read this as a table.",
    table_not_json: "This table was not valid JSON, so Raiker did not render it.",
    table_columns_missing: "This table named no columns.",
    table_too_many_columns: "This table declared more columns than Raiker will render.",
    table_too_many_rows: "This table declared more rows than Raiker will render.",
    table_rows_missing: "This table had no rows.",
    table_row_not_a_list: "One of this table's rows was not a list of cells.",
    table_row_width_mismatch: "One row did not match the number of columns, so Raiker did not guess at the missing cells.",
    table_cell_not_text: "A cell in this table was not text Raiker could show.",
    table_column_not_text: "A column heading in this table was not text.",
    table_caption_invalid: "This table's caption was not usable.",
    chart_not_an_object: "Raiker could not read this as a chart.",
    chart_not_json: "This chart was not valid JSON, so Raiker did not render it.",
    chart_kind_unsupported: "Raiker draws bar, line and area charts; this asked for something else.",
    chart_labels_missing: "This chart had no labels to plot against.",
    chart_too_many_points: "This chart declared more points than Raiker will draw.",
    chart_label_invalid: "One of this chart's labels was not usable.",
    chart_series_missing: "This chart declared no series.",
    chart_too_many_series: "This chart declared more series than Raiker will draw.",
    chart_series_not_an_object: "One of this chart's series was not readable.",
    chart_series_name_invalid: "One series name was not usable.",
    chart_series_length_mismatch: "A series did not have one value per label, so Raiker did not align them by guessing.",
    chart_value_not_a_number: "A value in this chart was not a number.",
    chart_caption_invalid: "This chart's caption was not usable.",
    chart_y_label_invalid: "This chart's axis label was not usable.",
  };

  function refusal(code: string): string {
    return REFUSALS[code] ?? "Raiker did not accept this part of the answer.";
  }
</script>

{#if !typed}
  <Markdown {text} {citations} {oncite} />
{:else}
  {#each parts as part, index (index)}
    {#if part.type === "text"}
      <Markdown text={part.text ?? ""} {citations} {oncite} />
    {:else if part.type === "table" && part.data}
      <DataTable
        caption={String(part.data.caption ?? "")}
        columns={(part.data.columns ?? []) as string[]}
        rows={(part.data.rows ?? []) as string[][]}
      />
    {:else if part.type === "chart" && part.data}
      <DataChart
        kind={String(part.data.kind ?? "bar")}
        caption={String(part.data.caption ?? "")}
        yLabel={String(part.data.y_label ?? "")}
        labels={(part.data.labels ?? []) as string[]}
        series={(part.data.series ?? []) as { name: string; values: number[] }[]}
      />
    {:else if part.type === "refused"}
      <p class="refused" role="note">
        <strong>Not rendered.</strong>
        {refusal(part.reason_code ?? "")}
        <span class="code">{part.reason_code}</span>
      </p>
    {/if}
  {/each}
{/if}

<style>
  /* A notice, not an error: the turn answered, and one declared block of it was
     not something Raiker would draw. It says which and why. */
  .refused {
    margin: var(--space-3) 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--warn-border);
    border-radius: var(--r-md);
    background: var(--warn-soft);
    color: var(--text-1);
    font-size: var(--text-sm);
  }
  .code {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-3);
    margin-inline-start: var(--space-2);
  }
</style>
