/**
 * Raiker Design's structured documents, as the canvas reads them (DW-01 to DW-12).
 *
 * The server owns the document: every change is a typed operation it applies
 * and versions. What lives here is the reading side — walking the layer tree,
 * naming things for people, building the operation a gesture means — so the
 * component stays about layout and the rules stay testable.
 */

export type DesignNodeType = "text" | "rect" | "ellipse" | "image" | "group" | "stack";

export interface DesignNode {
  id: string;
  type: DesignNodeType;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  rotation: number;
  visible: boolean;
  locked: boolean;
  opacity: number;
  created_by: "owner" | "agent";
  children?: DesignNode[];
  text?: string;
  color?: string | null;
  color_var?: string | null;
  font_family?: string;
  font_var?: string | null;
  font_size?: number;
  font_weight?: number;
  align?: string;
  line_height?: number;
  fill?: string | null;
  fill_var?: string | null;
  stroke?: string | null;
  stroke_width?: number;
  radius?: number;
  asset_id?: string | null;
  alt?: string;
  fit?: "cover" | "contain" | "fill";
  crop?: { x: number; y: number; w: number; h: number } | null;
  direction?: "row" | "column";
  gap?: number;
  padding?: number;
  component_id?: string | null;
}

/** DW-06 — a reusable layer tree kept in the document, drawn from (0, 0). */
export interface DesignComponent {
  name: string;
  nodes: DesignNode[];
}

/** DW-08 — a note on a layer or a frame. Versioned like any change; never drawn into an export. */
export interface DesignNote {
  id: string;
  target: string;
  text: string;
  author: "owner" | "agent";
  resolved: boolean;
}

export interface DesignFrame {
  id: string;
  name: string;
  preset: string;
  width: number;
  height: number;
  background: string | null;
  background_var?: string | null;
  grid: { size: number; visible: boolean };
  variant_of: string | null;
  nodes: DesignNode[];
}

export interface DesignDocumentBody {
  schema: number;
  frames: DesignFrame[];
  system?: { id: string; version: number };
  components: Record<string, DesignComponent>;
  notes: DesignNote[];
}

export type DesignOperation = Record<string, unknown> & { op: string };

/** The document body the API sends, typed for the canvas. */
export function documentBody(raw: Record<string, unknown> | undefined | null): DesignDocumentBody {
  const frames = Array.isArray(raw?.frames) ? (raw!.frames as DesignFrame[]) : [];
  const components = (raw?.components ?? {}) as Record<string, DesignComponent>;
  const notes = Array.isArray(raw?.notes) ? (raw!.notes as DesignNote[]) : [];
  return { schema: Number(raw?.schema ?? 1), frames, system: raw?.system as DesignDocumentBody["system"], components, notes };
}

export interface LayerRow {
  node: DesignNode;
  depth: number;
  parentId: string | null;
}

/** Every layer in a frame, front-most first — the order a layer panel reads in. */
export function layerRows(nodes: readonly DesignNode[], depth = 0, parentId: string | null = null): LayerRow[] {
  const rows: LayerRow[] = [];
  for (const node of [...nodes].reverse()) {
    rows.push({ node, depth, parentId });
    if (node.children) rows.push(...layerRows(node.children, depth + 1, node.id));
  }
  return rows;
}

export function findNode(nodes: readonly DesignNode[], id: string | null): DesignNode | null {
  if (id === null) return null;
  for (const node of nodes) {
    if (node.id === id) return node;
    const inner = node.children ? findNode(node.children, id) : null;
    if (inner) return inner;
  }
  return null;
}

/** Where a node sits among its siblings: the parent (null at frame root), the index and the count. */
export function siblingPosition(
  nodes: readonly DesignNode[],
  id: string,
  parentId: string | null = null,
): { parentId: string | null; index: number; count: number } | null {
  const at = nodes.findIndex((node) => node.id === id);
  if (at >= 0) return { parentId, index: at, count: nodes.length };
  for (const node of nodes) {
    if (node.children) {
      const inner = siblingPosition(node.children, id, node.id);
      if (inner) return inner;
    }
  }
  return null;
}

