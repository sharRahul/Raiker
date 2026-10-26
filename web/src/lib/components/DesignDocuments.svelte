<script lang="ts">
  /**
   * Design → Documents: the structured canvas (DW-01 to DW-12).
   *
   * The Images view is the Asset layer — one picture at a time. This is the
   * Composition and Agent layers: a document of frames and layers that stays
   * editable. Three regions, as the spec draws them:
   *
   * * **left** — the documents, then a document's frames and layers;
   * * **centre** — the canvas, which is the document drawn, not a preview image;
   * * **right** — the inspector and the work around the document: the agent,
   *   the design system, checks, export and history.
   *
   * Every change is a typed operation the server versions. The page sends the
   * version it is looking at, so a change made against something stale is
   * either rebased or refused — never written over later work. The agent only
   * ever proposes; nothing it says is applied until the owner accepts it.
   */
  import { onMount, tick } from "svelte";
  import { routeStateFromHash } from "../routeState";
  import Icon from "./Icon.svelte";
  import TabStrip from "./TabStrip.svelte";
  import { api, ApiError } from "../api";
  import { contract } from "../generated/apiContract";
  import type {
    DesignDocumentList,
    DesignDocumentView,
    DesignExportView,
    DesignHandoffRecord,
    DesignProposalDecision,
    DesignProposalView,
    DesignSystemPreview,
    DesignSystemView,
    DesignTokenImport,
    DesignValidationView,
    DesignVersionList,
    ImageGallery,
    ModelsView,
  } from "../generated/apiContract";
  import type { ProjectsList } from "../apiTypes";
  import {
    addLayerOperation,
    alignOperations,
    allIds,
    distributeOperations,
    freshId,
    HANDLES,
    handlePoint,
    instanceOutOfDate,
    moveOperations,
    resizeBox,
    rotationFromPointer,
    siblingPosition,
    snapMove,
    toLocalDelta,
    topLevelSelection,
    type Alignment,
    type Box,
    type DesignNote,
    type Guide,
    type Handle,
    CHECK_STATUS,
    designReason,
    documentBody,
    findNode,
    layerRows,
    nudge,
    placeImageOperation,
    reorderOperation,
    versionKind,
    type DesignNode,
    type DesignOperation,
  } from "../designDocument";
  import { isReachableProfile } from "../modelReadiness.svelte";
  import { modelName } from "../modelPresentation";
  import { providerName, relativeTime } from "../format";
  import { offerDesignHandoff } from "../designHandoff.svelte";

  let { projects = null }: { projects?: ProjectsList | null } = $props();

  let list = $state<DesignDocumentList | null>(null);
  let listError = $state<string | null>(null);
  let open = $state<DesignDocumentView | null>(null);
  let frameId = $state<string | null>(null);
  let selectedId = $state<string | null>(null);
  let busy = $state(false);
  let notice = $state<string | null>(null);
  let gallery = $state<ImageGallery | null>(null);
  let models = $state<ModelsView | null>(null);
  let systems = $state<DesignSystemView[]>([]);

  type RailTab = "inspect" | "agent" | "system" | "check" | "export" | "history";
  let rail = $state<RailTab>("inspect");

  const body = $derived(documentBody(open?.document as Record<string, unknown> | undefined));
  const frame = $derived(body.frames.find((item) => item.id === frameId) ?? body.frames[0] ?? null);
  const selected = $derived(frame ? findNode(frame.nodes, selectedId) : null);
  const rows = $derived(frame ? layerRows(frame.nodes) : []);
  const images = $derived((gallery?.generations ?? []).filter((item) => item.has_image));

  /* ── Selection (DW-02) ──
   * `selectedId` is the layer the inspector shows; `multi` holds every
   * selected layer once there is more than one. Shift, Ctrl or Cmd adds or
   * removes a layer, on the canvas and in Layers alike. */
  let multi = $state<string[]>([]);
  const selection = $derived(multi.length > 1 ? multi : selectedId ? [selectedId] : []);
  const selectedNodes = $derived(
    frame ? selection.map((id) => findNode(frame!.nodes, id)).filter((node): node is DesignNode => node !== null) : [],
  );
  $effect(() => {
    if (multi.length > 0 && (selectedId === null || !multi.includes(selectedId))) multi = [];
  });

  function pick(id: string, additive: boolean) {
    if (!additive) {
      selectedId = id;
      multi = [];
      return;
    }
    const current = multi.length > 0 ? multi : selectedId ? [selectedId] : [];
    const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
    multi = next.length > 1 ? next : [];
    selectedId = next[next.length - 1] ?? null;
  }

  /* ── New document ── */
  let newTitle = $state("");
  let newPreset = $state("social_square");

  async function loadList() {
    try {
      list = await contract.listDesignDocuments();
      listError = null;
    } catch (error) {
      listError = error instanceof ApiError ? error.message : "Designs are unavailable.";
    }
  }

  async function createDocument() {
    busy = true;
    notice = null;
    try {
      const made = await contract.createDesignDocument({
        title: newTitle.trim() || "Untitled design",
        preset: newPreset,
      });
      newTitle = "";
      await loadList();
      show(made);
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  function show(view: DesignDocumentView) {
    open = view;
    const frames = documentBody(view.document as Record<string, unknown>).frames;
    if (!frames.some((item) => item.id === frameId)) frameId = frames[0]?.id ?? null;
    if (selectedId && frame && !findNode(frame.nodes, selectedId)) selectedId = null;
  }

  async function openDocument(documentId: string, keepNotice = false) {
    if (!keepNotice) notice = null;
    try {
      show(await contract.readDesignDocument(documentId));
      selectedId = null;
      rail = "inspect";
      void refreshRail();
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    }
  }

  /* ── Changes ── */

  /**
   * Send typed operations against the version on screen. A conflict reloads
   * the document and says so, rather than retrying blind over someone's work.
   */
  async function apply(operations: DesignOperation[], select: string | null = selectedId): Promise<boolean> {
    if (open === null || operations.length === 0) return false;
    busy = true;
    notice = null;
    try {
      const change = await contract.applyDesignOperations(open.document_id, {
        base_version: open.current_version,
        operations,
      });
      show(change.document);
      selectedId = select;
      if (rail === "check" || rail === "history") void refreshRail();
      return true;
    } catch (error) {
      const code = error instanceof ApiError ? error.reasonCode : null;
      notice = designReason(code);
      // Reloaded so the next change is made against what is really there; the
      // notice stays, because the owner needs to know why their change did not land.
      if (code?.startsWith("design_version_conflict")) await openDocument(open.document_id, true);
      return false;
    } finally {
      busy = false;
    }
  }

  function setField(field: string, value: unknown) {
    if (!selected) return;
    void apply([{ op: "update_node", node_id: selected.id, set: { [field]: value } }]);
  }

  function numberField(field: string, event: Event) {
    const raw = Number((event.currentTarget as HTMLInputElement).value);
    if (Number.isFinite(raw)) setField(field, raw);
  }

  function addLayer(kind: "text" | "rect" | "ellipse" | "stack") {
    if (!frame) return;
    const { op, id } = addLayerOperation(frame, kind, allIds(body));
    void apply([op], id);
  }

  let placing = $state(false);
  function placeImage(assetId: string) {
    if (!frame) return;
    const { op, id } = placeImageOperation(frame, assetId, allIds(body));
    placing = false;
    void apply([op], id);
  }

  function removeSelected() {
    if (!frame) return;
    const doomed = topLevelSelection(frame.nodes, selection).filter((node) => !node.locked);
    if (doomed.length === 0) return;
    void apply(doomed.map((node) => ({ op: "remove_node", node_id: node.id })), null);
  }

  function reorder(direction: "forward" | "backward" | "front" | "back") {
    if (!selected || !frame) return;
    const op = reorderOperation(body, frame, selected.id, direction);
    if (op) void apply([op]);
  }

  function groupSelected() {
    if (!selected || !frame) return;
    const ids = selection.length > 1 ? selection : [selected.id];
    const id = freshId("group", allIds(body));
    void apply([{ op: "group_nodes", node_ids: ids, group_id: id, name: "Group" }], id);
  }

  /** Grouping needs every selected layer to share one parent. */
  const sameParent = $derived(
    frame !== null &&
      new Set(selection.map((id) => siblingPosition(frame!.nodes, id)?.parentId ?? "?")).size === 1,
  );

  function align(how: Alignment) {
    if (!frame) return;
    const nodes = topLevelSelection(frame.nodes, selection);
    void apply(alignOperations(nodes, how, { x: 0, y: 0, w: frame.width, h: frame.height }));
  }

  function distribute(axis: "horizontal" | "vertical") {
    if (!frame) return;
    void apply(distributeOperations(topLevelSelection(frame.nodes, selection), axis));
  }

  /* ── Pointer editing (DW-02) ──
   * A drag is previewed locally and sent as one operation list when the
   * pointer is released, so a whole gesture is one version with the same lock
   * rules as the keyboard. Snapping draws the guides it matched; Alt turns it off. */
  type Point = { x: number; y: number };
  type Gesture =
    | { kind: "move"; start: Point; nodes: DesignNode[]; ids: Set<string>; dx: number; dy: number; moved: boolean }
    | { kind: "resize"; start: Point; node: DesignNode; handle: Handle; box: Box }
    | { kind: "rotate"; node: DesignNode; rotation: number };
  let gesture = $state<Gesture | null>(null);
  let guides = $state<Guide[]>([]);
  let unit = $state(1);
  let swallowClick = false;

  function svgPoint(event: PointerEvent): Point | null {
    const matrix = canvasEl?.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  }

  function measure() {
    const matrix = canvasEl?.getScreenCTM();
    if (matrix && matrix.a > 0) unit = 1 / matrix.a;
  }

  function subtree(nodes: readonly DesignNode[]): Set<string> {
    const ids = new Set<string>();
    const walk = (items: readonly DesignNode[]) => {
      for (const item of items) {
        ids.add(item.id);
        if (item.children) walk(item.children);
      }
    };
    walk(nodes);
    return ids;
  }

  function capture(event: PointerEvent) {
    try {
      canvasEl?.setPointerCapture(event.pointerId);
    } catch {
      // A synthetic pointer cannot be captured; the gesture still works.
    }
  }

  function startMove(event: PointerEvent, node: DesignNode) {
    if (event.button !== 0 || busy) return;
    event.stopPropagation();
    canvasEl?.focus();
    if (event.shiftKey || event.metaKey || event.ctrlKey) {
      pick(node.id, true);
      swallowClick = true;
      return;
    }
    if (!selection.includes(node.id)) pick(node.id, false);
    const point = svgPoint(event);
    if (!point || !frame) return;
    const nodes = topLevelSelection(frame.nodes, selection.includes(node.id) ? selection : [node.id]).filter(
      (item) => !item.locked,
    );
    swallowClick = true;
    if (nodes.length === 0) return;
    measure();
    gesture = { kind: "move", start: point, nodes, ids: subtree(nodes), dx: 0, dy: 0, moved: false };
    capture(event);
  }

  function startResize(event: PointerEvent, node: DesignNode, handle: Handle) {
    event.stopPropagation();
    const point = svgPoint(event);
    if (!point || node.locked || busy) return;
    measure();
    swallowClick = true;
    gesture = { kind: "resize", start: point, node, handle, box: { x: node.x, y: node.y, w: node.w, h: node.h } };
    capture(event);
  }

  function startRotate(event: PointerEvent, node: DesignNode) {
    event.stopPropagation();
    if (node.locked || busy) return;
    swallowClick = true;
    gesture = { kind: "rotate", node, rotation: node.rotation };
    capture(event);
  }

  function onPointerMove(event: PointerEvent) {
    if (gesture === null || frame === null) return;
    const point = svgPoint(event);
    if (!point) return;
    if (gesture.kind === "move") {
      // Whole pixels: a pointer at a scaled canvas lands between them.
      const dx = Math.round(point.x - gesture.start.x);
      const dy = Math.round(point.y - gesture.start.y);
      if (!gesture.moved && Math.hypot(dx, dy) < 3 * unit) return;
      const nodes = gesture.nodes;
      const left = Math.min(...nodes.map((n) => n.x));
      const top = Math.min(...nodes.map((n) => n.y));
      const box = { x: left, y: top, w: Math.max(...nodes.map((n) => n.x + n.w)) - left, h: Math.max(...nodes.map((n) => n.y + n.h)) - top };
      const ids = gesture.ids;
      const others = rows
        .map((row) => row.node)
        .filter((n) => n.visible && !ids.has(n.id) && !(n.children && n.children.some((c) => ids.has(c.id))));
      const snapped = event.altKey
        ? { dx, dy, guides: [] }
        : snapMove(box, dx, dy, { x: 0, y: 0, w: frame.width, h: frame.height }, others, 6 * unit, frame.grid.visible ? frame.grid.size : 0);
      gesture = { ...gesture, dx: snapped.dx, dy: snapped.dy, moved: true };
      guides = snapped.guides;
    } else if (gesture.kind === "resize") {
      const [lx, ly] = toLocalDelta(point.x - gesture.start.x, point.y - gesture.start.y, gesture.node.rotation);
      gesture = { ...gesture, box: resizeBox(gesture.node, gesture.handle, Math.round(lx), Math.round(ly), event.shiftKey) };
    } else {
      const node = gesture.node;
      gesture = { ...gesture, rotation: rotationFromPointer(node.x + node.w / 2, node.y + node.h / 2, point.x, point.y, event.shiftKey) };
    }
  }

  function onPointerUp(event: PointerEvent) {
    const done = gesture;
    gesture = null;
    guides = [];
    try {
      canvasEl?.releasePointerCapture(event.pointerId);
    } catch {
      // Not captured.
    }
    if (done === null) return;
    if (done.kind === "move" && done.moved) {
      void apply(moveOperations(done.nodes, done.dx, done.dy));
    } else if (done.kind === "resize") {
      const set: Record<string, number> = {};
      for (const key of ["x", "y", "w", "h"] as const) if (Math.abs(done.box[key] - done.node[key]) > 0.01) set[key] = done.box[key];
      if (Object.keys(set).length > 0) void apply([{ op: "update_node", node_id: done.node.id, set }]);
    } else if (done.kind === "rotate" && Math.abs(done.rotation - done.node.rotation) > 0.01) {
      void apply([{ op: "update_node", node_id: done.node.id, set: { rotation: done.rotation } }]);
    }
  }

  /** A layer as drawn right now: its stored geometry, or the gesture's preview of it. */
  function look(node: DesignNode): { box: Box; rotation: number; shift: [number, number] } {
    const box = { x: node.x, y: node.y, w: node.w, h: node.h };
    if (gesture?.kind === "move" && gesture.moved && gesture.nodes.some((item) => item.id === node.id)) {
      return { box, rotation: node.rotation, shift: [gesture.dx, gesture.dy] };
    }
    if (gesture?.kind === "resize" && gesture.node.id === node.id) return { box: gesture.box, rotation: node.rotation, shift: [0, 0] };
    if (gesture?.kind === "rotate" && gesture.node.id === node.id) return { box, rotation: gesture.rotation, shift: [0, 0] };
    return { box, rotation: node.rotation, shift: [0, 0] };
  }

  function transformOf(view: { box: Box; rotation: number; shift: [number, number] }): string | undefined {
    const parts: string[] = [];
    if (view.shift[0] || view.shift[1]) parts.push(`translate(${view.shift[0]} ${view.shift[1]})`);
    if (view.rotation) parts.push(`rotate(${view.rotation} ${view.box.x + view.box.w / 2} ${view.box.y + view.box.h / 2})`);
    return parts.length > 0 ? parts.join(" ") : undefined;
  }

  const handleNode = $derived(selectedNodes.length === 1 && !selectedNodes[0].locked ? selectedNodes[0] : null);

  /* ── Components (DW-06) ── */
  let componentName = $state("");
  const componentList = $derived(Object.entries(body.components));

  function makeComponent() {
    if (!selected) return;
    const name = componentName.trim() || selected.name;
    const id = freshId(`component-${name}`, allIds(body));
    componentName = "";
    void apply([{ op: "define_component", component_id: id, node_id: selected.id, name }]);
  }

  function placeComponent(componentId: string) {
    if (!frame) return;
    const component = body.components[componentId];
    if (!component) return;
    const width = Math.max(...component.nodes.map((n) => n.x + n.w), 1);
    const height = Math.max(...component.nodes.map((n) => n.y + n.h), 1);
    const id = freshId(componentId.replace(/^component-/, ""), allIds(body));
    void apply(
      [{ op: "place_component", component_id: componentId, frame_id: frame.id, node_id: id,
         x: Math.round((frame.width - width) / 2), y: Math.round((frame.height - height) / 2) }],
      id,
    );
  }

  /* ── Notes (DW-08) ── */
  let noteDraft = $state("");
  let showNotes = $state(true);
  const openNotes = $derived(body.notes.filter((note) => !note.resolved));

  function notesOn(target: string): DesignNote[] {
    return body.notes.filter((note) => note.target === target);
  }

  function addNote(target: string) {
    const text = noteDraft.trim();
    if (!text) return;
    noteDraft = "";
    void apply([{ op: "add_note", note: { id: freshId("note", allIds(body)), target, text } }]);
  }

  /* ── The owner's own pictures (DW-04) ── */
  let importing = $state(false);

  function fileBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function importPicture(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || !frame) return;
    importing = true;
    notice = null;
    try {
      const made = await contract.importDesignAsset({
        filename: file.name,
        media_type: file.type,
        data_base64: await fileBase64(file),
        project_id: open?.project_id ?? null,
      });
      gallery = await api.images();
      placeImage(made.generation.generation_id);
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      importing = false;
    }
  }

  function ungroupSelected() {
    if (!selected || selected.type !== "group") return;
    void apply([{ op: "ungroup", node_id: selected.id }], null);
  }

  async function changeVersion(kind: "undo" | "redo") {
    if (open === null) return;
    busy = true;
    notice = null;
    try {
      const request = { base_version: open.current_version };
      const change =
        kind === "undo"
          ? await contract.undoDesignChange(open.document_id, request)
          : await contract.redoDesignChange(open.document_id, request);
      show(change.document);
      if (rail === "history" || rail === "check") void refreshRail();
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  /* ── Frames ── */
  let variantPreset = $state("mobile");

  function addFrame() {
    if (!frame) return;
    const taken = allIds(body);
    let n = body.frames.length + 1;
    while (taken.has(`frame-${n}`)) n += 1;
    void apply([{ op: "add_frame", frame: { id: `frame-${n}`, name: `Frame ${n}`, preset: frame.preset } }]).then(
      (ok) => {
        if (ok) frameId = `frame-${n}`;
      },
    );
  }

  function makeVariant() {
    if (!frame || !list) return;
    const preset = list.presets.find((item) => item.preset === variantPreset);
    if (!preset) return;
    const taken = allIds(body);
    let id = `${frame.id}-${variantPreset}`.replace(/_/g, "-").slice(0, 40);
    let n = 2;
    while (taken.has(id)) id = `${frame.id}-${variantPreset}-${n++}`.replace(/_/g, "-").slice(0, 44);
    void apply([
      {
        op: "duplicate_frame",
        frame_id: frame.id,
        new_frame_id: id,
        name: `${frame.name} · ${preset.label}`,
        width: preset.width,
        height: preset.height,
        preset: preset.preset,
        variant: true,
      },
    ]).then((ok) => {
      if (ok) frameId = id;
    });
  }

  function setFrameField(field: string, value: unknown) {
    if (!frame) return;
    void apply([{ op: "update_frame", frame_id: frame.id, set: { [field]: value } }]);
  }

  function removeFrame() {
    if (!frame || body.frames.length < 2) return;
    const gone = frame.id;
    void apply([{ op: "remove_frame", frame_id: gone }], null).then((ok) => {
      if (ok) frameId = body.frames.find((item) => item.id !== gone)?.id ?? null;
    });
  }

  /* ── Canvas keyboard ── */
  let canvasEl = $state<SVGSVGElement | undefined>();

  function onCanvasKey(event: KeyboardEvent) {
    const mod = event.metaKey || event.ctrlKey;
    if (mod && event.key.toLowerCase() === "z") {
      event.preventDefault();
      void changeVersion(event.shiftKey ? "redo" : "undo");
      return;
    }
    if (event.key === "Escape") {
      selectedId = null;
      multi = [];
      return;
    }
    if (!selected || !frame) return;
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      removeSelected();
      return;
    }
    const step = nudge(selected, event.key, event.shiftKey);
    if (step) {
      event.preventDefault();
      const set = step.set as { x: number; y: number };
      const ops = selection.length > 1 ? moveOperations(topLevelSelection(frame.nodes, selection), set.x - selected.x, set.y - selected.y) : [step];
      void apply(ops);
    }
  }

  /* ── Rail data ── */
  let validation = $state<DesignValidationView | null>(null);
  let versions = $state<DesignVersionList | null>(null);
  let exports = $state<DesignExportView[]>([]);
  let handoffs = $state<DesignHandoffRecord[]>([]);
  let proposals = $state<DesignProposalView[]>([]);

  async function refreshRail() {
    if (open === null) return;
    const id = open.document_id;
    try {
      if (rail === "check" || rail === "export") validation = await contract.validateDesignDocument(id);
      if (rail === "history") versions = await contract.listDesignVersions(id);
      if (rail === "export") {
        exports = (await contract.listDesignExports(id)).exports;
        handoffs = (await contract.listDesignHandoffs(id)).handoffs;
      }
      if (rail === "agent") {
        proposals = (await contract.listDesignProposals(id)).proposals;
        // Read again on every visit: a host that has just restarted, or a model
        // connected on Models meanwhile, changes what can be asked.
        models = await api.models();
      }
      if (rail === "system") systems = (await contract.listDesignSystems()).systems;
    } catch {
      // Supplementary: the canvas stays usable when a side panel cannot load.
    }
  }

  async function restoreVersion(version: number) {
    if (open === null) return;
    busy = true;
    try {
      const change = await contract.restoreDesignVersion(open.document_id, String(version), {
        base_version: open.current_version,
      });
      show(change.document);
      await refreshRail();
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  /* ── Agent ── */
  let brief = $state("");
  let agentChoice = $state("");
  let proposing = $state(false);
  let picked = $state<Record<string, boolean>>({});
  let decision = $state<DesignProposalDecision | null>(null);
  const agentModels = $derived(
    (models?.profiles ?? [])
      .filter((profile) => isReachableProfile(profile) && profile.model && !/[<>]/.test(profile.model))
      .map((profile) => ({ key: `${profile.profile_id}::${profile.model}`, profile, model: profile.model })),
  );
  const agentPick = $derived(agentModels.find((item) => item.key === agentChoice) ?? agentModels[0] ?? null);
  $effect(() => {
    // The picker shows the model a proposal will use, never a blank choice.
    if (agentPick !== null && agentChoice !== agentPick.key) agentChoice = agentPick.key;
  });
  const pending = $derived(proposals.find((item) => item.status === "pending") ?? null);

  async function propose() {
    if (open === null || frame === null || !brief.trim() || agentPick === null) return;
    proposing = true;
    notice = null;
    decision = null;
    try {
      const made = await contract.proposeDesignChange(open.document_id, {
        frame_id: frame.id,
        brief: brief.trim(),
        model_profile: agentPick.profile.profile_id,
        model: agentPick.model,
      });
      proposals = [made, ...proposals];
      picked = Object.fromEntries(made.operations.filter((op) => op.status === "valid").map((op) => [String(op.index), true]));
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      proposing = false;
    }
  }

  async function decide(proposal: DesignProposalView, accept: boolean, skipConflicts = false) {
    if (open === null) return;
    busy = true;
    notice = null;
    try {
      const indexes = proposal.operations
        .filter((op) => op.status === "valid" && picked[String(op.index)] !== false)
        .map((op) => op.index);
      decision = await contract.decideDesignProposal(proposal.proposal_id, {
        decision: accept ? "accept" : "reject",
        ...(accept ? { indexes, skip_conflicts: skipConflicts } : {}),
      });
      if (decision.ok) {
        await openDocument(open.document_id);
        rail = "agent";
      }
      proposals = (await contract.listDesignProposals(open.document_id)).proposals;
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  /* ── Design system ── */
  let systemChoice = $state("");
  let preview = $state<DesignSystemPreview | null>(null);
  let systemName = $state("");
  let systemColors = $state("primary=#1144aa\nink=#111111\nsurface=#ffffff");
  let systemFonts = $state("body=sans-serif\nheading=sans-serif");
  let systemSpacing = $state("");
  let systemRequired = $state("");
  let systemSource = $state("");
  let tokenReport = $state<DesignTokenImport | null>(null);
  let paletteAsset = $state("");

  /** DW-06 — a tokens file read on this machine fills the form; saving is still the owner's. */
  async function importTokens(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    notice = null;
    try {
      const read = await contract.readDesignTokens({ filename: file.name, text: await file.text() });
      const variables = read.variables as Record<string, Record<string, string | number>>;
      const lines = (group: string) => Object.entries(variables[group] ?? {}).map(([key, value]) => `${key}=${value}`).join("\n");
      systemColors = lines("colors");
      systemFonts = lines("fonts");
      systemSpacing = lines("spacing");
      systemSource = `${read.filename} (sha256 ${read.sha256.slice(0, 12)}…)`;
      if (!systemName.trim()) systemName = read.filename.replace(/\.[^.]+$/, "");
      tokenReport = read;
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    }
  }

  /** DW-06 — the dominant colours of a picture the owner already has, read here. */
  async function readPalette() {
    const asset = images.find((item) => item.generation_id === paletteAsset);
    if (!asset) return;
    notice = null;
    try {
      const read = await contract.readDesignAssetPalette(asset.generation_id);
      systemColors = read.colors.map((item, index) => `brand-${index + 1}=${item.color}`).join("\n");
      systemSource = `Colours read from “${asset.prompt}” (${asset.generation_id})`;
      tokenReport = null;
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    }
  }

  function spacingPairs(text: string): Record<string, number> {
    const out: Record<string, number> = {};
    for (const [key, value] of Object.entries(pairs(text))) {
      const number = Number(value.replace(/px$/, ""));
      if (Number.isFinite(number)) out[key] = number;
    }
    return out;
  }

  function pairs(text: string): Record<string, string> {
    const out: Record<string, string> = {};
    for (const line of text.split("\n")) {
      const at = line.indexOf("=");
      if (at > 0) out[line.slice(0, at).trim()] = line.slice(at + 1).trim();
    }
    return out;
  }

  async function saveSystem() {
    busy = true;
    notice = null;
    try {
      const saved = await contract.createDesignSystem({
        name: systemName.trim() || "Brand",
        source_note: systemSource.trim(),
        variables: {
          colors: pairs(systemColors),
          fonts: pairs(systemFonts),
          spacing: spacingPairs(systemSpacing),
          required: systemRequired.split(",").map((item) => item.trim()).filter(Boolean),
        },
      });
      systems = (await contract.listDesignSystems()).systems;
      systemChoice = saved.system_id;
      systemName = "";
      tokenReport = null;
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  async function previewSystem() {
    if (open === null) return;
    try {
      preview = await contract.previewDesignSystem(open.document_id, { system_id: systemChoice || null });
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    }
  }

  async function chooseSystem() {
    if (open === null) return;
    busy = true;
    try {
      const change = await contract.chooseDesignSystem(open.document_id, {
        system_id: systemChoice || null,
        version: preview?.system?.version ?? null,
        base_version: open.current_version,
      });
      show(change.document);
      preview = null;
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  const activeSystem = $derived(systems.find((item) => item.system_id === open?.system_id) ?? null);
  const colorVars = $derived(
    Object.keys(((activeSystem?.variables as Record<string, unknown> | undefined)?.colors as Record<string, string>) ?? {}),
  );

  /* ── Export and handoff ── */
  let exportFormat = $state("png");
  let exportScale = $state(1);
  let handoffTarget = $state("");
  let handedOff = $state<string | null>(null);

  async function runExport() {
    if (open === null || frame === null) return;
    busy = true;
    notice = null;
    try {
      await contract.exportDesignFrame(open.document_id, { frame_id: frame.id, format: exportFormat, scale: exportScale });
      await refreshRail();
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  const FORMAT_LABEL: Record<string, string> = { png: "PNG", pdf: "PDF (raster)", vector_pdf: "PDF (vector)", svg: "SVG", json: "JSON" };

  async function download(item: DesignExportView) {
    const blob = await api.designExportBlob(item.export_id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `raiker-design-${item.frame_id}-v${item.version}.${item.format === "vector_pdf" ? "pdf" : item.format}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function handOff() {
    if (open === null || frame === null) return;
    busy = true;
    notice = null;
    try {
      const made = await contract.handDesignToBuild(open.document_id, {
        frame_ids: [frame.id],
        target: handoffTarget.trim(),
      });
      offerDesignHandoff({
        kind: "document",
        label: made.filename,
        detail: `${made.filename} (${made.media_type}, ${made.byte_size} bytes)`,
        attachmentId: made.attachment_id,
        mediaType: made.media_type,
        byteSize: made.byte_size,
        source: "generated",
      });
      handedOff = made.filename;
      await refreshRail();
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = false;
    }
  }

  /* ── Rename and filing ── */
  async function rename(event: Event) {
    if (open === null) return;
    const title = (event.currentTarget as HTMLInputElement).value.trim();
    if (!title || title === open.title) return;
    try {
      show(await contract.updateDesignDocument(open.document_id, { title }));
      await loadList();
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    }
  }

  async function file(event: Event) {
    if (open === null) return;
    try {
      show(await contract.updateDesignDocument(open.document_id, { project_id: (event.currentTarget as HTMLSelectElement).value }));
    } catch (error) {
      notice = designReason(error instanceof ApiError ? error.reasonCode : null);
    }
  }

  async function removeDocument(documentId: string) {
    await contract.deleteDesignDocument(documentId);
    if (open?.document_id === documentId) open = null;
    await loadList();
  }

  async function restoreDocument(documentId: string) {
    await contract.restoreDesignDocument(documentId);
    await loadList();
  }

  $effect(() => {
    void rail;
    void refreshRail();
  });

  onMount(async () => {
    await loadList();
    // QUI-F15 — a Library link names the document (`record=`). Opened only if
    // it is in this owner's list; anything else leaves the list as it was.
    const named = routeStateFromHash(window.location.hash).recordId;
    if (named !== null && (list?.documents ?? []).some((row) => row.document_id === named)) {
      void openDocument(named);
    }
    try {
      gallery = await api.images();
    } catch {
      gallery = null;
    }
    try {
      models = await api.models();
    } catch {
      models = null;
    }
    try {
      systems = (await contract.listDesignSystems()).systems;
    } catch {
      systems = [];
    }
    await tick();
  });

  const RAIL_TABS = [
    { id: "inspect", label: "Inspect" },
    { id: "agent", label: "Agent" },
    { id: "system", label: "System" },
    { id: "check", label: "Check" },
    { id: "export", label: "Export" },
    { id: "history", label: "History" },
  ];

  /** A finding's layer, with its frame named when the design has more than one. */
  function findingPlace(frameKey: string | null, layerName: string): string {
    if (body.frames.length < 2 || frameKey === null) return layerName;
    return `${body.frames.find((item) => item.id === frameKey)?.name ?? frameKey} › ${layerName}`;
  }

  function cropValue(node: DesignNode, key: string): number {
    const crop = node.crop ?? { x: 0, y: 0, w: 1, h: 1 };
    return crop[key as keyof typeof crop];
  }

  function planSummary(proposal: DesignProposalView): string {
    const summary = (proposal.plan as Record<string, unknown>).summary;
    return typeof summary === "string" && summary ? summary : proposal.brief;
  }

  function planItems(proposal: DesignProposalView, part: string): string[] {
    const items = (proposal.plan as Record<string, unknown>)[part];
    return Array.isArray(items) ? items.map(String) : [];
  }

  /** DW-12 — a proposal's state in words. */
  const PROPOSAL_STATE: Record<string, string> = {
    pending: "Proposed",
    requesting: "Asking the model",
    accepted: "Accepted",
    partially_accepted: "Partly accepted",
    rejected: "Rejected",
    failed: "Failed",
    outcome_unknown: "Outcome unknown",
  };

  function nodeLabel(node: DesignNode): string {
    return `${node.name} (${node.type}${node.locked ? ", locked" : ""}${node.visible ? "" : ", hidden"}${node.created_by === "agent" ? ", added by the agent" : ""})`;
  }
</script>

{#snippet layer(node: DesignNode)}
  {#if node.visible}
    {@const view = look(node)}
    {@const b = view.box}
    {@const isSelected = selection.includes(node.id)}
    <g data-layer={node.id} opacity={node.opacity} transform={transformOf(view)}>
      {#if node.type === "rect" || (node.type === "stack" && (node.fill || node.stroke))}
        <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={node.radius ?? 0} fill={node.fill ?? "none"} stroke={node.stroke ?? undefined} stroke-width={node.stroke_width ?? 0} />
      {:else if node.type === "ellipse"}
        <ellipse cx={b.x + b.w / 2} cy={b.y + b.h / 2} rx={b.w / 2} ry={b.h / 2} fill={node.fill ?? "none"} stroke={node.stroke ?? undefined} stroke-width={node.stroke_width ?? 0} />
      {:else if node.type === "text"}
        <!-- Drawn past its box when it overflows, as the export draws it, so
             what Check calls overflow is visible here rather than clipped. -->
        <foreignObject x={b.x} y={b.y} width={Math.max(b.w, 1)} height={Math.max(b.h, (frame?.height ?? b.h) - b.y, 1)}>
          <div
            class="canvas-text"
            style={`font-family:${node.font_family};font-size:${node.font_size}px;font-weight:${node.font_weight};color:${node.color ?? "currentColor"};text-align:${node.align};line-height:${node.line_height}`}
          >{node.text}</div>
        </foreignObject>
      {:else if node.type === "image"}
        {#if node.asset_id}
          {@const crop = node.crop ?? { x: 0, y: 0, w: 1, h: 1 }}
          <svg x={b.x} y={b.y} width={b.w} height={b.h} viewBox={`${crop.x * 1000} ${crop.y * 1000} ${crop.w * 1000} ${crop.h * 1000}`} preserveAspectRatio={node.fit === "cover" ? "xMidYMid slice" : node.fit === "contain" ? "xMidYMid meet" : "none"}>
            <image href={api.imageBytesUrl(node.asset_id)} width="1000" height="1000" preserveAspectRatio="none" />
          </svg>
        {:else}
          <rect class="missing" x={b.x} y={b.y} width={b.w} height={b.h} />
        {/if}
      {/if}
      {#if node.children}
        {#each node.children as child (child.id)}{@render layer(child)}{/each}
      {/if}
      <rect
        class="hit"
        class:selected={isSelected}
        class:locked={node.locked}
        x={b.x}
        y={b.y}
        width={Math.max(b.w, 4)}
        height={Math.max(b.h, 4)}
        role="button"
        tabindex="-1"
        aria-label={nodeLabel(node)}
        aria-pressed={isSelected}
        onpointerdown={(event) => startMove(event, node)}
        onclick={(event) => {
          // A press already selected in pointerdown; a click without one (a
          // screen reader, a test) selects here.
          event.stopPropagation();
          if (swallowClick) {
            swallowClick = false;
            return;
          }
          pick(node.id, event.shiftKey || event.metaKey || event.ctrlKey);
          canvasEl?.focus();
        }}
        onkeydown={() => {}}
      />
    </g>
  {/if}
{/snippet}

{#snippet notes(target: string, label: string)}
  {@const here = notesOn(target)}
  <section class="panel" aria-label="Notes">
    <h3>Notes on {label} <span class="muted">{here.filter((note) => !note.resolved).length} open</span></h3>
    {#each here as note (note.id)}
      <div class="note" class:resolved={note.resolved}>
        <p>{note.text}</p>
        <span class="muted">{note.author === "agent" ? "the agent" : "you"}{note.resolved ? " · resolved" : ""}</span>
        <div class="row-actions">
          <button type="button" class="link" disabled={busy} onclick={() => void apply([{ op: "update_note", note_id: note.id, set: { resolved: !note.resolved } }])}>{note.resolved ? "Reopen" : "Resolve"}</button>
          <button type="button" class="link danger" disabled={busy} onclick={() => void apply([{ op: "remove_note", note_id: note.id }])}>Delete</button>
        </div>
      </div>
    {/each}
    <textarea rows="2" bind:value={noteDraft} placeholder="Leave a note — what to change, a question for later" aria-label={`New note on ${label}`} maxlength="1000"></textarea>
    <div class="row-actions">
      <button type="button" class="btn btn-sm" disabled={busy || !noteDraft.trim()} onclick={() => addNote(target)}>Add note</button>
      <label class="check"><input type="checkbox" bind:checked={showNotes} /> Show pins</label>
    </div>
    <p class="muted">Notes are versions like any change. They are not drawn into exports; open ones go with a Build handoff.</p>
  </section>
{/snippet}

<div class="documents" data-testid="design-documents">
  {#if notice}<p class="notice" role="alert">{notice}</p>{/if}

  {#if open === null}
    <section class="start" aria-label="Designs">
      <form
        class="new-doc"
        onsubmit={(event) => {
          event.preventDefault();
          void createDocument();
        }}
      >
        <label>
          <span>New design</span>
          <input type="text" bind:value={newTitle} placeholder="Name it — Launch post, Pricing page…" maxlength="120" />
        </label>
        <label>
          <span>Starts as</span>
          <select bind:value={newPreset} aria-label="Frame size">
            {#each list?.presets ?? [] as preset (preset.preset)}
              <option value={preset.preset}>{preset.label} · {preset.width}×{preset.height}</option>
            {/each}
          </select>
        </label>
        <button type="submit" class="btn btn-primary" disabled={busy}><Icon name="plus" size="sm" />Create</button>
      </form>
      {#if listError}
        <p class="error" role="alert">{listError}</p>
      {:else if list === null}
        <p class="muted">Loading designs…</p>
      {:else if list.documents.length === 0}
        <p class="muted empty">
          No designs yet. A design is a document of frames and layers you can keep editing, ask
          the agent to change, check, export and hand to Build. Pictures you generate live under
          <strong>Images</strong> and can be placed into one.
        </p>
      {:else}
        <ul class="doc-list">
          {#each list.documents as item (item.document_id)}
            <li>
              <button type="button" class="doc-open" onclick={() => void openDocument(item.document_id)}>
                <span class="doc-title">{item.title}</span>
                <span class="muted">
                  {item.frame_count} {item.frame_count === 1 ? "frame" : "frames"} · version {item.current_version} ·
                  {relativeTime(item.updated_at)}
                </span>
              </button>
              <button type="button" class="link danger" onclick={() => void removeDocument(item.document_id)}
                >Delete</button
              >
            </li>
          {/each}
        </ul>
      {/if}
      {#if (list?.deleted ?? []).length > 0}
        <details class="deleted-docs">
          <summary>Recently deleted ({list!.deleted.length})</summary>
          <ul>
            {#each list!.deleted as item (item.document_id)}
              <li>
                {item.title}
                <button type="button" class="link" onclick={() => void restoreDocument(item.document_id)}>Restore</button>
              </li>
            {/each}
          </ul>
        </details>
      {/if}
    </section>
  {:else}
    <header class="doc-head">
      <button type="button" class="back" onclick={() => { open = null; void loadList(); }}>
        <Icon name="chevron-left" size="sm" />All designs
      </button>
      <input class="doc-name" type="text" value={open.title} aria-label="Design name" onchange={rename} maxlength="120" />
      <label class="filed">
        <span class="sr-only">Filed in</span>
        <select value={open.project_id ?? ""} onchange={file} aria-label="Filed in">
          <option value="">Unfiled</option>
          {#each projects?.projects ?? [] as project (project.project_id)}
            <option value={project.project_id}>{project.name}</option>
          {/each}
        </select>
      </label>
      <span class="version" title={`Content hash ${open.content_hash}`}>v{open.current_version}</span>
      <button type="button" class="btn btn-ghost btn-sm" disabled={busy || !open.can_undo} onclick={() => void changeVersion("undo")} aria-label="Undo">Undo</button>
      <button type="button" class="btn btn-ghost btn-sm" disabled={busy || !open.can_redo} onclick={() => void changeVersion("redo")} aria-label="Redo">Redo</button>
    </header>

    <div class="workspace">
      <aside class="left" aria-label="Frames and layers">
        <h3>Frames</h3>
        <ul class="frames">
          {#each body.frames as item (item.id)}
            <li>
              <button type="button" class="row" class:current={item.id === frame?.id} aria-current={item.id === frame?.id ? "true" : undefined} onclick={() => { frameId = item.id; selectedId = null; }}>
                {item.name}
                <span class="muted">{item.width}×{item.height}{item.variant_of ? ` · variant of ${body.frames.find((f) => f.id === item.variant_of)?.name ?? item.variant_of}` : ""}</span>
              </button>
            </li>
          {/each}
        </ul>
        <div class="row-actions">
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={addFrame}>Add frame</button>
        </div>
        <div class="variant">
          <label>
            <span>Responsive variant as</span>
            <select bind:value={variantPreset}>
              {#each list?.presets ?? [] as preset (preset.preset)}
                <option value={preset.preset}>{preset.label}</option>
              {/each}
            </select>
          </label>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={makeVariant}>Make variant</button>
        </div>

        <h3>Layers <span class="muted">{rows.length}</span></h3>
        <div class="add-row" role="group" aria-label="Add a layer">
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => addLayer("text")}>Text</button>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => addLayer("rect")}>Rectangle</button>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => addLayer("ellipse")}>Ellipse</button>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => addLayer("stack")}>Stack</button>
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} title="Place a picture you made or import your own" aria-expanded={placing} onclick={() => (placing = !placing)}>Image</button>
        </div>
        {#if placing}
          <label class="import-picture">
            <span class="btn btn-ghost btn-sm">{importing ? "Importing…" : "Import your own picture…"}</span>
            <input class="sr-only" type="file" accept="image/png,image/jpeg,image/webp,image/gif" disabled={importing} onchange={(event) => void importPicture(event)} />
          </label>
          <p class="muted">An imported picture stays on this machine; it goes to an image provider only if you later ask to edit it under Images.</p>
          <ul class="place" aria-label="Choose a picture to place">
            {#each images.slice(0, 24) as item (item.generation_id)}
              <li>
                <button type="button" onclick={() => placeImage(item.generation_id)} title={item.prompt}>
                  <img src={api.imageBytesUrl(item.generation_id)} alt={item.prompt} loading="lazy" />
                </button>
              </li>
            {/each}
          </ul>
        {/if}
        <h3>Components <span class="muted">{componentList.length}</span></h3>
        {#if componentList.length === 0}
          <p class="muted">Select a layer and choose <strong>Make component</strong> to reuse it.</p>
        {:else}
          <ul class="components">
            {#each componentList as [componentId, component] (componentId)}
              <li>
                <span class="name">{component.name}</span>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => placeComponent(componentId)} aria-label={`Place ${component.name}`}>Place</button>
                <button type="button" class="link danger" disabled={busy} onclick={() => void apply([{ op: "remove_component", component_id: componentId }])} aria-label={`Remove component ${component.name}`}>Remove</button>
              </li>
            {/each}
          </ul>
        {/if}

        {#if rows.length === 0}
          <p class="muted">This frame is empty. Add a layer, or ask the agent.</p>
        {:else}
          <ul class="layers">
            {#each rows as row (row.node.id)}
              <li style={`--depth:${row.depth}`}>
                <button
                  type="button"
                  class="row layer-row"
                  class:current={selection.includes(row.node.id)}
                  aria-current={selection.includes(row.node.id) ? "true" : undefined}
                  onclick={(event) => pick(row.node.id, event.shiftKey || event.metaKey || event.ctrlKey)}
                >
                  <span class="kind">{row.node.component_id ? "instance" : row.node.type}</span>
                  <span class="name">{row.node.name}</span>
                  {#if row.node.created_by === "agent"}<span class="badge">agent</span>{/if}
                  {#if openNotes.some((note) => note.target === row.node.id)}<span class="badge">note</span>{/if}
                </button>
                <button type="button" class="icon-btn" aria-label={`${row.node.visible ? "Hide" : "Show"} ${row.node.name}`} aria-pressed={!row.node.visible} onclick={() => void apply([{ op: "update_node", node_id: row.node.id, set: { visible: !row.node.visible } }])}>
                  <Icon name={row.node.visible ? "eye" : "eye-off"} size="sm" />
                </button>
                <button type="button" class="icon-btn" aria-label={`${row.node.locked ? "Unlock" : "Lock"} ${row.node.name}`} aria-pressed={row.node.locked} onclick={() => void apply([{ op: "update_node", node_id: row.node.id, set: { locked: !row.node.locked } }])}>
                  <Icon name="lock" size="sm" filled={row.node.locked} />
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </aside>

      <section class="stage" aria-label="Canvas">
        {#if frame}
          <p class="stage-head muted">
            {frame.name} · {frame.width}×{frame.height} — drag a layer to move it (it snaps to edges and centres; hold Alt to place freely), drag a handle to resize or rotate, Shift-click to select more. Arrow keys nudge (Shift for 10px), Delete removes, Ctrl+Z undoes.
          </p>
          <!-- The canvas is one keyboard stop: arrows move the selected layer,
               Delete removes it, Escape clears the selection, Ctrl+Z undoes.
               Layers are also reachable as buttons in the Layers list. -->
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
          <svg
            bind:this={canvasEl}
            class="canvas"
            viewBox={`0 0 ${frame.width} ${frame.height}`}
            role="application"
            aria-label={`Canvas: ${frame.name}${selected ? `, ${selected.name} selected` : ""}`}
            tabindex="0"
            onkeydown={onCanvasKey}
            onpointermove={onPointerMove}
            onpointerup={onPointerUp}
            onpointercancel={onPointerUp}
            onclick={() => {
              if (swallowClick) {
                swallowClick = false;
                return;
              }
              selectedId = null;
              multi = [];
            }}
          >
            <rect width={frame.width} height={frame.height} fill={frame.background ?? "#ffffff"} />
            {#if frame.grid.visible && frame.grid.size > 0}
              <defs>
                <pattern id={`grid-${frame.id}`} width={frame.grid.size} height={frame.grid.size} patternUnits="userSpaceOnUse">
                  <path d={`M ${frame.grid.size} 0 L 0 0 0 ${frame.grid.size}`} class="grid-line" />
                </pattern>
              </defs>
              <rect width={frame.width} height={frame.height} fill={`url(#grid-${frame.id})`} />
            {/if}
            {#each frame.nodes as node (node.id)}{@render layer(node)}{/each}
            {#if showNotes}
              {#each openNotes as note, index (note.id)}
                {@const target = findNode(frame.nodes, note.target)}
                {#if target && target.visible}
                  <g class="note-pin" aria-hidden="true">
                    <circle cx={target.x + target.w} cy={target.y} r={11 * unit} />
                    <text x={target.x + target.w} y={target.y} font-size={12 * unit} text-anchor="middle" dominant-baseline="central">{index + 1}</text>
                  </g>
                {/if}
              {/each}
            {/if}
            {#each guides as guide, i (i)}
              {#if guide.axis === "x"}
                <line class="guide" x1={guide.at} y1="0" x2={guide.at} y2={frame.height} />
              {:else}
                <line class="guide" x1="0" y1={guide.at} x2={frame.width} y2={guide.at} />
              {/if}
            {/each}
            {#if handleNode && !(gesture?.kind === "move" && gesture.moved)}
              {@const view = look(handleNode)}
              {@const hb = view.box}
              <!-- Handles: the same operations as the inspector, one version per drag. -->
              <g class="handles" data-handles={handleNode.id} transform={view.rotation ? `rotate(${view.rotation} ${hb.x + hb.w / 2} ${hb.y + hb.h / 2})` : undefined}>
                {#if handleNode.type !== "group"}
                  {#each HANDLES as handle (handle)}
                    {@const at = handlePoint(hb, handle)}
                    <!-- svelte-ignore a11y_no_static_element_interactions -->
                    <rect
                      class={`handle handle-${handle}`}
                      data-handle={handle}
                      x={at.x - 6 * unit}
                      y={at.y - 6 * unit}
                      width={12 * unit}
                      height={12 * unit}
                      onpointerdown={(event) => startResize(event, handleNode!, handle)}
                    />
                  {/each}
                {/if}
                <line class="rotate-stem" x1={hb.x + hb.w / 2} y1={hb.y} x2={hb.x + hb.w / 2} y2={hb.y - 30 * unit} />
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <circle
                  class="handle rotate"
                  data-handle="rotate"
                  cx={hb.x + hb.w / 2}
                  cy={hb.y - 30 * unit}
                  r={7 * unit}
                  onpointerdown={(event) => startRotate(event, handleNode!)}
                />
              </g>
            {/if}
          </svg>
        {/if}
      </section>

      <aside class="right" aria-label="Inspector and design work">
        <TabStrip tabs={RAIL_TABS} selected={rail} onselect={(id: string) => (rail = id as RailTab)} label="Design panels" />

        {#if rail === "inspect"}
          {#if selectedNodes.length > 1}
            <section class="panel" aria-label="Selected layers">
              <h3>{selectedNodes.length} layers selected</h3>
              <div class="row-actions" role="group" aria-label="Align">
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => align("left")}>Align left</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => align("center")}>Centre</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => align("right")}>Align right</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => align("top")}>Align top</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => align("middle")}>Middle</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => align("bottom")}>Align bottom</button>
              </div>
              <div class="row-actions" role="group" aria-label="Distribute">
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selectedNodes.length < 3} onclick={() => distribute("horizontal")}>Distribute across</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selectedNodes.length < 3} onclick={() => distribute("vertical")}>Distribute down</button>
              </div>
              <div class="row-actions">
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || !sameParent} title={sameParent ? "" : "Only layers with the same parent can be grouped"} onclick={groupSelected}>Group</button>
                <button type="button" class="link danger" disabled={busy} onclick={removeSelected}>Remove</button>
              </div>
              <p class="muted">Locked layers stay where they are. Shift-click a layer to add or remove it; Escape clears the selection.</p>
            </section>
          {:else if selected}
            <section class="panel" aria-label="Layer properties">
              <h3>{selected.type} · <code>{selected.id}</code></h3>
              {#if selected.locked}<p class="muted">Locked — unlock it in Layers to change it.</p>{/if}
              <label>Name <input type="text" value={selected.name} disabled={selected.locked} onchange={(e) => setField("name", (e.currentTarget as HTMLInputElement).value)} /></label>
              <div class="grid4">
                <label>X <input type="number" value={selected.x} disabled={selected.locked} onchange={(e) => numberField("x", e)} /></label>
                <label>Y <input type="number" value={selected.y} disabled={selected.locked} onchange={(e) => numberField("y", e)} /></label>
                <label>W <input type="number" min="0" value={selected.w} disabled={selected.locked || selected.type === "group"} onchange={(e) => numberField("w", e)} /></label>
                <label>H <input type="number" min="0" value={selected.h} disabled={selected.locked || selected.type === "group"} onchange={(e) => numberField("h", e)} /></label>
              </div>
              <div class="grid4">
                <label>Rotate <input type="number" min="-360" max="360" value={selected.rotation} disabled={selected.locked} onchange={(e) => numberField("rotation", e)} /></label>
                <label>Opacity <input type="number" min="0" max="1" step="0.05" value={selected.opacity} disabled={selected.locked} onchange={(e) => numberField("opacity", e)} /></label>
              </div>
              {#if selected.type === "text"}
                <label>Text <textarea rows="3" value={selected.text} disabled={selected.locked} onchange={(e) => setField("text", (e.currentTarget as HTMLTextAreaElement).value)}></textarea></label>
                <div class="grid4">
                  <label>Size <input type="number" min="1" value={selected.font_size} disabled={selected.locked} onchange={(e) => numberField("font_size", e)} /></label>
                  <label>Weight
                    <select value={String(selected.font_weight)} disabled={selected.locked} onchange={(e) => setField("font_weight", Number((e.currentTarget as HTMLSelectElement).value))}>
                      {#each [300, 400, 500, 600, 700, 800] as weight (weight)}<option value={String(weight)}>{weight}</option>{/each}
                    </select>
                  </label>
                  <label>Align
                    <select value={selected.align} disabled={selected.locked} onchange={(e) => setField("align", (e.currentTarget as HTMLSelectElement).value)}>
                      <option value="left">Left</option><option value="center">Centre</option><option value="right">Right</option>
                    </select>
                  </label>
                </div>
                <label>Font <input type="text" value={selected.font_family} disabled={selected.locked} onchange={(e) => setField("font_family", (e.currentTarget as HTMLInputElement).value)} /></label>
                <label>Colour <input type="color" value={(selected.color ?? "#111111").slice(0, 7)} disabled={selected.locked} onchange={(e) => setField("color", (e.currentTarget as HTMLInputElement).value)} /></label>
                {#if colorVars.length > 0}
                  <label>Colour variable
                    <select value={selected.color_var ?? ""} disabled={selected.locked} onchange={(e) => setField("color_var", (e.currentTarget as HTMLSelectElement).value || null)}>
                      <option value="">None</option>{#each colorVars as name (name)}<option value={name}>{name}</option>{/each}
                    </select>
                  </label>
                {/if}
              {/if}
              {#if selected.type === "rect" || selected.type === "ellipse" || selected.type === "stack"}
                <label>Fill <input type="color" value={(selected.fill ?? "#d9d9d9").slice(0, 7)} disabled={selected.locked} onchange={(e) => setField("fill", (e.currentTarget as HTMLInputElement).value)} /></label>
                {#if colorVars.length > 0}
                  <label>Fill variable
                    <select value={selected.fill_var ?? ""} disabled={selected.locked} onchange={(e) => setField("fill_var", (e.currentTarget as HTMLSelectElement).value || null)}>
                      <option value="">None</option>{#each colorVars as name (name)}<option value={name}>{name}</option>{/each}
                    </select>
                  </label>
                {/if}
                {#if selected.type !== "ellipse"}
                  <label>Corner radius <input type="number" min="0" value={selected.radius ?? 0} disabled={selected.locked} onchange={(e) => numberField("radius", e)} /></label>
                {/if}
              {/if}
              {#if selected.type === "stack"}
                <div class="grid4">
                  <label>Direction
                    <select value={selected.direction} disabled={selected.locked} onchange={(e) => setField("direction", (e.currentTarget as HTMLSelectElement).value)}>
                      <option value="column">Column</option><option value="row">Row</option>
                    </select>
                  </label>
                  <label>Gap <input type="number" min="0" value={selected.gap} disabled={selected.locked} onchange={(e) => numberField("gap", e)} /></label>
                  <label>Padding <input type="number" min="0" value={selected.padding} disabled={selected.locked} onchange={(e) => numberField("padding", e)} /></label>
                </div>
                <p class="muted">A stack places what is inside it. Move a layer into it from Layers with the arrange buttons below.</p>
              {/if}
              {#if selected.type === "image"}
                <label>Alternative text <input type="text" value={selected.alt} disabled={selected.locked} placeholder="Describe the picture" onchange={(e) => setField("alt", (e.currentTarget as HTMLInputElement).value)} /></label>
                <label>Fit
                  <select value={selected.fit} disabled={selected.locked} onchange={(e) => setField("fit", (e.currentTarget as HTMLSelectElement).value)}>
                    <option value="cover">Fill the box (crop edges)</option><option value="contain">Fit inside the box</option><option value="fill">Stretch</option>
                  </select>
                </label>
                <fieldset class="crop">
                  <legend>Crop (kept part of the picture, 0–1)</legend>
                  {#each ["x", "y", "w", "h"] as key (key)}
                    <label>{key.toUpperCase()}
                      <input type="number" min="0" max="1" step="0.05" value={cropValue(selected, key)} disabled={selected.locked}
                        onchange={(e) => setField("crop", { ...(selected!.crop ?? { x: 0, y: 0, w: 1, h: 1 }), [key]: Number((e.currentTarget as HTMLInputElement).value) })} />
                    </label>
                  {/each}
                  <button type="button" class="link" disabled={selected.locked || !selected.crop} onclick={() => setField("crop", null)}>Remove crop</button>
                </fieldset>
                <p class="muted">Crop and fit never change the picture itself; it stays linked to the asset under Images.</p>
              {/if}
              <div class="row-actions" role="group" aria-label="Arrange">
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selected.locked} onclick={() => reorder("forward")}>Forward</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selected.locked} onclick={() => reorder("backward")}>Backward</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selected.locked} onclick={groupSelected}>Group</button>
                {#if selected.type === "group"}<button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={ungroupSelected}>Ungroup</button>{/if}
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => void apply([{ op: "add_node", frame_id: frame!.id, node: { ...selected!, id: `${selected!.id}-copy`.slice(0, 44), x: selected!.x + 16, y: selected!.y + 16, locked: false } }])}>Duplicate</button>
                <button type="button" class="link danger" disabled={busy || selected.locked} onclick={removeSelected}>Remove</button>
              </div>
              <div class="row-actions" role="group" aria-label="Align to the frame">
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selected.locked} onclick={() => align("center")}>Centre in frame</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={busy || selected.locked} onclick={() => align("middle")}>Middle of frame</button>
              </div>
            </section>
            <section class="panel" aria-label="Component">
              <h3>Component</h3>
              {#if selected.type === "group" && selected.component_id}
                {@const component = body.components[selected.component_id]}
                {#if component}
                  <p>Placed from <strong>{component.name}</strong>.
                    {#if instanceOutOfDate(selected, component)}It differs from the component now.{:else}It matches the component.{/if}</p>
                  <button type="button" class="btn btn-sm" disabled={busy || selected.locked} onclick={() => void apply([{ op: "update_instance", node_id: selected!.id }])}>Update from component</button>
                  <p class="muted">Updating replaces this layer's contents with the component's, as one version you can undo.</p>
                {:else}
                  <p class="notice-inline">Its component “{selected.component_id}” is no longer in this design. The layers stay; Check reports the broken link.</p>
                {/if}
              {:else}
                <label>Name <input type="text" bind:value={componentName} placeholder={selected.name} maxlength="120" /></label>
                <button type="button" class="btn btn-sm" disabled={busy} onclick={makeComponent}>Make component</button>
                <p class="muted">Keeps a copy of this layer to place again. Placed copies change only when you update them.</p>
              {/if}
            </section>
            {@render notes(selected.id, selected.name)}
          {:else if frame}
            <section class="panel" aria-label="Frame properties">
              <h3>Frame</h3>
              <label>Name <input type="text" value={frame.name} onchange={(e) => setFrameField("name", (e.currentTarget as HTMLInputElement).value)} /></label>
              <div class="grid4">
                <label>Width <input type="number" min="1" max="8000" value={frame.width} onchange={(e) => setFrameField("width", Number((e.currentTarget as HTMLInputElement).value))} /></label>
                <label>Height <input type="number" min="1" max="8000" value={frame.height} onchange={(e) => setFrameField("height", Number((e.currentTarget as HTMLInputElement).value))} /></label>
              </div>
              <label>Background <input type="color" value={(frame.background ?? "#ffffff").slice(0, 7)} onchange={(e) => setFrameField("background", (e.currentTarget as HTMLInputElement).value)} /></label>
              <label class="check"><input type="checkbox" checked={frame.grid.visible} onchange={(e) => setFrameField("grid", { ...frame!.grid, visible: (e.currentTarget as HTMLInputElement).checked })} /> Show the {frame.grid.size}px grid</label>
              <button type="button" class="link danger" disabled={busy || body.frames.length < 2} onclick={removeFrame}>Remove this frame</button>
              <p class="muted">Select a layer on the canvas or in Layers to edit it.</p>
            </section>
            {@render notes(frame.id, frame.name)}
          {/if}
        {:else if rail === "agent"}
          <section class="panel" aria-label="Design agent">
            <h3>Ask the agent</h3>
            <p class="muted">
              It proposes changes to <strong>{frame?.name}</strong> only, as a list you accept or reject.
              Nothing is applied until you do. It cannot place pictures, remove locked layers or
              remove a large group.
            </p>
            <textarea rows="4" bind:value={brief} placeholder="Make the headline bolder and add a call-to-action button under it" aria-label="Brief for the agent"></textarea>
            {#if agentModels.length > 0}
              <label>Model
                <select bind:value={agentChoice} aria-label="Agent model">
                  {#each agentModels as item (item.key)}
                    <option value={item.key}>{providerName(item.profile.provider)} · {modelName(item.model)}</option>
                  {/each}
                </select>
              </label>
            {:else}
              <p class="muted">No chat model is connected. <a href="#/models">Connect one on Models</a>.</p>
            {/if}
            <button type="button" class="btn btn-primary btn-sm" disabled={proposing || !brief.trim() || agentPick === null} onclick={() => void propose()}>
              {proposing ? "Asking…" : "Propose changes"}
            </button>
            <p class="muted">The frame's layers and your brief go to {agentPick ? providerName(agentPick.profile.provider) : "the model"}; text that looks like a credential is removed first.</p>
          </section>
          {#if decision && !decision.ok && decision.conflicts.length > 0}
            <section class="panel conflict" role="alert">
              <h3>Changed since the proposal</h3>
              <p>
                {decision.conflicts.length} of the selected changes touch layers you changed after the agent
                read the design ({decision.conflicts.map((c) => c.node_ids.join(", ")).join("; ")}). Nothing was applied.
              </p>
              {#if pending}
                <button type="button" class="btn btn-sm" disabled={busy} onclick={() => void decide(pending, true, true)}>Apply the rest, keep my changes</button>
              {/if}
            </section>
          {/if}
          {#each proposals as proposal (proposal.proposal_id)}
            <section class="panel proposal" aria-label="Proposal">
              <h3>{PROPOSAL_STATE[proposal.status] ?? proposal.status} · {modelName(proposal.model)} · {relativeTime(proposal.created_at)}</h3>
              <p><strong>{planSummary(proposal)}</strong></p>
              {#if proposal.status === "outcome_unknown"}
                <p class="notice-inline">Raiker stopped while it waited for the model, so whether the provider answered is not known. Nothing was applied and nothing will be retried on its own.</p>
              {:else if proposal.status === "failed"}
                <p class="notice-inline">{designReason(String((proposal.result as Record<string, unknown> | null)?.reason_code ?? ""))}</p>
              {/if}
              {#if proposal.status === "outcome_unknown" || proposal.status === "failed"}
                <button type="button" class="btn btn-ghost btn-sm" onclick={() => (brief = proposal.brief)}>Ask again with this brief</button>
              {/if}
              {#each ["hierarchy", "assumptions", "assets", "validation"] as part (part)}
                {@const items = planItems(proposal, part)}
                {#if items.length > 0}
                  <p class="plan-part"><span class="muted">{part}:</span> {items.join(" · ")}</p>
                {/if}
              {/each}
              <ol class="ops">
                {#each proposal.operations as op (op.index)}
                  <li class:refused={op.status === "refused"}>
                    {#if proposal.status === "pending" && op.status === "valid"}
                      <label class="check">
                        <input type="checkbox" checked={picked[String(op.index)] !== false} onchange={(e) => (picked = { ...picked, [String(op.index)]: (e.currentTarget as HTMLInputElement).checked })} />
                        {op.summary}
                      </label>
                    {:else}
                      {op.summary}
                      {#if op.status === "refused"}<span class="muted"> — refused: {op.reason_code}</span>{/if}
                    {/if}
                  </li>
                {/each}
              </ol>
              {#if proposal.status === "pending"}
                <div class="row-actions">
                  <button type="button" class="btn btn-primary btn-sm" disabled={busy || !proposal.operations.some((op) => op.status === "valid")} onclick={() => void decide(proposal, true)}>Accept selected</button>
                  <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => void decide(proposal, false)}>Reject</button>
                </div>
              {/if}
            </section>
          {/each}
        {:else if rail === "system"}
          <section class="panel" aria-label="Design system">
            <h3>Design system</h3>
            <p>
              {#if open.system_id}
                This design uses <strong>{activeSystem?.name ?? "a system"}</strong> v{open.system_version}.
              {:else}
                No design system chosen.
              {/if}
            </p>
            <label>Choose
              <select bind:value={systemChoice} aria-label="Design system to use" onchange={() => (preview = null)}>
                <option value="">None</option>
                {#each systems as system (system.system_id)}<option value={system.system_id}>{system.name} (v{system.version})</option>{/each}
              </select>
            </label>
            <button type="button" class="btn btn-sm" disabled={busy} onclick={() => void previewSystem()}>Preview the change</button>
            {#if preview}
              <div class="preview" role="status">
                {#if preview.changes.length === 0 && preview.missing.length === 0}
                  <p>No layer changes; only the choice is recorded.</p>
                {/if}
                {#if preview.changes.length > 0}
                  <p>{preview.changes.length} layer {preview.changes.length === 1 ? "change" : "changes"}:</p>
                  <ul>{#each preview.changes as change, i (i)}<li>{change.name}: {change.field} {change.before} → {change.after}</li>{/each}</ul>
                {/if}
                {#if preview.missing.length > 0}
                  <p>Not defined in that system (left as they are):</p>
                  <ul>{#each preview.missing as missing, i (i)}<li>{missing.node_id ?? "frame background"}: {missing.variable}</li>{/each}</ul>
                {/if}
                <button type="button" class="btn btn-primary btn-sm" disabled={busy} onclick={() => void chooseSystem()}>Apply to this design</button>
                <p class="muted">Only this design changes, as one version you can undo.</p>
              </div>
            {/if}
          </section>
          <section class="panel" aria-label="New design system">
            <h3>New design system</h3>
            <label>Import from a tokens file (CSS variables or JSON)
              <input type="file" accept=".css,.json,.txt,text/css,application/json,text/plain" onchange={(event) => void importTokens(event)} />
            </label>
            {#if tokenReport}
              <div class="preview" role="status">
                <p>Read {tokenReport.found} {tokenReport.found === 1 ? "value" : "values"} from {tokenReport.filename} — check them below, then save.</p>
                {#if tokenReport.skipped.length > 0}
                  <p class="muted">Skipped {tokenReport.skipped.length}:</p>
                  <ul class="skipped">{#each tokenReport.skipped as item, i (i)}<li>{item.name}: {item.reason}</li>{/each}</ul>
                {/if}
              </div>
            {/if}
            {#if images.length > 0}
              <div class="variant">
                <label>Or colours from a picture
                  <select bind:value={paletteAsset} aria-label="Picture to read colours from">
                    <option value="">Choose a picture…</option>
                    {#each images.slice(0, 40) as item (item.generation_id)}<option value={item.generation_id}>{item.prompt.slice(0, 60)}</option>{/each}
                  </select>
                </label>
                <button type="button" class="btn btn-ghost btn-sm" disabled={!paletteAsset} onclick={() => void readPalette()}>Read colours</button>
              </div>
            {/if}
            <p class="muted">Both are read on this machine. Nothing is saved until you choose Save system.</p>
            <label>Name <input type="text" bind:value={systemName} placeholder="Acme brand" /></label>
            <label>Colours (name=#rrggbb per line) <textarea rows="3" bind:value={systemColors}></textarea></label>
            <label>Fonts (name=family per line) <textarea rows="2" bind:value={systemFonts}></textarea></label>
            <label>Spacing (name=px per line) <textarea rows="2" bind:value={systemSpacing} placeholder="md=16"></textarea></label>
            <label>Required (comma-separated names) <input type="text" bind:value={systemRequired} placeholder="primary" /></label>
            <label>Where it came from <input type="text" bind:value={systemSource} placeholder="Brand guide 2026, p. 4" /></label>
            <button type="button" class="btn btn-sm" disabled={busy} onclick={() => void saveSystem()}>Save system</button>
          </section>
        {:else if rail === "check"}
          <section class="panel" aria-label="Checks">
            <h3>Checks at v{validation?.version ?? open.current_version}</h3>
            {#if validation === null}
              <p class="muted">Checking…</p>
            {:else}
              <p class="outcome" data-outcome={validation.outcome}>
                {validation.outcome === "passed" ? "Every check passed." : validation.outcome === "failed" ? "Some checks failed." : "Checked what could be checked; some things cannot be known from the design."}
              </p>
              <ul class="checks">
                {#each validation.checks as check (check.check)}
                  <li data-status={check.status}>
                    <span class="status">{CHECK_STATUS[check.status]}</span> {check.label}
                    {#if check.findings.length > 0}
                      <ul>
                        {#each check.findings as finding, i (i)}
                          <li>
                            {#if finding.node_id}
                              <button type="button" class="link" onclick={() => { frameId = finding.frame_id; selectedId = finding.node_id; rail = "inspect"; }}>{findingPlace(finding.frame_id, finding.layer)}</button>:
                            {:else}{finding.layer}:{/if}
                            {finding.message}
                          </li>
                        {/each}
                      </ul>
                    {/if}
                  </li>
                {/each}
              </ul>
              <p class="muted">{validation.validator_version}. Visual quality and accessibility compliance are not judged here.</p>
            {/if}
          </section>
        {:else if rail === "export"}
          <section class="panel" aria-label="Export">
            <h3>Export {frame?.name}</h3>
            <div class="grid4">
              <label>Format
                <select bind:value={exportFormat}>
                  <option value="png">PNG</option><option value="vector_pdf">PDF (vector, selectable text)</option><option value="pdf">PDF (one raster page)</option><option value="svg">SVG (editable)</option><option value="json">JSON (structured)</option>
                </select>
              </label>
              {#if exportFormat === "png" || exportFormat === "pdf"}
                <label>Scale
                  <select bind:value={exportScale}>
                    <option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option>
                  </select>
                </label>
              {/if}
            </div>
            {#if validation && validation.outcome !== "passed"}
              <p class="muted">Checks: {validation.outcome.replace("_", " ")} — recorded with the export.</p>
            {/if}
            <button type="button" class="btn btn-primary btn-sm" disabled={busy} onclick={() => void runExport()}>Export</button>
            {#if exports.length > 0}
              <ul class="exports">
                {#each exports as item (item.export_id)}
                  <li>
                    <button type="button" class="link" onclick={() => void download(item)}>{FORMAT_LABEL[item.format] ?? item.format.toUpperCase()} · v{item.version}</button>
                    <span class="muted">{item.frame_id} · checks {item.validation_outcome.replace("_", " ")} · sha256 {item.sha256.slice(0, 12)}… · {relativeTime(item.created_at)}</span>
                  </li>
                {/each}
              </ul>
            {/if}
          </section>
          <section class="panel" aria-label="Hand to Build">
            <h3>Hand to Build</h3>
            <p class="muted">Gives Build this frame at v{open.current_version} — layers, text, colours and the design system — as a document its composer carries. It is context only: Build's own modes and approvals decide every code change.</p>
            <label>What it should become <input type="text" bind:value={handoffTarget} placeholder="web/src/routes/Landing.svelte" maxlength="300" /></label>
            <button type="button" class="btn btn-sm" disabled={busy} onclick={() => void handOff()}>Hand to Build</button>
            {#if handedOff}<p role="status">Ready in Build's composer as {handedOff}. <a href="#/build">Open Build</a></p>{/if}
            {#if handoffs.length > 0}
              <ul class="exports">{#each handoffs as item (item.handoff_id)}<li class="muted">v{item.version} · {item.frame_ids.join(", ")} · {relativeTime(item.created_at)}</li>{/each}</ul>
            {/if}
          </section>
        {:else if rail === "history"}
          <section class="panel" aria-label="History">
            <h3>History</h3>
            {#if versions === null}
              <p class="muted" role="status">Reading this design's history…</p>
            {:else}
              <ol class="history">
                {#each versions.versions as item (item.version)}
                  <li>
                    <span class="v">v{item.version}</span>
                    <span>{versionKind(item.kind, item.actor)} — {item.summary}</span>
                    <span class="muted">{relativeTime(item.created_at)}{item.scope.length ? ` · ${item.scope.length} ${item.scope.length === 1 ? "layer" : "layers"}` : ""}</span>
                    {#if item.version !== versions.current_version}
                      <button type="button" class="link" disabled={busy} onclick={() => void restoreVersion(item.version)}>Go back to this</button>
                    {:else}
                      <span class="muted">current</span>
                    {/if}
                  </li>
                {/each}
              </ol>
              <p class="muted">Going back adds a new version; nothing here is removed.</p>
            {/if}
          </section>
        {/if}
      </aside>
    </div>
  {/if}
</div>

<style>
  .documents { display: grid; gap: var(--space-3); min-width: 0; }
  .notice, .error { color: var(--danger); margin: 0; }
  .muted { color: var(--text-3); font-size: var(--text-xs); }
  .start { display: grid; gap: var(--space-3); max-width: 48rem; }
  .new-doc { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: end; }
  .new-doc label { display: grid; gap: 0.2rem; font-size: var(--text-xs); color: var(--text-2); }
  .new-doc input { min-width: 16rem; }
  .doc-list, .frames, .layers, .exports, .history, .checks, .ops, .place { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
  .doc-list li { display: flex; align-items: center; gap: var(--space-2); border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--space-2) var(--space-3); background: var(--sunken); }
  .doc-open { flex: 1; display: grid; text-align: left; background: none; border: 0; padding: 0; font: inherit; color: var(--text-1); cursor: pointer; }
  .doc-title { font-weight: 650; }
  .empty { max-width: var(--prose-measure); font-size: var(--text-sm); }
  .doc-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
  .back { display: inline-flex; align-items: center; gap: 0.25rem; background: none; border: 0; padding: 0; font: inherit; font-size: var(--text-sm); color: var(--accent); cursor: pointer; }
  .doc-name { font-weight: 650; min-width: 12rem; flex: 1; }
  .version { font-size: var(--text-xs); color: var(--text-2); border: 1px solid var(--border); border-radius: var(--r-sm); padding: 2px 6px; }
  .workspace { display: grid; grid-template-columns: minmax(0, 15rem) minmax(0, 1fr) minmax(0, 20rem); gap: var(--space-4); align-items: start; }
  .left, .right { display: grid; gap: var(--space-2); align-content: start; min-width: 0; }
  h3 { margin: 0; font-size: var(--text-2xs); font-weight: 750; color: var(--text-3); }
  .row { display: grid; width: 100%; text-align: left; background: none; border: 1px solid transparent; border-radius: var(--r-sm); padding: 4px 6px; font: inherit; font-size: var(--text-sm); color: var(--text-1); cursor: pointer; }
  .row.current { border-color: var(--accent); background: var(--accent-soft); }
  .row:focus-visible, .icon-btn:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 1px; }
  .layers li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 2px; padding-left: calc(var(--depth) * 0.75rem); }
  .layer-row { grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--space-1); align-items: center; }
  .layer-row .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kind { font-size: var(--text-2xs); color: var(--text-3); }
  .badge { font-size: var(--text-2xs); color: var(--accent); border: 1px solid var(--accent-border); border-radius: var(--r-sm); padding: 0 4px; }
  .icon-btn { background: none; border: 0; padding: 2px; color: var(--text-2); cursor: pointer; border-radius: var(--r-sm); }
  .add-row, .row-actions { display: flex; flex-wrap: wrap; gap: var(--space-1); align-items: center; }
  .variant { display: flex; flex-wrap: wrap; gap: var(--space-1); align-items: end; }
  .variant label { display: grid; gap: 0.2rem; font-size: var(--text-xs); color: var(--text-2); }
  .place { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .place button { padding: 0; border: 1px solid var(--canvas-edge); border-radius: var(--r-sm); background: var(--sunken); cursor: pointer; overflow: hidden; }
  .place img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; }
  .stage { display: grid; gap: var(--space-2); min-width: 0; }
  .stage-head { margin: 0; }
  .canvas { width: 100%; height: auto; max-height: min(72vh, 52rem); border: 1px solid var(--canvas-edge); border-radius: var(--r-md); background: var(--sunken); }
  .canvas:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
  .canvas :global(.hit) { fill: transparent; stroke: transparent; cursor: pointer; }
  .canvas :global(.hit:hover) { stroke: var(--accent-border); stroke-width: 2; vector-effect: non-scaling-stroke; }
  .canvas :global(.hit.selected) { stroke: var(--accent); stroke-width: 2; stroke-dasharray: 6 3; vector-effect: non-scaling-stroke; }
  .canvas :global(.missing) { fill: var(--sunken); stroke: var(--text-3); stroke-dasharray: 4 4; }
  .canvas :global(.grid-line) { fill: none; stroke: var(--border); stroke-width: 0.5; }
  .canvas :global(.hit.locked) { cursor: not-allowed; }
  .canvas :global(.hit:not(.locked)) { cursor: move; }
  .canvas :global(.guide) { stroke: var(--accent); stroke-width: 1; stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; pointer-events: none; }
  .canvas :global(.handle) { fill: var(--surface); stroke: var(--accent); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
  .canvas :global(.handle-n), .canvas :global(.handle-s) { cursor: ns-resize; }
  .canvas :global(.handle-e), .canvas :global(.handle-w) { cursor: ew-resize; }
  .canvas :global(.handle-nw), .canvas :global(.handle-se) { cursor: nwse-resize; }
  .canvas :global(.handle-ne), .canvas :global(.handle-sw) { cursor: nesw-resize; }
  .canvas :global(.handle.rotate) { cursor: grab; }
  .canvas :global(.rotate-stem) { stroke: var(--accent); stroke-width: 1; vector-effect: non-scaling-stroke; }
  .canvas :global(.note-pin circle) { fill: var(--warning); stroke: var(--surface); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
  .canvas :global(.note-pin text) { fill: var(--text-1); font-weight: 700; pointer-events: none; }
  .canvas :global(.note-pin) { pointer-events: none; }
  .canvas { touch-action: none; }
  .components { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
  .components li { display: flex; align-items: center; gap: var(--space-1); font-size: var(--text-sm); }
  .components .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .import-picture { display: inline-flex; cursor: pointer; }
  .note { border: 1px solid var(--border); border-radius: var(--r-sm); padding: var(--space-1) var(--space-2); background: var(--sunken); display: grid; gap: 2px; }
  .note p { margin: 0; font-size: var(--text-sm); white-space: pre-wrap; }
  .note.resolved p { color: var(--text-3); text-decoration: line-through; }
  .notice-inline { margin: 0; color: var(--warning); font-size: var(--text-sm); }
  .skipped { margin: 0; padding-left: 1rem; font-size: var(--text-xs); }
  .canvas :global(.canvas-text) { width: 100%; height: 100%; overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere; }
  .panel { display: grid; gap: var(--space-2); }
  .panel label { display: grid; gap: 0.2rem; font-size: var(--text-xs); color: var(--text-2); }
  .panel label.check { display: flex; align-items: center; gap: 0.35rem; }
  .grid4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(4.5rem, 1fr)); gap: var(--space-2); }
  .grid4 input, .grid4 select { width: 100%; min-width: 0; }
  .crop { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-1); border: 1px solid var(--border); border-radius: var(--r-sm); padding: var(--space-2); }
  .crop legend { font-size: var(--text-xs); color: var(--text-2); }
  .crop input { width: 100%; min-width: 0; }
  .proposal, .conflict, .preview { border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--space-2) var(--space-3); background: var(--sunken); }
  .conflict { border-color: var(--warning); }
  .ops li { font-size: var(--text-sm); }
  .ops li.refused { color: var(--text-3); }
  .plan-part { margin: 0; font-size: var(--text-xs); }
  .checks > li { font-size: var(--text-sm); }
  .checks ul { margin: 0.2rem 0 0.4rem 1rem; padding: 0; font-size: var(--text-xs); }
  .status { font-weight: 650; }
  .checks [data-status="fail"] > .status { color: var(--danger); }
  .checks [data-status="pass"] > .status { color: var(--success); }
  .checks [data-status="unsupported"] > .status, .checks [data-status="unknown"] > .status { color: var(--warning); }
  .outcome { margin: 0; font-weight: 650; }
  .history li { display: grid; gap: 2px; font-size: var(--text-sm); border-bottom: 1px solid var(--border); padding-bottom: var(--space-1); }
  .v { font-weight: 650; }
  .link { background: none; border: 0; padding: 0; font: inherit; color: var(--accent); cursor: pointer; text-decoration: underline; }
  .link.danger { color: var(--danger); }
  .link:disabled { color: var(--text-3); cursor: default; }
  .deleted-docs ul { list-style: none; padding: 0; margin: var(--space-1) 0 0; display: grid; gap: var(--space-1); }
  @media (max-width: 79.9rem) {
    .workspace { grid-template-columns: minmax(0, 13rem) minmax(0, 1fr); }
    .right { grid-column: 1 / -1; }
  }
  @media (max-width: 47.9rem) {
    .workspace { grid-template-columns: minmax(0, 1fr); }
    .left { order: 2; }
    .right { order: 3; }
    .new-doc input { min-width: 0; width: 100%; }
  }
  @media (prefers-reduced-motion: reduce) {
    .canvas :global(*) { transition: none; }
  }
</style>
