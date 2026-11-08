/**
 * QUI-A08 — where each box of a `raiker:diagram` goes, and the path of each arrow.
 *
 * The runtime has already validated the block and given every node its layer
 * (`rank`, the longest forward path that reaches it), so every surface agrees
 * on which row a box is in. This only orders the boxes inside a layer and
 * turns the result into coordinates. It is a pure function, so the drawing and
 * its tests use the same numbers, and it has no library: the built UI makes no
 * external requests, and a diagram language such as Mermaid would be the
 * first thing in the page that interprets model text as markup.
 *
 * Ordering is one barycentre pass: each box sits near the average place of the
 * boxes that point to it, which removes most crossings in the small flows an
 * answer draws (at most 24 nodes). Ties keep the order the model wrote.
 */

export type DiagramNode = { id: string; label: string; shape: "box" | "round" | "diamond"; rank: number };
export type DiagramEdge = { from: string; to: string; label: string };
export type Direction = "down" | "right";

export type PlacedNode = DiagramNode & { x: number; y: number; w: number; h: number; lines: string[] };
export type PlacedEdge = DiagramEdge & {
  path: string;
  /** Where the label sits: the curve's midpoint. */
  lx: number;
  ly: number;
  /** An arrow back to an earlier layer (a loop or a retry), drawn around the side. */
  back: boolean;
};
export type Layout = { width: number; height: number; nodes: PlacedNode[]; edges: PlacedEdge[] };

/** Roughly how wide a character is at the diagram's 13-unit type. */
const CHAR = 7;
const LINE = 16;
const MAX_LINE_CHARS = 22;
const NODE_MIN_W = 96;
const NODE_MAX_W = MAX_LINE_CHARS * CHAR + 28;
/** Space between layers leaves room for an arrow and its label. */
const LAYER_GAP = 60;
const SIBLING_GAP = 28;
const MARGIN = 16;
/** How far an arrow that goes round swings outside the boxes it passes. */
const BACK_SWING = 36;
/** The gap between two arrows that go round on the same side. */
const LANE = 14;

/** A label broken into at most three lines of whole words; a long word is cut with "…". */
export function wrapLabel(label: string): string[] {
  const words = label.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const piece = word.length > MAX_LINE_CHARS ? `${word.slice(0, MAX_LINE_CHARS - 1)}…` : word;
    if (!current) current = piece;
    else if (current.length + 1 + piece.length <= MAX_LINE_CHARS) current = `${current} ${piece}`;
    else {
      lines.push(current);
      current = piece;
    }
  }
  if (current) lines.push(current);
  if (lines.length > 3) {
    const kept = lines.slice(0, 3);
    kept[2] = `${kept[2].slice(0, MAX_LINE_CHARS - 1)}…`;
    return kept;
  }
  return lines.length ? lines : [label];
}

function size(node: DiagramNode, lines: string[]): { w: number; h: number } {
  const longest = Math.max(...lines.map((line) => line.length));
  const w = Math.min(NODE_MAX_W, Math.max(NODE_MIN_W, longest * CHAR + 28));
  const h = 18 + lines.length * LINE;
  // A diamond's text sits in its middle half, so the shape is drawn larger.
  return node.shape === "diamond" ? { w: w + 36, h: h + 24 } : { w, h };
}

/** Each layer's ids, in barycentre order. */
export function orderLayers(nodes: DiagramNode[], edges: DiagramEdge[]): string[][] {
  const rankOf = new Map(nodes.map((node) => [node.id, node.rank]));
  const depth = Math.max(0, ...nodes.map((node) => node.rank)) + 1;
  const layers: string[][] = Array.from({ length: depth }, () => []);
  for (const node of nodes) layers[node.rank].push(node.id);
  const position = new Map<string, number>();
  layers[0].forEach((id, index) => position.set(id, index));
  for (let rank = 1; rank < depth; rank += 1) {
    const declared = layers[rank];
    const weight = (id: string, fallback: number): number => {
      const from = edges
        .filter((edge) => edge.to === id && (rankOf.get(edge.from) ?? 0) < rank)
        .map((edge) => position.get(edge.from))
        .filter((value): value is number => value !== undefined);
      return from.length ? from.reduce((a, b) => a + b, 0) / from.length : fallback;
    };
    const keyed = declared.map((id, index) => ({ id, index, key: weight(id, index) }));
    keyed.sort((a, b) => a.key - b.key || a.index - b.index);
    layers[rank] = keyed.map((entry) => entry.id);
    layers[rank].forEach((id, index) => position.set(id, index));
  }
  return layers;
}

function point(x: number, y: number): string {
  return `${Math.round(x * 10) / 10} ${Math.round(y * 10) / 10}`;
}