/** Every id in the document, so a new one never repeats. */
export function allIds(document: DesignDocumentBody): Set<string> {
  const ids = new Set<string>();
  const walk = (nodes: readonly DesignNode[]) => {
    for (const node of nodes) {
      ids.add(node.id);
      if (node.children) walk(node.children);
    }
  };
  for (const frame of document.frames) {
    ids.add(frame.id);
    walk(frame.nodes);
  }
  for (const id of Object.keys(document.components)) ids.add(id);
  for (const note of document.notes) ids.add(note.id);
  return ids;
}

/** `text-3`, `rect-2`… — a readable id that is not already taken. */
export function freshId(base: string, taken: Set<string>): string {
  const stem = base.toLowerCase().replace(/[^a-z0-9_-]/g, "-").replace(/^[^a-z]+/, "") || "layer";
  let counter = 1;
  let candidate = `${stem}-${counter}`;
  while (taken.has(candidate)) {
    counter += 1;
    candidate = `${stem}-${counter}`;
  }
  return candidate.slice(0, 48);
}

const NEW_LAYER: Record<"text" | "rect" | "ellipse" | "stack", Partial<DesignNode>> = {
  text: { name: "Text", text: "Your headline", w: 480, h: 72, font_size: 48, font_weight: 700, color: "#111111" },
  rect: { name: "Rectangle", w: 240, h: 160, fill: "#d9d9d9" },
  ellipse: { name: "Ellipse", w: 200, h: 200, fill: "#d9d9d9" },
  stack: { name: "Stack", w: 400, h: 300, direction: "column", gap: 16, padding: 16 },
};

/** The operation that adds one new layer near the middle of the frame. */
export function addLayerOperation(
  frame: DesignFrame,
  kind: "text" | "rect" | "ellipse" | "stack",
  taken: Set<string>,
): { op: DesignOperation; id: string } {
  const preset = NEW_LAYER[kind];
  const id = freshId(kind, taken);
  const w = Number(preset.w);
  const h = Number(preset.h);
  return {
    id,
    op: {
      op: "add_node",
      frame_id: frame.id,
      node: { id, type: kind, ...preset, x: Math.round((frame.width - w) / 2), y: Math.round((frame.height - h) / 2) },
    },
  };
}

/** Place an image from the owner's gallery, linked to it rather than copied (DW-05). */
export function placeImageOperation(
  frame: DesignFrame,
  assetId: string,
  taken: Set<string>,
): { op: DesignOperation; id: string } {
  const id = freshId("image", taken);
  const w = Math.round(Math.min(frame.width, frame.height) * 0.5);
  return {
    id,
    op: {
      op: "add_node",
      frame_id: frame.id,
      node: { id, type: "image", name: "Image", asset_id: assetId, alt: "", fit: "cover", x: Math.round((frame.width - w) / 2), y: Math.round((frame.height - w) / 2), w, h: w },
    },
  };
}

/** Arrow-key nudge: 1px, or 10 with Shift. */
export function nudge(node: DesignNode, key: string, shift: boolean): DesignOperation | null {
  const step = shift ? 10 : 1;
  const delta: Record<string, [number, number]> = {
    ArrowLeft: [-step, 0],
    ArrowRight: [step, 0],
    ArrowUp: [0, -step],
    ArrowDown: [0, step],
  };
  const move = delta[key];
  if (!move || node.locked) return null;
  return { op: "update_node", node_id: node.id, set: { x: node.x + move[0], y: node.y + move[1] } };
}

/** Bring forward / send backward within the same parent. */
export function reorderOperation(
  document: DesignDocumentBody,
  frame: DesignFrame,
  id: string,
  direction: "forward" | "backward" | "front" | "back",
): DesignOperation | null {
  const at = siblingPosition(frame.nodes, id);
  if (!at) return null;
  const target =
    direction === "front" ? at.count - 1 : direction === "back" ? 0 : at.index + (direction === "forward" ? 1 : -1);
  if (target < 0 || target >= at.count || target === at.index) return null;
  void document;
  return { op: "move_node", node_id: id, parent_id: at.parentId, index: target };
}

