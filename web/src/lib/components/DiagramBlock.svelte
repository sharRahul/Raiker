<script lang="ts">
  /**
   * QUI-A08 — a flow or a structure a turn declared, drawn.
   *
   * The model sends nodes and edges, never a picture or diagram markup; the
   * runtime validates them and ranks the layers, and `diagramLayout.ts` places
   * the boxes. Inline SVG with no library, like every chart: nothing a model
   * writes in a label is interpreted as anything but text.
   *
   * Three shapes, each a claim: a box is a step, a rounded box a start or an
   * end, a diamond a question. An arrow back to an earlier step (a retry, a
   * loop) is dashed and drawn around the side, so a reader sees it is a return
   * and not the way forward.
   *
   * **The list is not optional.** The SVG is `aria-hidden`; the same diagram is
   * in the page as an ordered list of each step and where it leads, the way a
   * chart keeps its table.
   */
  import { layoutDiagram, type DiagramEdge, type DiagramNode, type Direction } from "../diagramLayout";

  let {
    caption = "",
    direction = "down",
    nodes,
    edges,
  }: {
    caption?: string;
    direction?: Direction;
    nodes: DiagramNode[];
    edges: DiagramEdge[];
  } = $props();

  // One marker per drawing: two diagrams in one answer must not share an id.
  const uid = `dg-${Math.random().toString(36).slice(2, 9)}`;

  const layout = $derived(layoutDiagram(nodes, edges, direction));
  const labels = $derived(new Map(nodes.map((node) => [node.id, node.label])));
  const ordered = $derived([...nodes].sort((a, b) => a.rank - b.rank));

  function diamond(x: number, y: number, w: number, h: number): string {
    return `${x},${y - h / 2} ${x + w / 2},${y} ${x},${y + h / 2} ${x - w / 2},${y}`;
  }
</script>

<figure class="diagram" data-direction={direction}>
  {#if caption}<figcaption>{caption}</figcaption>{/if}
  <div class="canvas">
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      width={layout.width}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <marker id={`${uid}-head`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path class="head" d="M 0 0 L 10 5 L 0 10 z" />
        </marker>
      </defs>
      {#each layout.edges as edge (edge.from + "→" + edge.to)}
        <path class="edge" class:back={edge.back} d={edge.path} marker-end={`url(#${uid}-head)`} />
      {/each}
      {#each layout.nodes as node (node.id)}
        <g class="node" data-shape={node.shape}>
          {#if node.shape === "diamond"}
            <polygon class="shape" points={diamond(node.x, node.y, node.w, node.h)} />
          {:else}
            <rect
              class="shape"
              x={node.x - node.w / 2}
              y={node.y - node.h / 2}
              width={node.w}
              height={node.h}
              rx={node.shape === "round" ? node.h / 2 : 6}
            />
          {/if}
          {#each node.lines as line, index (index)}
            <text
              class="label"
              x={node.x}
              y={node.y - ((node.lines.length - 1) * 16) / 2 + index * 16 + 4.5}
              text-anchor="middle">{line}</text
            >
          {/each}
        </g>
      {/each}
      {#each layout.edges.filter((edge) => edge.label) as edge (edge.from + "→" + edge.to + ":label")}
        <g class="edge-label">
          <rect
            class="chip"
            x={edge.lx - (edge.label.length * 6.2 + 12) / 2}
            y={edge.ly - 10}
            width={edge.label.length * 6.2 + 12}
            height="20"
            rx="10"
          />
          <text class="chip-text" x={edge.lx} y={edge.ly + 4} text-anchor="middle">{edge.label}</text>
        </g>
      {/each}
    </svg>
  </div>
  <ol class="sr-only">
    {#each ordered as node (node.id)}
      {@const leads = edges.filter((edge) => edge.from === node.id)}
      <li>
        {node.label}{#if leads.length}: leads to {leads
            .map((edge) => `${labels.get(edge.to)}${edge.label ? ` (${edge.label})` : ""}`)
            .join("; ")}{/if}
      </li>
    {/each}
  </ol>
</figure>

<style>
  .diagram { margin: 0; }
  figcaption { font-weight: 650; color: var(--text-1); margin-bottom: var(--space-2); }
  /* A wide pipeline scrolls inside its block rather than shrinking its text
     below reading size or widening the transcript. */
  /* The width a chart is drawn at, so a narrow flow does not shrink its
     answer bubble to a column; the drawing keeps its own size, centred. */
  .canvas { overflow-x: auto; width: 640px; max-width: 100%; }
  svg { display: block; margin: 0 auto; max-width: 100%; height: auto; }
  .shape {
    fill: var(--surface-raised);
    stroke: var(--border-strong);
    stroke-width: 1.25;
  }
  .node[data-shape="round"] .shape { fill: var(--accent-soft); stroke: var(--accent-border); }
  .node[data-shape="diamond"] .shape { stroke: var(--accent); }
  .label {
    fill: var(--text-1);
    font-family: var(--font-sans);
    font-size: 13px;
    font-weight: 500;
  }
  .edge {
    fill: none;
    stroke: var(--text-3);
    stroke-width: 1.5;
  }
  .edge.back { stroke-dasharray: 5 4; }
  .head { fill: var(--text-3); }
  .chip { fill: var(--surface); stroke: var(--border); stroke-width: 1; }
  .chip-text {
    fill: var(--text-2);
    font-family: var(--font-sans);
    font-size: 11px;
  }
</style>
