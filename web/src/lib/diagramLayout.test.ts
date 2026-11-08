/*
 * QUI-A08 — the diagram's layout is a pure function of the runtime's ranks.
 */
import { describe, expect, it } from "vitest";
import { layoutDiagram, orderLayers, wrapLabel, type DiagramEdge, type DiagramNode } from "./diagramLayout";

const NODES: DiagramNode[] = [
  { id: "start", label: "Start", shape: "round", rank: 0 },
  { id: "ok", label: "Password right?", shape: "diamond", rank: 1 },
  { id: "code", label: "Ask for the code", shape: "box", rank: 2 },
  { id: "in", label: "Signed in", shape: "round", rank: 3 },
];
const EDGES: DiagramEdge[] = [
  { from: "start", to: "ok", label: "" },
  { from: "ok", to: "code", label: "yes" },
  { from: "ok", to: "start", label: "no" },
  { from: "code", to: "in", label: "" },
];

describe("diagram layout (QUI-A08)", () => {
  it("puts each layer below the last when the diagram reads down", () => {
    const layout = layoutDiagram(NODES, EDGES, "down");
    const ys = layout.nodes.map((node) => node.y);
    expect([...ys].sort((a, b) => a - b)).toEqual(ys);
    expect(new Set(layout.nodes.map((node) => node.x)).size).toBe(1);
    // Every box is inside the drawing.
    for (const node of layout.nodes) {
      expect(node.x - node.w / 2).toBeGreaterThanOrEqual(0);
      expect(node.x + node.w / 2).toBeLessThanOrEqual(layout.width);
      expect(node.y + node.h / 2).toBeLessThanOrEqual(layout.height);
    }
  });

  it("draws a loop back as a back edge, and forward edges as forward", () => {
    const layout = layoutDiagram(NODES, EDGES, "down");
    expect(layout.edges.filter((edge) => edge.back).map((edge) => `${edge.from}>${edge.to}`)).toEqual(["ok>start"]);
    expect(layout.edges.every((edge) => edge.path.startsWith("M "))).toBe(true);
  });

  it("routes an arrow that skips a layer round the boxes it passes, not through them", () => {
    const nodes: DiagramNode[] = [
      { id: "ci", label: "CI passed?", shape: "diamond", rank: 0 },
      { id: "review", label: "Code review with a long name", shape: "box", rank: 1 },
      { id: "fix", label: "Update the code", shape: "box", rank: 2 },
    ];
    const edges: DiagramEdge[] = [
      { from: "ci", to: "review", label: "pass" },
      { from: "review", to: "fix", label: "" },
      { from: "ci", to: "fix", label: "fail" },
    ];
    const layout = layoutDiagram(nodes, edges, "down");
    const review = layout.nodes.find((node) => node.id === "review")!;
    const skip = layout.edges.find((edge) => edge.from === "ci" && edge.to === "fix")!;
    expect(skip.back).toBe(false);
    // Its label, at the curve's middle, sits left of the box in the layer it skips.
    expect(skip.lx).toBeLessThan(review.x - review.w / 2);
    expect(skip.lx).toBeGreaterThan(0);
  });

  it("gives two loop-backs their own lanes outside every box they pass", () => {
    const layout = layoutDiagram(NODES, [...EDGES, { from: "in", to: "ok", label: "again" }], "down");
    const backs = layout.edges.filter((edge) => edge.back);
    expect(backs).toHaveLength(2);
    const widest = Math.max(...layout.nodes.map((node) => node.x + node.w / 2));
    for (const edge of backs) expect(edge.lx).toBeGreaterThan(widest);
    expect(backs[0].lx).not.toBe(backs[1].lx);
    expect(Math.max(...backs.map((edge) => edge.lx))).toBeLessThan(layout.width);
  });

  it("sends a loop back round the side where its box has no sibling in the way", () => {
    const nodes: DiagramNode[] = [
      { id: "ci", label: "CI runs", shape: "box", rank: 0 },
      { id: "fix", label: "Update code", shape: "box", rank: 1 },
      { id: "ok", label: "Approve", shape: "box", rank: 1 },
    ];
    const edges: DiagramEdge[] = [
      { from: "ci", to: "fix", label: "" },
      { from: "ci", to: "ok", label: "" },
      { from: "fix", to: "ci", label: "again" },
    ];
    const layout = layoutDiagram(nodes, edges, "down");
    const fix = layout.nodes.find((node) => node.id === "fix")!;
    const ok = layout.nodes.find((node) => node.id === "ok")!;
    expect(fix.x).toBeLessThan(ok.x);
    const back = layout.edges.find((edge) => edge.back)!;
    // Update code is on the left of its layer, so the loop goes round the left.
    expect(back.lx).toBeLessThan(fix.x - fix.w / 2);
  });

  it("puts layers side by side when the diagram reads right", () => {
    const layout = layoutDiagram(NODES, EDGES, "right");
    const xs = layout.nodes.map((node) => node.x);
    expect([...xs].sort((a, b) => a - b)).toEqual(xs);
    expect(layout.width).toBeGreaterThan(layout.height);
  });

  it("orders a layer by where its arrows come from, and keeps the written order on a tie", () => {
    const nodes: DiagramNode[] = [
      { id: "a", label: "A", shape: "box", rank: 0 },
      { id: "b", label: "B", shape: "box", rank: 0 },
      { id: "x", label: "From B", shape: "box", rank: 1 },
      { id: "y", label: "From A", shape: "box", rank: 1 },
      { id: "z", label: "Alone", shape: "box", rank: 1 },
    ];
    const edges: DiagramEdge[] = [
      { from: "b", to: "x", label: "" },
      { from: "a", to: "y", label: "" },
    ];
    expect(orderLayers(nodes, edges)).toEqual([["a", "b"], ["y", "x", "z"]]);
  });

  it("wraps a long label into at most three lines of whole words", () => {
    expect(wrapLabel("Short")).toEqual(["Short"]);
    const lines = wrapLabel("Check the signature against the pinned publisher and then the leaf key hash too");
    expect(lines).toHaveLength(3);
    expect(lines.every((line) => line.length <= 22)).toBe(true);
    expect(lines[2].endsWith("…")).toBe(true);
  });
});