/** Plain words for a refusal code the Design routes answer with. */
export function designReason(code: string | null | undefined): string {
  if (!code) return "That change was refused.";
  const [head, detail] = code.split(":");
  const words: Record<string, string> = {
    design_version_conflict: "This design changed since you loaded it. It has been refreshed — make the change again.",
    design_version_unknown: "That version does not exist yet. Reload the design.",
    node_locked: "That layer is locked. Unlock it first.",
    unknown_node: "That layer no longer exists.",
    unknown_frame: "That frame no longer exists.",
    invalid_color: "Colours are written as #rrggbb.",
    field_out_of_range: "That value is outside what a layer can hold.",
    too_many_nodes: "This design has reached its layer limit.",
    too_many_frames: "This design has reached its frame limit.",
    document_needs_a_frame: "A design keeps at least one frame.",
    nothing_to_undo: "There is nothing to undo.",
    nothing_to_redo: "There is nothing to redo.",
    design_proposal_unreadable: "The model did not answer with operations Raiker can read. Nothing was changed.",
    design_proposal_model_required: "Choose a model for the design agent first.",
    design_proposal_profile_unknown: "That model is not connected. Choose another one.",
    design_proposal_provider_error: "The model's provider returned an error. Nothing was changed.",
    design_proposal_cannot_apply: "Those changes depend on ones you left out. Include them or reject the proposal.",
    design_proposal_all_conflicting: "Every selected change meets a layer you changed since. Nothing was applied.",
    group_needs_siblings: "Only layers with the same parent can be grouped.",
    unknown_component: "That component is no longer in this design.",
    not_an_instance: "That layer is not placed from a component.",
    invalid_component_id: "That component name is taken. Choose another.",
    too_many_components: "This design has reached its component limit.",
    unknown_note_target: "That layer no longer exists, so the note has nothing to sit on.",
    empty_note: "Write something in the note first.",
    unknown_note: "That note no longer exists.",
    too_many_notes: "This design has reached its note limit.",
    content_does_not_match_media_type: "That file is not the kind of picture its name says. Use a PNG, JPEG, WebP or GIF.",
    unsupported_media_type: "Only PNG, JPEG, WebP and GIF pictures can be imported.",
    attachment_too_large: "That picture is too large to import.",
    empty_attachment: "That file is empty.",
    invalid_base64: "That file could not be read.",
    unknown_design_asset: "That picture is not one of yours, or it is in Recently deleted.",
    design_asset_unreadable: "That picture could not be read.",
    design_proposal_interrupted: "The request to the model did not finish. Nothing was changed.",
    export_too_large: "That export would be too large. Try a smaller scale.",
    unknown_project: "That project is not one of yours.",
    unknown_design_system: "That design system no longer exists.",
    invalid_variable_value: "A design-system value is not valid (colours as #rrggbb, fonts as a family name).",
  };
  const said = words[head];
  if (said) return detail && head === "design_proposal_provider_error" ? `${said} (${detail})` : said;
  return code;
}

/* ── Direct manipulation (DW-02) ───────────────────────────────────────── */

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

const round2 = (value: number) => Math.round(value * 100) / 100;

/** The selected layers that are not inside another selected layer: moving a group already moves its children. */
export function topLevelSelection(frameNodes: readonly DesignNode[], ids: readonly string[]): DesignNode[] {
  const wanted = new Set(ids);
  const out: DesignNode[] = [];
  const walk = (nodes: readonly DesignNode[], covered: boolean) => {
    for (const node of nodes) {
      const hit = wanted.has(node.id) && !covered;
      if (hit) out.push(node);
      if (node.children) walk(node.children, covered || hit);
    }
  };
  walk(frameNodes, false);
  return out;
}

/** One version for a whole gesture: every moved, unlocked layer in one operation list. */
export function moveOperations(nodes: readonly DesignNode[], dx: number, dy: number): DesignOperation[] {
  if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) return [];
  return nodes
    .filter((node) => !node.locked)
    .map((node) => ({ op: "update_node", node_id: node.id, set: { x: round2(node.x + dx), y: round2(node.y + dy) } }));
}

export type Handle = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";
export const HANDLES: readonly Handle[] = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];

