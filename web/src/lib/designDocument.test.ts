import { describe, expect, it } from "vitest";
import {
  addLayerOperation,
  allIds,
  designReason,
  documentBody,
  freshId,
  layerRows,
  nudge,
  placeImageOperation,
  reorderOperation,
  versionKind,
  type DesignFrame,
  type DesignNode,
} from "./designDocument";

function node(partial: Partial<DesignNode>): DesignNode {
  return {
    id: "n",
    type: "rect",
    name: "Rect",
    x: 0,
    y: 0,
    w: 10,
    h: 10,
    rotation: 0,
    visible: true,
    locked: false,
    opacity: 1,
    created_by: "owner",
    ...partial,
  };
}

const FRAME: DesignFrame = {
  id: "frame-1",
  name: "Frame 1",
  preset: "social_square",
  width: 1080,
  height: 1080,
  background: "#ffffff",
  grid: { size: 8, visible: false },
  variant_of: null,
  nodes: [
    node({ id: "back" }),
    node({ id: "g", type: "group", children: [node({ id: "inner" })] }),
    node({ id: "front" }),
  ],
};

describe("the layer panel reads front-most first, with depth", () => {
  it("lists every layer in paint order reversed", () => {
    expect(layerRows(FRAME.nodes).map((row) => [row.node.id, row.depth, row.parentId])).toEqual([
      ["front", 0, null],
      ["g", 0, null],
      ["inner", 1, "g"],
      ["back", 0, null],
    ]);
  });
});

describe("new layers and ids", () => {
  it("never repeats an id", () => {
    const taken = allIds({ schema: 1, frames: [FRAME], components: {}, notes: [] });
    expect(taken.has("inner")).toBe(true);
    expect(freshId("text", new Set(["text-1"]))).toBe("text-2");
    const { op, id } = addLayerOperation(FRAME, "text", taken);
    expect(id).toBe("text-1");
    expect(op).toMatchObject({ op: "add_node", frame_id: "frame-1", node: { id: "text-1", type: "text", x: 300 } });
  });

  it("places a picture as a link to the asset, with empty alternative text to fill in", () => {
    const { op } = placeImageOperation(FRAME, "img_abc", new Set());
    expect(op).toMatchObject({ node: { type: "image", asset_id: "img_abc", alt: "" } });
  });
});

describe("gestures become typed operations", () => {
  it("nudges by one, or ten with Shift, and never a locked layer", () => {
    expect(nudge(node({ x: 5 }), "ArrowRight", false)).toEqual({ op: "update_node", node_id: "n", set: { x: 6, y: 0 } });
    expect(nudge(node({ y: 5 }), "ArrowUp", true)).toEqual({ op: "update_node", node_id: "n", set: { x: 0, y: -5 } });
    expect(nudge(node({ locked: true }), "ArrowRight", false)).toBeNull();
    expect(nudge(node({}), "a", false)).toBeNull();
  });

  it("reorders within the same parent and stops at the ends", () => {
    const body = documentBody({ schema: 1, frames: [FRAME] });
    expect(reorderOperation(body, FRAME, "back", "forward")).toEqual({ op: "move_node", node_id: "back", parent_id: null, index: 1 });
    expect(reorderOperation(body, FRAME, "front", "forward")).toBeNull();
    expect(reorderOperation(body, FRAME, "inner", "front")).toBeNull();
  });
});

describe("refusals and history read as words", () => {
  it("names a conflict and a lock plainly", () => {
    expect(designReason("design_version_conflict:title")).toMatch(/changed since you loaded it/);
    expect(designReason("node_locked:a@0")).toBe("That layer is locked. Unlock it first.");
    expect(designReason("design_proposal_provider_error:quota")).toMatch(/\(quota\)$/);
    expect(designReason("something_new")).toBe("something_new");
  });

  it("says who made a version", () => {
    expect(versionKind("proposal", "agent")).toBe("Agent proposal accepted");
    expect(versionKind("edit", "owner")).toBe("Edit");
  });
});
