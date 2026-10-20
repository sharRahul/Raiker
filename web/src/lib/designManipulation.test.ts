import { describe, expect, it } from "vitest";
import {
  alignOperations,
  distributeOperations,
  documentBody,
  handlePoint,
  instanceOutOfDate,
  moveOperations,
  resizeBox,
  rotationFromPointer,
  snapMove,
  toLocalDelta,
  topLevelSelection,
  type DesignNode,
} from "./designDocument";

function node(partial: Partial<DesignNode>): DesignNode {
  return {
    id: "n", type: "rect", name: "Rect", x: 0, y: 0, w: 10, h: 10, rotation: 0,
    visible: true, locked: false, opacity: 1, created_by: "owner", ...partial,
  };
}

describe("pointer gestures (DW-02)", () => {
  it("moves every unlocked top-level layer in one operation list", () => {
    const child = node({ id: "c", x: 5, y: 5 });
    const group = node({ id: "g", type: "group", children: [child] });
    const locked = node({ id: "l", locked: true });
    const top = topLevelSelection([group, locked], ["g", "c", "l"]);
    expect(top.map((n) => n.id)).toEqual(["g", "l"]);
    expect(moveOperations(top, 12, -3)).toEqual([{ op: "update_node", node_id: "g", set: { x: 12, y: -3 } }]);
    expect(moveOperations(top, 0, 0)).toEqual([]);
  });

  it("keeps the opposite edge when resizing and never turns a box inside out", () => {
    const box = { x: 100, y: 100, w: 200, h: 100 };
    expect(resizeBox(box, "se", 50, 20)).toEqual({ x: 100, y: 100, w: 250, h: 120 });
    expect(resizeBox(box, "nw", 50, 20)).toEqual({ x: 150, y: 120, w: 150, h: 80 });
    expect(resizeBox(box, "w", 500, 0)).toEqual({ x: 299, y: 100, w: 1, h: 100 });
    expect(resizeBox(box, "se", 100, 0, true)).toEqual({ x: 100, y: 100, w: 200, h: 100 });
    expect(resizeBox(box, "se", 100, 100, true)).toEqual({ x: 100, y: 100, w: 300, h: 150 });
    expect(handlePoint(box, "ne")).toEqual({ x: 300, y: 100 });
  });

  it("resizes a rotated layer along its own sides", () => {
    const [x, y] = toLocalDelta(0, 10, 90);
    expect(Math.round(x)).toBe(10);
    expect(Math.round(y)).toBe(0);
  });

  it("turns a pointer into a rotation and snaps to 15° with Shift", () => {
    expect(rotationFromPointer(0, 0, 0, -10, false)).toBe(0);
    expect(rotationFromPointer(0, 0, 10, 0, false)).toBe(90);
    expect(rotationFromPointer(0, 0, 10, -9, true)).toBe(45);
    expect(rotationFromPointer(0, 0, -10, 0, false)).toBe(-90);
  });
});

describe("align and distribute", () => {
  const a = node({ id: "a", x: 10, y: 10, w: 20, h: 20 });
  const b = node({ id: "b", x: 50, y: 40, w: 40, h: 10 });
  const c = node({ id: "c", x: 200, y: 0, w: 10, h: 10 });

  it("aligns to the selection's shared box, or to the frame for one layer", () => {
    expect(alignOperations([a, b], "left")).toEqual([{ op: "update_node", node_id: "b", set: { x: 10 } }]);
    expect(alignOperations([a, b], "bottom")).toEqual([{ op: "update_node", node_id: "a", set: { y: 30 } }]);
    expect(alignOperations([a], "center", { x: 0, y: 0, w: 100, h: 100 })).toEqual([
      { op: "update_node", node_id: "a", set: { x: 40 } },
    ]);
    expect(alignOperations([node({ locked: true })], "left")).toEqual([]);
  });

  it("spaces three or more layers evenly, the outer two staying put", () => {
    expect(distributeOperations([a, b], "horizontal")).toEqual([]);
    expect(distributeOperations([c, a, b], "horizontal")).toEqual([
      { op: "update_node", node_id: "b", set: { x: 95 } },
    ]);
  });
});

describe("snapping", () => {
  const frame = { x: 0, y: 0, w: 1000, h: 1000 };

  it("snaps an edge or centre to the frame and to other layers, and names the guide", () => {
    const moved = snapMove({ x: 100, y: 100, w: 100, h: 100 }, 296, 3, frame, [], 6);
    expect(moved.dx).toBe(300); // centre 450 → 500
    expect(moved.guides).toContainEqual({ axis: "x", at: 500 });
    const toOther = snapMove({ x: 0, y: 300, w: 50, h: 50 }, 0, 47, frame, [{ x: 600, y: 400, w: 10, h: 10 }], 6);
    expect(toOther.dy).toBe(50);
    expect(toOther.guides).toEqual([{ axis: "x", at: 0 }, { axis: "y", at: 400 }]);
  });

  it("falls back to the grid, and leaves a free move alone", () => {
    expect(snapMove({ x: 100, y: 100, w: 30, h: 30 }, 23, 0, frame, [], 2, 8)).toMatchObject({ dx: 20 });
    expect(snapMove({ x: 100, y: 100, w: 30, h: 30 }, 23, 0, frame, [], 2, 0)).toMatchObject({ dx: 23 });
  });
});

describe("components and notes in the document body", () => {
  it("reads components and notes, defaulting to none", () => {
    expect(documentBody({ frames: [] })).toMatchObject({ components: {}, notes: [] });
  });

  it("says when an instance no longer matches its component", () => {
    const component = { name: "Card", nodes: [node({ id: "bg", x: 0, y: 0, w: 100, h: 50 })] };
    const fresh = node({ id: "i", type: "group", x: 300, y: 200, w: 100, h: 50, component_id: "card",
      children: [node({ id: "i-bg", x: 300, y: 200, w: 100, h: 50 })] });
    expect(instanceOutOfDate(fresh, component)).toBe(false);
    const edited = { ...fresh, children: [node({ id: "i-bg", x: 300, y: 200, w: 120, h: 50 })] };
    expect(instanceOutOfDate(edited, component)).toBe(true);
    expect(instanceOutOfDate(fresh, undefined)).toBe(false);
  });
});
