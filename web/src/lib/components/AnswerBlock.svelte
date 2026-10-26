<script lang="ts">
  /**
   * One drawn block of an answer, with its toolbar (Quiet UI 04, Block
   * toolbar): **Chart · Table** on a chart, **Show as text**, **Copy**, and
   * **CSV** or **PNG**.
   *
   * Every action works on the validated part the runtime sent, never on the
   * drawing: Copy and Show as text use the same sentence form the runtime
   * gives an unsourced block and an export, and CSV is the block's own rows.
   * A failed copy or download says so in the toolbar rather than pretending.
   *
   * **Pin** (QUI-F15) files the block in the Library, in the conversation's
   * project when it has one. The surface does the pinning: it names the stored
   * turn and the block's place in it, and the runtime copies the block from
   * the record, so a pin holds exactly what this toolbar sits on.
   */
  import type { Snippet } from "svelte";
  import Icon from "./Icon.svelte";
  import Markdown from "./Markdown.svelte";
  import { blockFilename, blockGrid, blockText, toCsv } from "../answerBlocks";
  import { chartPng, downloadBlob } from "../chartImage";
  import type { ContentPart } from "../apiTypes";

  let {
    part,
    children,
    onpin,
    pinned = false,
    pinLabel = "Pin to the Library",
  }: {
    part: ContentPart;
    /** The drawn block, given the toolbar's chart-or-table choice. */
    children: Snippet<["chart" | "table"]>;
    /**
     * Pin or unpin this block; resolves to the sentence the toolbar says.
     * Without it there is no Pin button (an unsaved or streaming answer).
     */
    onpin?: () => Promise<string>;
    pinned?: boolean;
    /** What Pin does here, as its tooltip: "Pin to Quarterly". */
    pinLabel?: string;
  } = $props();

  let pinning = $state(false);

  async function pin() {
    if (!onpin || pinning) return;
    pinning = true;
    try {
      say(await onpin());
    } catch {
      say(pinned ? "Could not unpin: try again" : "Could not pin: try again");
    } finally {
      pinning = false;
    }
  }

  const BLOCK_NAMES: Record<string, string> = {
    table: "Table",
    chart: "Chart",
    figures: "Key figures",
    compare: "Comparison",
    measure: "Measure",
    callout: "Callout",
    proscons: "Pros and cons",
    steps: "Steps",
  };

  let view = $state<"chart" | "table">("chart");
  let asText = $state(false);
  let notice = $state("");
  let root = $state<HTMLElement>();

  const isChart = $derived(part.type === "chart");
  const grid = $derived(blockGrid(part));
  const text = $derived(blockText(part));
  const label = $derived(
    String(part.data?.caption ?? part.data?.label ?? "") || BLOCK_NAMES[part.type] || "Answer block",
  );

  function say(message: string) {
    notice = message;
    setTimeout(() => {
      if (notice === message) notice = "";
    }, 2500);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      say("Copied");
    } catch {
      say("Could not copy: the browser did not allow it");
    }
  }

  function csv() {
    if (grid === null) return;
    downloadBlob(new Blob([toCsv(grid)], { type: "text/csv;charset=utf-8" }), blockFilename(part, "csv"));
  }

  async function png() {
    const svg = root?.querySelector<SVGSVGElement>("figure.data-chart svg");
    if (!svg) {
      say("Switch to Chart to save it as an image");
      return;
    }
    try {
      const surface = getComputedStyle(document.documentElement).getPropertyValue("--surface").trim() || "white";
      downloadBlob(await chartPng(svg, surface), blockFilename(part, "png"));
    } catch {
      say("Could not make an image of this chart");
    }
  }
</script>

<section class="answer-block" data-block={part.type} aria-label={label} bind:this={root}>
  <div class="toolbar" role="toolbar" aria-label={`${label} actions`}>
    {#if isChart && !asText}
      <div class="segmented" role="group" aria-label="Show as">
        <button type="button" aria-pressed={view === "chart"} onclick={() => (view = "chart")}>Chart</button>
        <button type="button" aria-pressed={view === "table"} onclick={() => (view = "table")}>Table</button>
      </div>
    {/if}
    <button type="button" class="tool" aria-pressed={asText} onclick={() => (asText = !asText)}>
      {asText ? "Show as block" : "Show as text"}
    </button>
    <button type="button" class="tool icon" aria-label="Copy" title="Copy" onclick={copy}>
      <Icon name="copy" size="sm" />
    </button>
    {#if isChart && !asText && view === "chart"}
      <button type="button" class="tool" title="Save as PNG image" onclick={png}>PNG</button>
    {/if}
    {#if grid !== null}
      <button type="button" class="tool" title="Download as CSV" onclick={csv}>CSV</button>
    {/if}
    {#if onpin}
      <button
        type="button"
        class="tool icon"
        aria-pressed={pinned}
        title={pinned ? "Unpin" : pinLabel}
        aria-label={pinned ? "Unpin" : pinLabel}
        disabled={pinning}
        onclick={pin}
      >
        <Icon name="pin" size="sm" />
        <span class="pin-word">{pinned ? "Pinned" : "Pin"}</span>
      </button>
    {/if}
    <span class="notice" role="status">{notice}</span>
  </div>
  {#if asText}
    <div class="as-text"><Markdown text={text.replace(/\t/g, " · ")} /></div>
  {:else}
    {@render children(view)}
  {/if}
</section>

<style>
  .answer-block {
    margin: var(--space-3) 0;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  /* Quiet until wanted: the toolbar sits on one line above the block in the
     muted text colour, and full strength on hover or focus within. */
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin: calc(var(--space-1) * -1) 0 var(--space-2);
    color: var(--text-3);
  }
  .answer-block:hover .toolbar,
  .toolbar:focus-within { color: var(--text-2); }
  .tool,
  .segmented button {
    font: inherit;
    font-size: var(--text-xs);
    color: inherit;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--r-sm);
    padding: 0.15rem 0.45rem;
    cursor: pointer;
    min-height: 1.6rem;
  }
  .tool.icon { display: inline-flex; align-items: center; gap: 0.25rem; }
  .tool:disabled { opacity: 0.6; cursor: progress; }
  .tool:hover,
  .segmented button:hover { border-color: var(--border); color: var(--text-1); }
  .tool[aria-pressed="true"] { color: var(--text-1); border-color: var(--border); }
  .segmented { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-sm); }
  .segmented button { border-radius: 0; }
  .segmented button[aria-pressed="true"] { background: var(--accent-soft); color: var(--accent-strong); }
  .tool:focus-visible,
  .segmented button:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 1px; }
  .notice { font-size: var(--text-xs); color: var(--text-2); min-width: 0; }
  .notice:empty { display: none; }
  .as-text :global(p:first-child) { margin-top: 0; }
</style>
