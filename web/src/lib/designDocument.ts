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
}

export type DesignOperation = Record<string, unknown> & { op: string };

/** The document body the API sends, typed for the canvas. */
export function documentBody(raw: Record<string, unknown> | undefined | null): DesignDocumentBody {
  const frames = Array.isArray(raw?.frames) ? (raw!.frames as DesignFrame[]) : [];
  return { schema: Number(raw?.schema ?? 1), frames, system: raw?.system as DesignDocumentBody["system"] };
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
    export_too_large: "That export would be too large. Try a smaller scale.",
    unknown_project: "That project is not one of yours.",
    unknown_design_system: "That design system no longer exists.",
    invalid_variable_value: "A design-system value is not valid (colours as #rrggbb, fonts as a family name).",
  };
  const said = words[head];
  if (said) return detail && head === "design_proposal_provider_error" ? `${said} (${detail})` : said;
  return code;
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