/** Where a resize handle sits on a box. */
export function handlePoint(box: Box, handle: Handle): { x: number; y: number } {
  const x = handle.includes("w") ? box.x : handle.includes("e") ? box.x + box.w : box.x + box.w / 2;
  const y = handle.includes("n") ? box.y : handle.includes("s") ? box.y + box.h : box.y + box.h / 2;
  return { x, y };
}

/**
 * The box after dragging *handle* by (dx, dy) in the layer's own axes. The
 * opposite edge stays put; a box never turns inside out or shrinks below 1px.
 * With *keepRatio* a corner handle keeps the box's proportions.
 */
export function resizeBox(box: Box, handle: Handle, dx: number, dy: number, keepRatio = false): Box {
  let { x, y, w, h } = box;
  if (handle.includes("e")) w = Math.max(1, box.w + dx);
  if (handle.includes("s")) h = Math.max(1, box.h + dy);
  if (handle.includes("w")) {
    w = Math.max(1, box.w - dx);
    x = box.x + box.w - w;
  }
  if (handle.includes("n")) {
    h = Math.max(1, box.h - dy);
    y = box.y + box.h - h;
  }
  if (keepRatio && handle.length === 2 && box.w > 0 && box.h > 0) {
    const ratio = box.w / box.h;
    if (w / h > ratio) w = h * ratio;
    else h = w / ratio;
    if (handle.includes("w")) x = box.x + box.w - w;
    if (handle.includes("n")) y = box.y + box.h - h;
  }
  return { x: round2(x), y: round2(y), w: round2(w), h: round2(h) };
}

/** Rotate a pointer delta into a layer's own axes, so a rotated layer resizes along its sides. */
export function toLocalDelta(dx: number, dy: number, rotation: number): [number, number] {
  const angle = (-rotation * Math.PI) / 180;
  return [dx * Math.cos(angle) - dy * Math.sin(angle), dx * Math.sin(angle) + dy * Math.cos(angle)];
}

/** The rotation a pointer at (px, py) gives a layer centred at (cx, cy); Shift snaps to 15°. */
export function rotationFromPointer(cx: number, cy: number, px: number, py: number, snap: boolean): number {
  let degrees = (Math.atan2(py - cy, px - cx) * 180) / Math.PI + 90;
  if (degrees > 180) degrees -= 360;
  if (snap) degrees = Math.round(degrees / 15) * 15;
  if (degrees <= -180) degrees += 360;
  return round2(degrees);
}

export type Alignment = "left" | "center" | "right" | "top" | "middle" | "bottom";

/** Line the layers up on one edge or centre: of their shared box, or of the frame for a single layer. */
export function alignOperations(nodes: readonly DesignNode[], how: Alignment, frame: Box | null = null): DesignOperation[] {
  const movable = nodes.filter((node) => !node.locked);
  if (movable.length === 0) return [];
  const area: Box =
    nodes.length === 1 && frame
      ? frame
      : (() => {
          const left = Math.min(...nodes.map((n) => n.x));
          const top = Math.min(...nodes.map((n) => n.y));
          return { x: left, y: top, w: Math.max(...nodes.map((n) => n.x + n.w)) - left, h: Math.max(...nodes.map((n) => n.y + n.h)) - top };
        })();
  const ops: DesignOperation[] = [];
  for (const node of movable) {
    const set: Record<string, number> = {};
    if (how === "left") set.x = area.x;
    if (how === "center") set.x = area.x + (area.w - node.w) / 2;
    if (how === "right") set.x = area.x + area.w - node.w;
    if (how === "top") set.y = area.y;
    if (how === "middle") set.y = area.y + (area.h - node.h) / 2;
    if (how === "bottom") set.y = area.y + area.h - node.h;
    const [key, value] = Object.entries(set)[0];
    if (Math.abs((node as unknown as Record<string, number>)[key] - value) > 0.01) {
      ops.push({ op: "update_node", node_id: node.id, set: { [key]: round2(value) } });
    }
  }
  return ops;
}

