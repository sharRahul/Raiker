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
  import AnswerBlock from "./AnswerBlock.svelte";
  import Callout from "./Callout.svelte";
  import Comparison from "./Comparison.svelte";
  import DataChart from "./DataChart.svelte";
  import DataTable from "./DataTable.svelte";
  import KeyFigures from "./KeyFigures.svelte";
  import Markdown from "./Markdown.svelte";
  import MeasureBlock from "./MeasureBlock.svelte";
  import ProsCons from "./ProsCons.svelte";
  import StepsBlock from "./StepsBlock.svelte";
  import {
    BLOCK_TYPES,
    BLOCKS_PER_ANSWER,
    blockCount,
    holdBackBlocks,
    type CompareRow,
    type Figure,
    type ProsConsOption,
    type Step,
  } from "../answerBlocks";
  import type { ContentPart } from "../apiTypes";

  let {
    text,
    parts = [],
    citations,
    oncite,
    ondocument,
    streaming = false,
    onpin,
    pinned,
    pinLabel,
  }: {
    /** The whole answer. Rendered as-is when the runtime declared no parts. */
    text: string;
    parts?: ContentPart[];
    citations?: ReadonlySet<string>;
    oncite?: (sourceId: string) => void;
    /**
     * Quiet UI 04 — more than three blocks is a report, and a report belongs
     * in a document. The surface decides what *Create document* does; with no
     * handler the offer is not shown.
     */
    ondocument?: () => void;
    /** The turn is still streaming: `raiker:` fences are held back until it ends. */
    streaming?: boolean;
    /**
     * QUI-F15 — pin or unpin the block at this place in `parts`. The surface
     * passes it only for a stored turn; it resolves to what the toolbar says.
     */
    onpin?: (index: number) => Promise<string>;
    /** The places in `parts` already pinned. */
    pinned?: ReadonlySet<number>;
    /** Pin's tooltip, naming where a pin goes: "Pin to Quarterly". */
    pinLabel?: string;
  } = $props();

  const blocks = $derived(blockCount(parts));

  /**
   * Only take the typed route when there is something typed in it.
   *
   * A streaming turn has text and no parts yet; so does an older transcript,
   * and so does any client talking to a build that predates the channel. All
   * three want the renderer that has always been here.
   */
  const typed = $derived(parts.some((part) => BLOCK_TYPES.has(part.type) || part.type === "refused"));

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
    chart_kind_unsupported: "Raiker draws bar, line, area, stacked and scatter charts; this asked for something else.",
    chart_scatter_needs_two_series: "A scatter chart plots one measure against another, so it needs exactly two series.",
    chart_stacked_negative: "A part of a whole cannot be negative, so Raiker did not draw these shares.",
    chart_stacked_empty: "One bar's parts added up to nothing, so it had no whole to divide.",
    figures_not_json: "These figures were not valid JSON, so Raiker did not show them.",
    figures_too_many: "Key figures show at most four numbers.",
    figures_unit_missing: "A figure had no unit, and a number without one is not something to act on.",
    figures_value_not_a_number: "A figure's value was not a number.",
    compare_not_json: "This comparison was not valid JSON, so Raiker did not show it.",
    compare_row_width_mismatch: "A row did not have one value per item, so Raiker did not guess at the missing ones.",
    compare_better_needs_numbers: "A row said which value is better, but not every value in it was a number.",
    compare_too_many_items: "A comparison shows at most six items.",
    measure_value_off_scale: "The value was outside its own scale, so Raiker did not draw it as full or empty.",
    measure_scale_invalid: "This measure's scale was not usable.",
    callout_tone_invalid: "A callout is a verdict, a warning or a next step; this asked for something else.",
    proscons_option_empty: "An option had neither pros nor cons.",
    steps_too_many: "A sequence shows at most twelve steps.",
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
  <Markdown text={streaming ? holdBackBlocks(text) : text} {citations} {oncite} />
{:else}
  {#each parts as part, index (index)}
    {#if part.type === "text"}
      <Markdown text={part.text ?? ""} {citations} {oncite} />
    {:else if part.type === "refused"}
      <p class="refused" role="note">
        <strong>Not rendered.</strong>
        {refusal(part.reason_code ?? "")}
        <span class="code">{part.reason_code}</span>
      </p>
    {:else if BLOCK_TYPES.has(part.type) && part.data}
      {@const d = part.data as Record<string, unknown>}
      <AnswerBlock
        {part}
        onpin={onpin && !streaming ? () => onpin(index) : undefined}
        pinned={pinned?.has(index) ?? false}
        {pinLabel}
      >
        {#snippet children(view)}
          {#if part.type === "table"}
            <DataTable caption={String(d.caption ?? "")} columns={(d.columns ?? []) as string[]} rows={(d.rows ?? []) as string[][]} />
          {:else if part.type === "chart"}
            <DataChart
              kind={String(d.kind ?? "bar")}
              caption={String(d.caption ?? "")}
              yLabel={String(d.y_label ?? "")}
              labels={(d.labels ?? []) as string[]}
              series={(d.series ?? []) as { name: string; values: number[] }[]}
              {view}
            />
          {:else if part.type === "figures"}
            <KeyFigures caption={String(d.caption ?? "")} items={d.items as Figure[]} source={String(d.source ?? "")} estimate={Boolean(d.estimate)} />
          {:else if part.type === "compare"}
            <Comparison
              caption={String(d.caption ?? "")}
              items={d.items as string[]}
              rows={d.rows as CompareRow[]}
              source={String(d.source ?? "")}
              estimate={Boolean(d.estimate)}
            />
          {:else if part.type === "measure"}
            <MeasureBlock
              label={String(d.label ?? "")}
              value={Number(d.value)}
              min={Number(d.min ?? 0)}
              max={Number(d.max)}
              unit={String(d.unit ?? "")}
              source={String(d.source ?? "")}
              estimate={Boolean(d.estimate)}
            />
          {:else if part.type === "callout"}
            <Callout tone={String(d.tone ?? "verdict")} text={String(d.text ?? "")} />
          {:else if part.type === "proscons"}
            <ProsCons caption={String(d.caption ?? "")} options={d.options as ProsConsOption[]} />
          {:else if part.type === "steps"}
            <StepsBlock caption={String(d.caption ?? "")} steps={d.steps as Step[]} />
          {/if}
        {/snippet}
      </AnswerBlock>
    {/if}
  {/each}
  {#if blocks > BLOCKS_PER_ANSWER && ondocument}
    <p class="report-offer">
      This answer has {blocks} blocks. A document keeps them together.
      <button type="button" class="btn btn-soft btn-sm" onclick={ondocument}>Create document</button>
    </p>
  {/if}
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
  .report-offer {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin: var(--space-2) 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .code {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-3);
    margin-inline-start: var(--space-2);
  }
</style>