export function layoutDiagram(nodes: DiagramNode[], edges: DiagramEdge[], direction: Direction = "down"): Layout {
  if (!nodes.length) return { width: 0, height: 0, nodes: [], edges: [] };
  const layers = orderLayers(nodes, edges);
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const sized = new Map(
    nodes.map((node) => {
      const lines = wrapLabel(node.label);
      return [node.id, { lines, ...size(node, lines) }];
    }),
  );
  const down = direction === "down";
  // Work in flow coordinates: `along` the direction of reading, `across` it.
  const depthOf = (id: string) => (down ? sized.get(id)!.h : sized.get(id)!.w);
  const breadthOf = (id: string) => (down ? sized.get(id)!.w : sized.get(id)!.h);
  const layerDepth = layers.map((ids) => Math.max(...ids.map(depthOf)));
  const layerBreadth = layers.map(
    (ids) => ids.reduce((sum, id) => sum + breadthOf(id), 0) + SIBLING_GAP * Math.max(0, ids.length - 1),
  );
  const rankOf = (id: string) => byId.get(id)!.rank;
  // An arrow back to an earlier layer goes round the high side; an arrow that
  // skips a layer goes round the low side. Each gets its own lane, so two of
  // them never share a line, and neither crosses a box it passes.
  //
  // The side is chosen so the arrow leaves its box where no sibling is in the
  // way: a box at the high end of its layer goes high, at the low end low;
  // otherwise a loop back goes high and a skip goes low.
  const place = new Map<string, { index: number; count: number }>();
  layers.forEach((ids) => ids.forEach((id, index) => place.set(id, { index, count: ids.length })));
  const sideOf = new Map<DiagramEdge, 1 | -1>();
  for (const edge of edges) {
    const span = rankOf(edge.to) - rankOf(edge.from);
    if (span === 1) continue;
    const { index, count } = place.get(edge.from)!;
    const last = index === count - 1;
    const first = index === 0;
    const preferred: 1 | -1 = span <= 0 ? 1 : -1;
    sideOf.set(edge, last && !first ? 1 : first && !last ? -1 : preferred);
  }
  const onSide = (side: 1 | -1) => [...sideOf.values()].filter((value) => value === side).length;
  const swingFor = (count: number) => (count ? BACK_SWING + LANE * (count - 1) + 8 : 0);
  const lowSwing = swingFor(onSide(-1));
  const highSwing = swingFor(onSide(1));
  const breadth = Math.max(...layerBreadth);

  type Box = { node: DiagramNode; lines: string[]; along: number; across: number; depth: number; breadth: number };
  const boxes = new Map<string, Box>();
  let along = MARGIN;
  layers.forEach((ids, rank) => {
    let across = MARGIN + lowSwing + (breadth - layerBreadth[rank]) / 2;
    for (const id of ids) {
      boxes.set(id, {
        node: byId.get(id)!,
        lines: sized.get(id)!.lines,
        along: along + layerDepth[rank] / 2,
        across: across + breadthOf(id) / 2,
        depth: depthOf(id),
        breadth: breadthOf(id),
      });
      across += breadthOf(id) + SIBLING_GAP;
    }
    along += layerDepth[rank] + LAYER_GAP;
  });
  const totalAlong = along - LAYER_GAP + MARGIN;
  const totalAcross = breadth + MARGIN * 2 + lowSwing + highSwing;

  const xy = (a: number, c: number): [number, number] => (down ? [c, a] : [a, c]);
  const at = (a: number, c: number) => point(...xy(a, c));
  /** The boxes in the layers an edge spans, inclusive. */
  const spanned = (low: number, high: number) =>
    [...boxes.values()].filter((box) => box.node.rank >= low && box.node.rank <= high);

  const lanes = { [1]: 0, [-1]: 0 } as Record<1 | -1, number>;
  const routed = edges.map((edge): PlacedEdge => {
    const a = boxes.get(edge.from)!;
    const b = boxes.get(edge.to)!;
    const span = b.node.rank - a.node.rank;
    if (span === 1) {
      const start = { a: a.along + a.depth / 2, c: a.across };
      const end = { a: b.along - b.depth / 2 - 2, c: b.across };
      const bend = (end.a - start.a) / 2;
      const [lx, ly] = xy((start.a + end.a) / 2, (start.c + end.c) / 2);
      return {
        ...edge,
        back: false,
        path: `M ${at(start.a, start.c)} C ${at(start.a + bend, start.c)} ${at(end.a - bend, end.c)} ${at(end.a, end.c)}`,
        lx,
        ly,
      };
    }
    const back = span <= 0;
    const passed = back ? spanned(b.node.rank, a.node.rank) : spanned(a.node.rank, b.node.rank);
    const side = sideOf.get(edge)!;
    const lane = lanes[side]++;
    const out =
      side === 1
        ? Math.max(...passed.map((box) => box.across + box.breadth / 2)) + BACK_SWING + LANE * lane
        : Math.min(...passed.map((box) => box.across - box.breadth / 2)) - BACK_SWING - LANE * lane;
    // Leave a box a little after its middle and enter one a little before, so
    // an arrow arriving and an arrow leaving on the same side never share a point.
    const start = { a: a.along + 6, c: a.across + (side * a.breadth) / 2 };
    const end = { a: b.along - 6, c: b.across + side * (b.breadth / 2 + 2) };
    // The curve's midpoint (t = ½), where its label sits.
    const [lx, ly] = xy((start.a + end.a) / 2, (start.c + end.c) / 8 + (out * 3) / 4);
    return {
      ...edge,
      back,
      path: `M ${at(start.a, start.c)} C ${at(start.a, out)} ${at(end.a, out)} ${at(end.a, end.c)}`,
      lx,
      ly,
    };
  });

  const placed: PlacedNode[] = [...boxes.values()].map((box) => {
    const [x, y] = xy(box.along, box.across);
    const { w, h } = sized.get(box.node.id)!;
    return { ...box.node, lines: box.lines, x, y, w, h };
  });
  const [width, height] = down ? [totalAcross, totalAlong] : [totalAlong, totalAcross];
  return { width: Math.ceil(width), height: Math.ceil(height), nodes: placed, edges: routed };
}