/** Equal gaps between three or more layers, the outermost two staying where they are. */
export function distributeOperations(nodes: readonly DesignNode[], axis: "horizontal" | "vertical"): DesignOperation[] {
  if (nodes.length < 3) return [];
  const along = axis === "horizontal" ? ("x" as const) : ("y" as const);
  const size = axis === "horizontal" ? ("w" as const) : ("h" as const);
  const sorted = [...nodes].sort((a, b) => a[along] - b[along]);
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const span = last[along] + last[size] - first[along];
  const used = sorted.reduce((total, node) => total + node[size], 0);
  const gap = (span - used) / (sorted.length - 1);
  const ops: DesignOperation[] = [];
  let cursor = first[along] + first[size] + gap;
  for (const node of sorted.slice(1, -1)) {
    if (!node.locked && Math.abs(node[along] - cursor) > 0.01) {
      ops.push({ op: "update_node", node_id: node.id, set: { [along]: round2(cursor) } });
    }
    cursor += node[size] + gap;
  }
  return ops;
}

export interface Guide {
  axis: "x" | "y";
  at: number;
}

/**
 * Snap a moving box to the frame's edges and centre, to other layers' edges and
 * centres, and to the grid when it is shown. Within *threshold* (frame units)
 * the nearest line wins on each axis, and the lines that matched are returned
 * as guides to draw.
 */
export function snapMove(
  box: Box,
  dx: number,
  dy: number,
  frame: Box,
  others: readonly Box[],
  threshold: number,
  grid = 0,
): { dx: number; dy: number; guides: Guide[] } {
  const lines = (axis: "x" | "y") => {
    const start = axis === "x" ? "x" : "y";
    const size = axis === "x" ? "w" : "h";
    const out = [frame[start], frame[start] + frame[size] / 2, frame[start] + frame[size]];
    for (const other of others) out.push(other[start], other[start] + other[size] / 2, other[start] + other[size]);
    return out;
  };
  const guides: Guide[] = [];
  const solve = (axis: "x" | "y", delta: number): number => {
    const start = axis === "x" ? box.x : box.y;
    const size = axis === "x" ? box.w : box.h;
    const edges = [start + delta, start + delta + size / 2, start + delta + size];
    let best: { shift: number; at: number } | null = null;
    for (const line of lines(axis)) {
      for (const edge of edges) {
        const shift = line - edge;
        if (Math.abs(shift) <= threshold && (best === null || Math.abs(shift) < Math.abs(best.shift))) best = { shift, at: line };
      }
    }
    if (best !== null) {
      guides.push({ axis, at: best.at });
      return delta + best.shift;
    }
    if (grid > 0) return Math.round((start + delta) / grid) * grid - start;
    return delta;
  };
  return { dx: round2(solve("x", dx)), dy: round2(solve("y", dy)), guides };
}

/* ── Components (DW-06) ──────────────────────────────────────────────────── */

function shapeOf(nodes: readonly DesignNode[], originX: number, originY: number): unknown[] {
  return nodes.map((node) => {
    const rest: Record<string, unknown> = { ...node, x: round2(node.x - originX), y: round2(node.y - originY) };
    delete rest.id;
    delete rest.created_by;
    delete rest.children;
    return { ...rest, children: node.children ? shapeOf(node.children, originX, originY) : undefined };
  });
}

/** True when an instance's layers no longer match its component (ids and position aside). */
export function instanceOutOfDate(instance: DesignNode, component: DesignComponent | undefined): boolean {
  if (!component) return false;
  return JSON.stringify(shapeOf(instance.children ?? [], instance.x, instance.y)) !== JSON.stringify(shapeOf(component.nodes, 0, 0));
}

/** What a validation status looks like in words, never colour alone. */
export const CHECK_STATUS: Record<string, string> = {
  pass: "Passed",
  fail: "Failed",
  unsupported: "Not supported by the export",
  unknown: "Cannot be known from the design",
};

/** The version kinds a history row names. */
export function versionKind(kind: string, actor: string): string {
  const words: Record<string, string> = {
    create: "Created",
    edit: "Edit",
    undo: "Undo",
    redo: "Redo",
    restore: "Went back",
    system: "Design system",
    proposal: "Agent proposal accepted",
  };
  return `${words[kind] ?? kind}${actor === "agent" && kind !== "proposal" ? " (agent)" : ""}`;
}
