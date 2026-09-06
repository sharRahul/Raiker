<script lang="ts">
  import { onMount } from "svelte";
  import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type Simulation, type SimulationNodeDatum } from "d3-force";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { BrainEdge, BrainNode, BrainSourceBrowse, BrainSourceReview, BrainView as BrainData } from "../apiTypes";

  type MotionMode = "paused" | "activity" | "alive";
  type GraphNode = BrainNode & SimulationNodeDatum & { degree: number; virtual?: boolean; color?: string; pinned?: boolean };
  type GraphLink = BrainEdge & { source: string | GraphNode; target: string | GraphNode };
  type Group = { name: string; query: string; color: string };

  // BUG-218 — Chat and Build are different work and now say so. `build` and
  // `task_run` are new node types; `session` stays for anything whose origin
  // the store does not recognise, so an unknown surface still draws.
  const COLORS: Record<string, string> = {
    // Every entry here is a saturated mid-tone that reads on either ground —
    // this is a categorical key, so it stays fixed across themes rather than
    // following the palette. `user` was the exception at #f3f5fa: near-white,
    // picked to be the brightest thing on a canvas that was hard-coded dark.
    // Once the canvas follows the theme, that node vanished into the light one.
    // Rose is the same brightness, distinct from the purple, orange and yellow
    // already in the key, and visible on both.
    user: "#fb7185", workspace: "#77d5ee", project: "#a78bfa", source: "#60a5fa",
    folder: "#818cf8", file: "#60a5fa", session: "#58d68d", conversation: "#58d68d",
    build: "#38bdf8", task_run: "#f5b942",
    task: "#f5b942", memory: "#2dd4bf", entity: "#14b8a6", tool: "#fb923c", approval: "#facc15",
    agent: "#c084fc", schedule: "#f5b942", backup: "#60a5fa",
  };
  // The filter row is what an owner reaches for to answer "show me only my
  // files". It lists what the map now actually contains rather than what it
  // contained when the map was mostly event rows.
  const FILTER_TYPES = [
    "conversation", "build", "project", "folder", "file", "source",
    "task", "memory", "entity", "tool", "approval",
  ];
  const FILTER_LABELS: Record<string, string> = {
    conversation: "Chats", build: "Build", project: "Projects", folder: "Folders",
    file: "Files", source: "Context", task: "Tasks", memory: "Memories", entity: "Entities",
    tool: "Tools", approval: "Approvals",
  };

  let brain = $state<BrainData | null>(null);
  let loadError = $state<string | null>(null);
  let refreshing = $state(false);
  let updatedAt = $state<string | null>(null);
  let selectedIds = $state<string[]>([]);
  let hoveredId = $state<string | null>(null);
  let centreId = $state<string | null>(null);
  let graphMode = $state<"global" | "local">("global");
  let depth = $state(2);
  let search = $state("");
  let enabledTypes = $state<Record<string, boolean>>(Object.fromEntries(FILTER_TYPES.map((type) => [type, true])));
  let showOrphans = $state(true);
  let showLabels = $state(true);
  let showArrows = $state(true);
  let showParticles = $state(true);
  let settingsOpen = $state(false);
  let summaryOpen = $state(false);
  let sourceOpen = $state(false);
  let inspectorOpen = $state(false);
  let sourcePath = $state("");
  let grantPath = $state("");
  let uploadFile: File | null = null;
  let uploadName = $state<string | null>(null);
  let uploadConsent = $state(false);
  let sourceError = $state<string | null>(null);
  let sourceBusy = $state(false);
  let sourceBrowse = $state<BrainSourceBrowse | null>(null);
  let sourceReview = $state<BrainSourceReview | null>(null);
  let motion = $state<MotionMode>("alive");
  let centerStrength = $state(0.08);
  let chargeStrength = $state(-220);
  let linkStrength = $state(0.35);
  let linkDistance = $state(85);
  let collisionPadding = $state(8);
  let nodeScale = $state(1);
  let linkThickness = $state(1);
  let labelThreshold = $state(1.15);
  let groups = $state<Group[]>([
    { name: "Projects", query: "type:project", color: "#a78bfa" },
    { name: "Approved knowledge", query: "type:memory status:approved", color: "#2dd4bf" },
  ]);
  let newGroupOpen = $state(false);
  let groupName = $state("");
  let groupQuery = $state("");
  let groupColor = $state("#ef6a78");
  let graphElement = $state<HTMLDivElement>();
  let simulation: Simulation<GraphNode, GraphLink> | null = null;
  let graphWidth = $state(900);
  let graphHeight = $state(620);
  let renderedNodes = $state<GraphNode[]>([]);
  let renderedLinks = $state<GraphLink[]>([]);
  const positionCache = new Map<string, GraphNode>();
  let transform = $state({ x: 0, y: 0, k: 1 });
  let savedPositions = $state<Record<string, { x: number; y: number; pinned: boolean }>>({});
  let preferencesLoaded = $state(false);
  let panning = false;
  let panOrigin = { x: 0, y: 0, tx: 0, ty: 0 };
  let contextMenu = $state<{ x: number; y: number; node: GraphNode } | null>(null);

  async function load() {
    refreshing = true; loadError = null;
    try {
      brain = await api.brain();
      updatedAt = new Date().toISOString();
    } catch (error) {
      loadError = error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
    } finally { refreshing = false; }
  }

  async function loadPreferences() {
    try {
      const raw = (await api.brainPreferences()).settings as Record<string, unknown>;
      if (raw.transform && typeof raw.transform === "object") transform = { ...transform, ...(raw.transform as typeof transform) };
      if (raw.display && typeof raw.display === "object") {
        const display = raw.display as Partial<{ showOrphans: boolean; showLabels: boolean; showArrows: boolean; showParticles: boolean; nodeScale: number; linkThickness: number; labelThreshold: number }>;
        showOrphans = display.showOrphans ?? showOrphans; showLabels = display.showLabels ?? showLabels;
        showArrows = display.showArrows ?? showArrows; showParticles = display.showParticles ?? showParticles;
        nodeScale = display.nodeScale ?? nodeScale; linkThickness = display.linkThickness ?? linkThickness;
        labelThreshold = display.labelThreshold ?? labelThreshold;
      }
      if (raw.forces && typeof raw.forces === "object") {
        const forces = raw.forces as Partial<{ centerStrength: number; chargeStrength: number; linkStrength: number; linkDistance: number; collisionPadding: number }>;
        centerStrength = forces.centerStrength ?? centerStrength; chargeStrength = forces.chargeStrength ?? chargeStrength;
        linkStrength = forces.linkStrength ?? linkStrength; linkDistance = forces.linkDistance ?? linkDistance;
        collisionPadding = forces.collisionPadding ?? collisionPadding;
      }
      if (Array.isArray(raw.groups)) groups = raw.groups as Group[];
      if (raw.positions && typeof raw.positions === "object") savedPositions = raw.positions as typeof savedPositions;
      if (raw.filters && typeof raw.filters === "object") enabledTypes = { ...enabledTypes, ...(raw.filters as Record<string, boolean>) };
      if (typeof raw.motion === "string" && ["paused", "activity", "alive"].includes(raw.motion)) motion = raw.motion as MotionMode;
    } catch { /* Older runtimes simply start with the documented defaults. */ }
    finally { preferencesLoaded = true; }
  }

  onMount(() => {
    void loadPreferences();
    void load();
    const timer = window.setInterval(() => void load(), 15_000);
    return () => { window.clearInterval(timer); simulation?.stop(); };
  });

  /**
   * Keep the canvas the size of the box it is drawn in.
   *
   * This used to attach in `onMount`, once, to whatever `graphElement` happened
   * to be — and the graph lives on the `{:else}` branch of a load state, so on
   * any render where that branch was not up yet the observer attached to
   * nothing and never ran again. `graphWidth` then stayed at its 900px default
   * on every window: on a phone the canvas was more than twice the viewport,
   * two-thirds of the graph was off screen, and the centring force was aiming at
   * a point 450px from a 390px-wide edge. An effect re-attaches whenever the
   * element appears, which is the only version of this that cannot silently
   * do nothing.
   */
  $effect(() => {
    const element = graphElement;
    if (element === undefined || typeof ResizeObserver === "undefined") return;
    const resize = new ResizeObserver(([entry]) => {
      graphWidth = Math.max(320, entry.contentRect.width);
      graphHeight = Math.max(420, entry.contentRect.height);
      simulation?.force("center", forceCenter(graphWidth / 2, graphHeight / 2).strength(centerStrength)).alpha(0.2).restart();
    });
    resize.observe(element);
    return () => resize.disconnect();
  });

  $effect(() => {
    if (!preferencesLoaded) return;
    const settings = {
      transform, display: { showOrphans, showLabels, showArrows, showParticles, nodeScale, linkThickness, labelThreshold },
      forces: { centerStrength, chargeStrength, linkStrength, linkDistance, collisionPadding },
      groups, positions: savedPositions, filters: enabledTypes, motion,
    };
    const timer = window.setTimeout(() => { void api.saveBrainPreferences(settings).catch(() => undefined); }, 500);
    return () => window.clearTimeout(timer);
  });

  const rawNodes = $derived(brain?.nodes ?? []);
  const rawEdges = $derived(brain?.edges ?? []);
  const degrees = $derived.by(() => {
    const values = new Map<string, number>();
    for (const edge of rawEdges) {
      values.set(edge.source, (values.get(edge.source) ?? 0) + 1);
      values.set(edge.target, (values.get(edge.target) ?? 0) + 1);
    }
    return values;
  });
  // The instructional graph a brand-new workspace is given: three placeholder
  // nodes and two placeholder edges that stand in for records nobody has made
  // yet. One derived flag decides both the overlay that says the graph is empty
  // and what the count pill claims, because they used to disagree — the pill
  // counted the placeholders as workspace records and read "3 nodes · 2
  // relationships" directly above "Build your knowledge graph".
  const showingStarter = $derived(rawNodes.length <= 1 && search === "" && graphMode === "global");
  const sourceRoots = $derived(rawNodes.filter((node) => ["file", "folder"].includes(node.node_type) && node.status === "selected"));
  const summary = $derived([
    ["Records", rawNodes.length], ["Relationships", rawEdges.length],
    ["Sources", rawNodes.filter((node) => ["file", "folder"].includes(node.node_type)).length],
    ["Approved memories", rawNodes.filter((node) => node.node_type === "memory").length],
  ] as [string, number][]);

  function matchesQuery(node: BrainNode, query: string): boolean {
    const terms = query.toLowerCase().match(/(?:[^\s"]+|"[^"]*")+/g) ?? [];
    return terms.every((term) => {
      const [key, rawValue] = term.split(":", 2);
      if (!rawValue) return `${node.label} ${node.detail ?? ""}`.toLowerCase().includes(key);
      const value = rawValue.replaceAll('"', "");
      if (key === "type") return node.node_type.toLowerCase() === value;
      if (key === "status" || key === "approval") return node.status.toLowerCase().includes(value);
      return `${node.label} ${node.detail ?? ""}`.toLowerCase().includes(value);
    });
  }

  function groupColorFor(node: BrainNode): string {
    return groups.find((group) => matchesQuery(node, group.query))?.color ?? COLORS[node.node_type] ?? "#94a3b8";
  }

  const localIds = $derived.by(() => {
    if (graphMode === "global" || !centreId) return new Set(rawNodes.map((node) => node.node_id));
    const found = new Set([centreId]); let frontier = new Set([centreId]);
    for (let step = 0; step < depth; step += 1) {
      const next = new Set<string>();
      for (const edge of rawEdges) {
        if (frontier.has(edge.source) && !found.has(edge.target)) next.add(edge.target);
        if (frontier.has(edge.target) && !found.has(edge.source)) next.add(edge.source);
      }
      next.forEach((id) => found.add(id)); frontier = next;
    }
    return found;
  });

  const visibleData = $derived.by(() => {
    let nodes = rawNodes.filter((node) => {
      const typeOn = enabledTypes[node.node_type] ?? true;
      return typeOn && localIds.has(node.node_id) && matchesQuery(node, search);
    });
    if (!showOrphans) nodes = nodes.filter((node) => (degrees.get(node.node_id) ?? 0) > 0);
    let edges = rawEdges.filter((edge) => nodes.some((node) => node.node_id === edge.source) && nodes.some((node) => node.node_id === edge.target));
    if (showingStarter) {
      const principal = nodes[0] ?? { node_id: "starter:user", node_type: "user", label: "You", status: "active", detail: null, progress_percent: null, is_real: false };
      nodes = [principal, { node_id: "starter:workspace", node_type: "workspace", label: "Workspace", status: "active", detail: "Your governed workspace", progress_percent: null, is_real: false }, { node_id: "starter:add", node_type: "source", label: "Add first source", status: "instruction", detail: "Instructional prompt", progress_percent: null, is_real: false }];
      edges = [{ source: principal.node_id, target: "starter:workspace", relationship: "owns", is_active: false }, { source: "starter:workspace", target: "starter:add", relationship: "instruction", is_active: false }];
    }
    return { nodes, edges };
  });

  function radius(node: GraphNode): number { return Math.max(4, Math.min(20, 4 + Math.sqrt(node.degree) * 2.5)) * nodeScale; }
  function nodeId(value: string | GraphNode): string { return typeof value === "string" ? value : value.node_id; }
  function graphNode(value: string | GraphNode): GraphNode | null { return typeof value === "string" ? null : value; }
  function connectedTo(id: string | null): Set<string> {
    if (!id) return new Set();
    const result = new Set([id]);
    for (const edge of renderedLinks) {
      const source = nodeId(edge.source); const target = nodeId(edge.target);
      if (source === id) result.add(target); if (target === id) result.add(source);
    }
    return result;
  }
  const highlighted = $derived(connectedTo(hoveredId ?? selectedIds[0] ?? null));

  $effect(() => {
    const data = visibleData;
    const nodes: GraphNode[] = data.nodes.map((node) => ({
      ...node, degree: degrees.get(node.node_id) ?? (node.node_id === "starter:workspace" ? 2 : 1),
      color: groupColorFor(node), x: positionCache.get(node.node_id)?.x ?? savedPositions[node.node_id]?.x ?? graphWidth / 2 + (Math.random() - 0.5) * 80,
      y: positionCache.get(node.node_id)?.y ?? savedPositions[node.node_id]?.y ?? graphHeight / 2 + (Math.random() - 0.5) * 80,
      fx: savedPositions[node.node_id]?.pinned ? savedPositions[node.node_id].x : undefined,
      fy: savedPositions[node.node_id]?.pinned ? savedPositions[node.node_id].y : undefined,
      pinned: savedPositions[node.node_id]?.pinned ?? false,
    }));
    const links: GraphLink[] = data.edges.map((edge) => ({ ...edge }));
    simulation?.stop();
    simulation = forceSimulation<GraphNode>(nodes)
      .velocityDecay(0.32)
      .force("center", forceCenter(graphWidth / 2, graphHeight / 2).strength(centerStrength))
      .force("charge", forceManyBody<GraphNode>().strength(chargeStrength))
      .force("link", forceLink<GraphNode, GraphLink>(links).id((node) => node.node_id).distance(linkDistance).strength(linkStrength))
      .force("collision", forceCollide<GraphNode>().radius((node) => radius(node) + collisionPadding))
      .on("tick", () => { nodes.forEach((node) => positionCache.set(node.node_id, node)); renderedNodes = [...nodes]; renderedLinks = [...links]; })
      // The layout has stopped moving, which is the only moment a fit means
      // anything. `alive` motion never reaches it; the timer covers that.
      .on("end", () => autoFit());
    if (motion === "paused") simulation.stop();
    else if (motion === "alive") simulation.alphaTarget(0.015).restart();
    else simulation.alphaTarget(0).restart();
    renderedNodes = nodes; renderedLinks = links;
    const currentSimulation = simulation;
    return () => currentSimulation.stop();
  });

  function selectNode(event: MouseEvent, node: GraphNode) {
    event.stopPropagation(); contextMenu = null;
    if (node.node_id === "starter:add") { void openSourcePicker(); return; }
    selectedIds = event.shiftKey ? (selectedIds.includes(node.node_id) ? selectedIds.filter((id) => id !== node.node_id) : [...selectedIds, node.node_id]) : [node.node_id];
    inspectorOpen = true;
  }
  function clearGraphSelection(event: MouseEvent) {
    const target = event.target;
    if (!(target instanceof Element) || target.closest(".graph-node, button, input, label, details, aside, .context-menu")) return;
    selectedIds = [];
    inspectorOpen = false;
    contextMenu = null;
  }
  function modal(node: HTMLDialogElement) {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (typeof node.showModal === "function") node.showModal();
    else node.setAttribute("open", "");
    return { destroy() { returnFocus?.focus(); } };
  }
  function closeSourceDialog(event?: Event) {
    event?.preventDefault();
    sourceOpen = false;
  }
  function centreNode(node: GraphNode) { centreId = node.node_id; graphMode = "local"; selectedIds = [node.node_id]; inspectorOpen = true; }
  function dragStart(event: PointerEvent, node: GraphNode) { event.stopPropagation(); (event.currentTarget as Element).setPointerCapture(event.pointerId); node.fx = node.x; node.fy = node.y; simulation?.alphaTarget(0.1).restart(); }
  function dragMove(event: PointerEvent, node: GraphNode) { if (!(event.currentTarget as Element).hasPointerCapture(event.pointerId)) return; node.fx = (event.offsetX - transform.x) / transform.k; node.fy = (event.offsetY - transform.y) / transform.k; }
  function dragEnd(event: PointerEvent, node: GraphNode) { (event.currentTarget as Element).releasePointerCapture(event.pointerId); node.pinned = true; savedPositions = { ...savedPositions, [node.node_id]: { x: node.fx ?? node.x ?? 0, y: node.fy ?? node.y ?? 0, pinned: true } }; simulation?.alphaTarget(motion === "alive" ? 0.015 : 0); }
  function unpin(node: GraphNode) { node.fx = null; node.fy = null; node.pinned = false; const next = { ...savedPositions }; delete next[node.node_id]; savedPositions = next; simulation?.alpha(0.25).restart(); contextMenu = null; }
  async function rejectRelationship(edge: GraphLink) {
    if (!edge.relationship_id || !edge.owner_can_reject) return;
    const reason = window.prompt("Why is this relationship incorrect?", "Incorrect relationship");
    if (!reason?.trim()) return;
    try { await api.rejectMemoryRelationship(edge.relationship_id, reason.trim()); await load(); }
    catch { loadError = "This relationship could not be rejected. Refresh in case it changed elsewhere."; }
  }
  function onWheel(event: WheelEvent) { event.preventDefault(); const next = Math.max(0.35, Math.min(3, transform.k * Math.exp(-event.deltaY * 0.001))); const rect = graphElement?.getBoundingClientRect(); if (!rect) return; const px = event.clientX - rect.left; const py = event.clientY - rect.top; transform = { k: next, x: px - ((px - transform.x) / transform.k) * next, y: py - ((py - transform.y) / transform.k) * next }; }
  function panStart(event: PointerEvent) { if (event.target !== event.currentTarget && (event.target as Element).closest(".graph-stage")) return; panning = true; panOrigin = { x: event.clientX, y: event.clientY, tx: transform.x, ty: transform.y }; (event.currentTarget as Element).setPointerCapture(event.pointerId); }
  function panMove(event: PointerEvent) { if (panning) transform = { ...transform, x: panOrigin.tx + event.clientX - panOrigin.x, y: panOrigin.ty + event.clientY - panOrigin.y }; }
  function panEnd(event: PointerEvent) { panning = false; if ((event.currentTarget as Element).hasPointerCapture(event.pointerId)) (event.currentTarget as Element).releasePointerCapture(event.pointerId); }
  function graphInteractions(node: HTMLDivElement) {
    node.addEventListener("wheel", onWheel);
    node.addEventListener("pointerdown", panStart);
    node.addEventListener("pointermove", panMove);
    node.addEventListener("pointerup", panEnd);
    node.addEventListener("click", clearGraphSelection);
    return { destroy() {
      node.removeEventListener("wheel", onWheel);
      node.removeEventListener("pointerdown", panStart);
      node.removeEventListener("pointermove", panMove);
      node.removeEventListener("pointerup", panEnd);
      node.removeEventListener("click", clearGraphSelection);
    } };
  }
  /**
   * Bring every node on screen — which is what "Fit" has to mean.
   *
   * It used to reset the transform to the identity, which is not a fit: on a
   * phone-width window the graph's own extent is several times the viewport, so
   * pressing **Fit** left most of the nodes off screen and the control read as
   * broken. It now measures what is actually laid out and scales to it.
   *
   * Zooming *in* is capped at 1: a two-node graph blown up to fill a monitor is
   * a worse picture than a small one in the middle, and it would make Fit feel
   * like a different control on a sparse graph than on a dense one.
   */
  function fitGraph() {
    const placed = renderedNodes.filter(
      (node) => Number.isFinite(node.x) && Number.isFinite(node.y),
    );
    if (placed.length === 0) {
      transform = { x: 0, y: 0, k: 1 };
      return;
    }
    const margin = 48;
    const pad = Math.max(...placed.map((node) => radius(node))) + 18;
    const minX = Math.min(...placed.map((node) => (node.x ?? 0))) - pad;
    const maxX = Math.max(...placed.map((node) => (node.x ?? 0))) + pad;
    const minY = Math.min(...placed.map((node) => (node.y ?? 0))) - pad;
    const maxY = Math.max(...placed.map((node) => (node.y ?? 0))) + pad;
    const width = Math.max(1, maxX - minX);
    const height = Math.max(1, maxY - minY);
    const k = Math.max(
      0.35,
      Math.min(1, (graphWidth - margin) / width, (graphHeight - margin) / height),
    );
    transform = {
      k,
      x: graphWidth / 2 - ((minX + maxX) / 2) * k,
      y: graphHeight / 2 - ((minY + maxY) / 2) * k,
    };
    // Deliberately no `alpha().restart()`. Re-agitating the layout is what the
    // old implementation did, and it moved the very nodes the fit had just
    // measured — so the graph drifted back off screen a second later.
  }

  /**
   * Fit once, when the first layout settles, unless the owner has a saved view.
   *
   * A stored transform is a choice; the identity transform on a first visit is
   * not, and on a narrow window it put the graph off screen before the owner had
   * any reason to look for a **Fit** button.
   *
   * Triggered by the simulation's own `end`, not by a timer: a graph fitted
   * while it is still spreading is fitted to where it was, not to where it
   * lands. The timer below is only the fallback for `alive` motion, which never
   * ends by design.
   */
  let autoFitted = false;
  function autoFit() {
    if (autoFitted || renderedNodes.length === 0) return;
    autoFitted = true;
    fitGraph();
  }

  $effect(() => {
    if (autoFitted || !preferencesLoaded) return;
    // A stored view is the owner's; leave it exactly as they left it.
    if (transform.x !== 0 || transform.y !== 0 || transform.k !== 1) {
      autoFitted = true;
      return;
    }
    const timer = window.setTimeout(autoFit, 4_000);
    return () => window.clearTimeout(timer);
  });

  // The picker opens on the *boundary*, never on a listing. Browsing starts
  // from a root the owner already has — a project's files, what Raiker
  // generated, approved memory, or a folder they granted — so there is no
  // moment at which the dialog offers the whole installation to index.
  async function openSourcePicker() {
    sourceOpen = true; sourceError = null; sourceReview = null;
    sourcePath = ""; grantPath = ""; uploadConsent = false; uploadName = null;
    try { sourceBrowse = await api.browseBrainSources(""); } catch { sourceBrowse = null; }
  }
  async function browseSource(path: string) {
    sourceBusy = true; sourceError = null; sourceReview = null;
    try { sourceBrowse = await api.browseBrainSources(path); sourcePath = sourceBrowse.path; }
    catch { sourceError = "Could not open that folder. It may have been moved, or its access revoked."; }
    finally { sourceBusy = false; }
  }
  async function reviewSource() {
    if (!sourcePath.trim()) return; sourceBusy = true; sourceError = null;
    try { sourceReview = await api.reviewBrainSource(sourcePath.trim()); }
    catch (error) { sourceError = error instanceof ApiError ? "Choose a file or folder inside one of the places listed above. Nothing outside them is readable." : "Could not add this source."; }
    finally { sourceBusy = false; }
  }
  async function addSource() {
    if (!sourceReview) return;
    sourceBusy = true; sourceError = null;
    try { await api.addBrainSource(sourceReview.path); sourcePath = ""; sourceReview = null; sourceOpen = false; await load(); }
    catch { sourceError = "Could not add this reviewed source."; }
    finally { sourceBusy = false; }
  }

  // Granting a folder is how a file from the computer joins the graph *without*
  // being copied: Raiker reads it where it is, and revoking the grant removes
  // both the access and everything indexed under it.
  async function grantFolder() {
    const path = grantPath.trim();
    if (!path) return;
    sourceBusy = true; sourceError = null;
    try {
      const granted = await api.grantBrainSourceFolder(path);
      grantPath = "";
      await browseSource(granted.root_id);
    } catch (error) {
      sourceError = error instanceof ApiError
        ? grantMessage(error.reasonCode)
        : "Could not grant that folder.";
    } finally { sourceBusy = false; }
  }
  function grantMessage(reason: string | null): string {
    if (reason === "brain_grant_requires_absolute_path") return "Give the folder's full path, starting from the top of the drive.";
    if (reason === "brain_grant_not_found") return "There is no folder at that path on this machine.";
    if (reason === "brain_grant_not_a_directory") return "That path is a file. Grant the folder that holds it, then pick the file inside.";
    if (reason === "brain_grant_is_runtime_directory") return "That is Raiker's own runtime folder. Its documents are already listed above.";
    return "Could not grant that folder.";
  }
  async function revokeFolder(rootId: string) {
    sourceBusy = true; sourceError = null;
    try { await api.revokeBrainSourceFolder(rootId); sourceBrowse = await api.browseBrainSources(""); sourcePath = ""; sourceReview = null; await load(); }
    catch { sourceError = "Could not revoke that folder."; }
    finally { sourceBusy = false; }
  }

  // Uploading duplicates the file into the workspace, so it is behind an
  // explicit consent — choosing a file is not agreeing to store it.
  function pickUpload(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    uploadFile = input.files?.[0] ?? null;
    uploadName = uploadFile?.name ?? null;
    sourceError = null;
  }
  async function uploadCopy() {
    if (!uploadFile || !uploadConsent) return;
    sourceBusy = true; sourceError = null;
    try {
      const buffer = new Uint8Array(await uploadFile.arrayBuffer());
      let binary = "";
      for (const byte of buffer) binary += String.fromCharCode(byte);
      await api.uploadBrainSourceFile(uploadFile.name, btoa(binary), true);
      uploadFile = null; uploadName = null; uploadConsent = false;
      sourceOpen = false;
      await load();
    } catch (error) {
      sourceError = error instanceof ApiError && error.reasonCode === "brain_upload_unsupported_file_type"
        ? "Raiker reads text documents and source files. That file type is not one of them."
        : error instanceof ApiError && error.reasonCode === "brain_upload_too_large"
          ? "That file is larger than 5 MB. Grant its folder instead, and Raiker will read it where it is."
          : "Could not store that file.";
    } finally { sourceBusy = false; }
  }
  async function removeSource(path: string) { try { await api.removeBrainSource(path); await load(); } catch { sourceError = "Could not remove this source."; } }
  function addGroup() { if (!groupName.trim() || !groupQuery.trim()) return; groups = [...groups, { name: groupName.trim(), query: groupQuery.trim(), color: groupColor }]; groupName = ""; groupQuery = ""; newGroupOpen = false; }
  function statusLabel(status: string): string { return status.replaceAll("_", " ").replace(/^./, (value) => value.toUpperCase()); }
  const selected = $derived(renderedNodes.find((node) => node.node_id === selectedIds[0]) ?? null);
  const selectedConnections = $derived(selected ? renderedLinks.filter((edge) => nodeId(edge.source) === selected.node_id || nodeId(edge.target) === selected.node_id) : []);
</script>

{#if loadError}
  <PageState state="error" title="Couldn't load the knowledge graph" detail={loadError} />
{:else if brain === null}
  <PageState state="loading" title="Loading the knowledge graph…" />
{:else}
  <section class="knowledge-shell" aria-label="Knowledge Map">
    <header class="graph-toolbar">
      <div class="title-block"><span class="eyebrow">Workspace intelligence</span><h2>Knowledge Map</h2></div>
      <!-- Global/Local was a segmented control that spent most of its life half
           disabled: `centreNode()` already switches to local when you focus a
           node, so the switch's only unique job was getting back out again. That
           belongs beside the depth slider, which is the other control that only
           exists in local mode, rather than holding permanent toolbar space to
           say which mode you are already looking at.

           Fullscreen went too. The graph fills the content area already, and the
           browser's own fullscreen took the sidebar and topbar away without
           putting anything in their place. -->
      <button class="icon-button" aria-label="Add workspace source" title="Add source" onclick={() => void openSourcePicker()}>+</button>
      <button class="icon-button" aria-label="Graph settings" aria-expanded={settingsOpen} onclick={() => settingsOpen = !settingsOpen}><Icon name="settings" size="md" /></button>
      <label class="search"><Icon name="search" size="md" /><input bind:value={search} placeholder="Search records or use type:, status:…" aria-label="Search records" /></label>
    </header>

    <div class="graph-workspace" bind:this={graphElement} use:graphInteractions role="application" aria-label="Interactive force-directed knowledge graph">
      <div class="vignette"></div>
      <svg class="graph-stage" width={graphWidth} height={graphHeight} aria-label={`${renderedNodes.length} node${renderedNodes.length === 1 ? "" : "s"} and ${renderedLinks.length} relationship${renderedLinks.length === 1 ? "" : "s"}`}>
        <defs><marker id="arrow" viewBox="0 -5 10 10" refX="16" refY="0" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,-5L10,0L0,5" fill="rgba(180,188,205,.55)" /></marker></defs>
        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
          {#each renderedLinks as edge (`${nodeId(edge.source)}:${nodeId(edge.target)}:${edge.relationship}`)}
            {@const source = graphNode(edge.source)}
            {@const target = graphNode(edge.target)}
            {#if source && target}
              {@const active = highlighted.has(source.node_id) && highlighted.has(target.node_id)}
              <line class:highlighted={active} class:instruction={edge.relationship === "instruction"} x1={source.x ?? 0} y1={source.y ?? 0} x2={target.x ?? 0} y2={target.y ?? 0} style={`--link-width:${linkThickness}`} marker-end={showArrows && edge.relationship !== "instruction" ? "url(#arrow)" : undefined} />
              {#if showParticles && edge.is_active}<circle class="particle" r="2" fill={source.color}><animateMotion dur="1.8s" repeatCount="indefinite" path={`M ${source.x ?? 0} ${source.y ?? 0} L ${target.x ?? 0} ${target.y ?? 0}`} /></circle>{/if}
            {/if}
          {/each}
          {#each renderedNodes as node (node.node_id)}
            <g class="graph-node" class:dimmed={highlighted.size > 0 && !highlighted.has(node.node_id)} class:selected={selectedIds.includes(node.node_id)} class:virtual={node.node_id.startsWith("starter:")} transform={`translate(${node.x ?? 0},${node.y ?? 0})`} role="button" tabindex="0" aria-label={`${node.label}, ${node.node_type} record, ${node.degree} connections`} onpointerenter={() => hoveredId = node.node_id} onpointerleave={() => hoveredId = null} onpointerdown={(event) => dragStart(event, node)} onpointermove={(event) => dragMove(event, node)} onpointerup={(event) => dragEnd(event, node)} onclick={(event) => selectNode(event, node)} ondblclick={(event) => { event.stopPropagation(); centreNode(node); }} oncontextmenu={(event) => { event.preventDefault(); event.stopPropagation(); contextMenu = { x: event.clientX, y: event.clientY, node }; }} onkeydown={(event) => { if (event.key === "Enter") selectNode(event as unknown as MouseEvent, node); }}>
              <circle class="halo" r={radius(node) + 7} fill={node.color} />
              <!-- A cited source whose file is gone is drawn hollow with a dashed
                   outline, the way an unresolved link renders in a vault: the work
                   was grounded in something, and that something has been deleted.
                   Hiding it would make the conversation look ungrounded instead. -->
              <circle class="node-circle" class:unresolved={node.status === "missing"} r={radius(node)} fill={node.status === "missing" ? "transparent" : node.color} stroke={node.status === "failed" ? "#ef4444" : node.node_type === "approval" ? "#facc15" : node.color} />
              {#if showLabels && (transform.k >= labelThreshold || node.degree >= 4 || selectedIds.includes(node.node_id) || hoveredId === node.node_id)}<text class="node-label" y={radius(node) + 15} text-anchor="middle">{node.label}</text>{/if}
            </g>
          {/each}
        </g>
      </svg>

      {#if showingStarter}
        <div class="empty-copy"><strong>Build your knowledge graph</strong><span>Add sources, complete conversations, approve memories, or create tasks. Relationships will appear automatically.</span></div>
      {/if}

      <button class="summary-pill" aria-expanded={summaryOpen} onclick={(event) => { event.stopPropagation(); summaryOpen = !summaryOpen; }}>{#if showingStarter}<span>Starter view</span><i></i><span>nothing recorded yet</span>{:else}<span>{renderedNodes.length} node{renderedNodes.length === 1 ? "" : "s"}</span><i></i><span>{renderedLinks.length} relationship{renderedLinks.length === 1 ? "" : "s"}</span>{/if}<span aria-hidden="true">{summaryOpen ? "⌃" : "⌄"}</span></button>
      {#if summaryOpen}<section class="summary-popover"><h3>Workspace summary</h3>{#each summary as item}<p><span>{item[0]}</span><b>{item[1]}</b></p>{/each}<small><Icon name="shield" size="sm" /> Governed workspace boundary</small></section>{/if}

      <div class="viewport-controls"><button aria-label="Fit graph" onclick={fitGraph}>Fit</button><button aria-label="Zoom out" onclick={() => transform = { ...transform, k: Math.max(.35, transform.k - .15) }}>−</button><span>{Math.round(transform.k * 100)}%</span><button aria-label="Zoom in" onclick={() => transform = { ...transform, k: Math.min(3, transform.k + .15) }}>+</button></div>
      <div class="graph-meta"><span class="live-dot"></span>{updatedAt ? "Live workspace graph" : "Loading"}<button onclick={(event) => { event.stopPropagation(); void load(); }} disabled={refreshing}>{refreshing ? "Updating…" : "Refresh"}</button></div>

      {#if settingsOpen}
        <aside class="settings-panel" aria-label="Graph settings">
          <div class="panel-title"><div><span>Graph settings</span><small>Personal workspace view</small></div><button aria-label="Close graph settings" onclick={() => settingsOpen = false}>×</button></div>
          <details open><summary>Filters</summary>{#each FILTER_TYPES as type}<label class="check-row"><input type="checkbox" checked={enabledTypes[type]} onchange={(event) => enabledTypes = { ...enabledTypes, [type]: event.currentTarget.checked }} /><span>{FILTER_LABELS[type] ?? type.charAt(0).toUpperCase() + type.slice(1) + "s"}</span></label>{/each}<label class="check-row"><input type="checkbox" bind:checked={showOrphans} /><span>Orphan records</span></label></details>
          <details open><summary>Groups</summary>{#each groups as group}<div class="group-row"><i style={`background:${group.color}`}></i><span><b>{group.name}</b><small>{group.query}</small></span></div>{/each}<button class="text-action" onclick={() => newGroupOpen = !newGroupOpen}>+ New group</button>{#if newGroupOpen}<div class="group-form"><input bind:value={groupName} placeholder="Group name" /><input bind:value={groupQuery} placeholder='type:memory status:approved' /><label>Colour <input type="color" bind:value={groupColor} /></label><button onclick={addGroup}>Add group</button></div>{/if}</details>
          <details open><summary>Display</summary><label class="check-row"><input type="checkbox" bind:checked={showArrows} /><span>Direction arrows</span></label><label class="check-row"><input type="checkbox" bind:checked={showLabels} /><span>Node labels</span></label><label class="check-row"><input type="checkbox" bind:checked={showParticles} /><span>Relationship particles</span></label><label class="range-row"><span>Text fade threshold</span><input type="range" min="0.35" max="1.5" step="0.05" bind:value={labelThreshold} /></label><label class="range-row"><span>Node size</span><input type="range" min="0.7" max="1.7" step="0.1" bind:value={nodeScale} /></label><label class="range-row"><span>Link thickness</span><input type="range" min="0.5" max="2.5" step="0.1" bind:value={linkThickness} /></label></details>
          <details open><summary>Forces</summary><label class="range-row"><span>Centre force</span><input type="range" min="0" max="0.3" step="0.01" bind:value={centerStrength} /></label><label class="range-row"><span>Repel force</span><input type="range" min="-500" max="-40" step="10" bind:value={chargeStrength} /></label><label class="range-row"><span>Link force</span><input type="range" min="0" max="1" step="0.05" bind:value={linkStrength} /></label><label class="range-row"><span>Link distance</span><input type="range" min="30" max="220" step="5" bind:value={linkDistance} /></label><label class="range-row"><span>Collision radius</span><input type="range" min="0" max="30" step="1" bind:value={collisionPadding} /></label></details>
          <details open><summary>Motion</summary><div class="motion-options">{#each [["paused", "Paused"], ["activity", "Activity only"], ["alive", "Always alive"]] as option}<label><input type="radio" name="motion" value={option[0]} bind:group={motion} /><span>{option[1]}</span></label>{/each}</div></details>
        </aside>
      {/if}

      {#if inspectorOpen}
        <aside class="inspector" aria-label="Record inspector">
          <button class="close" aria-label="Close inspector" onclick={() => inspectorOpen = false}>×</button>
          {#if selected}<span class="record-kicker"><i style={`background:${selected.color}`}></i>{selected.node_type} record</span><h3>{selected.label}</h3><div class="status-line"><span>{statusLabel(selected.status)}</span><span>{selected.degree} connection{selected.degree === 1 ? "" : "s"}</span></div><p>{selected.detail ?? "No additional stored metadata is available."}</p><h4>Relationships</h4>{#if selectedConnections.length}{#each selectedConnections as edge}<div class="relationship-row"><button class="relationship" onclick={() => { const other = nodeId(edge.source) === selected.node_id ? nodeId(edge.target) : nodeId(edge.source); selectedIds = [other]; }}><span>{edge.relationship.replaceAll("_", " ")}</span><b>{renderedNodes.find((node) => node.node_id === (nodeId(edge.source) === selected.node_id ? nodeId(edge.target) : nodeId(edge.source)))?.label}</b></button>{#if edge.evidence_memory_id}<small>Evidence: {edge.evidence_memory_id}</small>{/if}{#if edge.owner_can_reject}<button class="reject-link" onclick={() => void rejectRelationship(edge)}>Reject link</button>{/if}</div>{/each}{:else}<p class="muted">No stored relationships yet.</p>{/if}<div class="inspector-actions"><button onclick={() => centreNode(selected)}>View neighbours</button>{#if selected.pinned}<button onclick={() => unpin(selected)}>Unpin position</button>{/if}</div>{:else}<p>Select a node to inspect it.</p>{/if}
        </aside>
      {/if}

      {#if graphMode === "local"}
        <!-- The way out of local mode, offered where local mode is visible. -->
        <div class="depth-control"><span>Relationship depth</span><input type="range" min="1" max="3" step="1" bind:value={depth} aria-label="Relationship depth" /><b>{depth}</b><button type="button" class="text-action" onclick={() => { graphMode = "global"; centreId = null; }}>Show all</button></div>
      {/if}
    </div>
  </section>

  <!-- The picker names its own boundary before it lists anything. It opens on
       the places Raiker holds an owner's work plus the folders they granted —
       it never lists the workspace root, which is what made it offer Raiker's
       whole installation as something to index. -->
  {#if sourceOpen}<dialog use:modal class="source-modal" aria-labelledby="source-title" oncancel={closeSourceDialog} onclick={(event) => { if (event.target === event.currentTarget) closeSourceDialog(); }}><button class="close" aria-label="Close add source" onclick={() => closeSourceDialog()}>×</button><span class="eyebrow">Knowledge boundary</span><h2 id="source-title">Add a source</h2><p>Nothing else on this computer is visible here. Review what would be indexed, then confirm — sources never become approved memory automatically.</p>
    {#if sourceBrowse}
      <nav class="source-browser" aria-label="Knowledge source browser">
        {#if sourceBrowse.parent !== null || sourceBrowse.path}<button onclick={() => void browseSource(sourceBrowse!.parent ?? "")}>← {sourceBrowse.parent ? "Up one folder" : "All places"}</button>{/if}
        {#if !sourceBrowse.path}
          {#each sourceBrowse.roots as root (root.root_id)}
            <button class="scope-root" class:disabled={!root.browsable} disabled={!root.browsable} onclick={() => { if (root.browsable) void browseSource(root.root_id); }}>
              <span>{root.kind === "granted" ? "Granted folder" : root.kind === "database" ? "Already indexed" : "Raiker data"}</span>
              <b>{root.label}</b>
              <small>{root.detail}</small>
            </button>
            {#if root.kind === "granted"}<button class="revoke" onclick={() => void revokeFolder(root.root_id)} disabled={sourceBusy}>Revoke access to {root.label}</button>{/if}
          {/each}
        {:else}
          {#each sourceBrowse.children as item (item.path)}<button class:selected={sourcePath === item.path} onclick={() => { if (item.kind === "folder") void browseSource(item.path); else { sourcePath = item.path; sourceReview = null; } }}><span>{item.kind === "folder" ? "Folder" : "File"}</span><b>{item.name}</b></button>{/each}
          {#if sourceBrowse.children.length === 0}<small>This folder is empty.</small>{/if}
          {#if sourceBrowse.truncated}<small>Showing the first 200 entries. Open a folder to continue.</small>{/if}
        {/if}
      </nav>
    {/if}
    {#if sourcePath}<form onsubmit={(event) => { event.preventDefault(); void reviewSource(); }}><label>Selected source<input bind:value={sourcePath} aria-label="Selected source" oninput={() => sourceReview = null} /></label><button class="primary" disabled={sourceBusy || !sourcePath.trim()}>{sourceBusy ? "Reviewing…" : "Review indexing plan"}</button></form>{/if}
    {#if sourceError}<p class="error" role="alert">{sourceError}</p>{/if}
    {#if sourceReview}<section class="source-review" aria-label="Source indexing review"><h3>Indexing plan</h3><p><b>{sourceReview.supported_files}</b> supported files · <b>{sourceReview.total_bytes.toLocaleString()}</b> bytes · <b>{sourceReview.unsupported_files}</b> skipped</p>{#each sourceReview.warnings as warning}<p class="warning">{warning}</p>{/each}<button class="primary" disabled={sourceBusy} onclick={() => void addSource()}>Add reviewed source</button></section>{/if}

    <!-- Two ways to bring in something from the computer, and the difference
         between them is stated rather than implied: a grant is read in place,
         an upload is a copy and needs the owner to say so. -->
    <section class="from-computer" aria-labelledby="from-computer-h">
      <h3 id="from-computer-h">From this computer</h3>
      <form onsubmit={(event) => { event.preventDefault(); void grantFolder(); }}>
        <label>Grant a folder — Raiker reads it where it is and copies nothing<input bind:value={grantPath} placeholder="/home/you/Documents/research" aria-label="Folder to grant" /></label>
        <button disabled={sourceBusy || !grantPath.trim()}>{sourceBusy ? "Working…" : "Grant folder access"}</button>
      </form>
      <div class="upload">
        <label for="brain-upload">Or add a single file. This <b>copies</b> it into your Raiker workspace.</label>
        <input id="brain-upload" type="file" onchange={pickUpload} aria-label="File to copy into Raiker" />
        {#if uploadName}
          <label class="consent"><input type="checkbox" bind:checked={uploadConsent} /> Store a copy of <b>{uploadName}</b> in Raiker. Without this, the file is not stored.</label>
          <button class="primary" disabled={sourceBusy || !uploadConsent} onclick={() => void uploadCopy()}>{sourceBusy ? "Storing…" : "Store the copy and add it"}</button>
        {/if}
      </div>
    </section>
    {#if sourceRoots.length}<h3>Current sources</h3>{#each sourceRoots as source}<div class="current-source"><span>{source.detail}</span><button aria-label={`Remove ${source.detail} from graph`} onclick={() => void removeSource(source.detail ?? "")}>Remove</button></div>{/each}{/if}</dialog>{/if}

  {#if contextMenu}<div class="context-menu" style={`left:${contextMenu.x}px;top:${contextMenu.y}px`} role="menu"><button onclick={() => centreNode(contextMenu!.node)}>Open local graph</button><button onclick={() => { selectedIds = [contextMenu!.node.node_id]; inspectorOpen = true; contextMenu = null; }}>Trace provenance</button><button onclick={() => contextMenu!.node.pinned ? unpin(contextMenu!.node) : (contextMenu!.node.fx = contextMenu!.node.x, contextMenu!.node.fy = contextMenu!.node.y, contextMenu!.node.pinned = true, contextMenu = null)}>{contextMenu.node.pinned ? "Unpin" : "Pin"}</button><button onclick={() => centreNode(contextMenu!.node)}>View neighbours</button></div>{/if}
{/if}

<style>
  :global(.content:has(.knowledge-shell)) { padding:0 !important; overflow:hidden; }

  /* The graph keeps the Obsidian interaction model, drawn in Raiker's own
     surface language.

     It used to carry four palettes: a hard-coded dark one, a hard-coded light
     one that overrode it, and a tokenised dark override written out twice —
     once keyed on `[data-theme="dark"]` and once, verbatim, inside a
     `prefers-color-scheme` query for the viewer who never chose a theme. The
     comment on that duplicate named the symptom exactly ("the Knowledge Map
     stayed light inside an otherwise dark app") without naming the cause: the
     base rules were painted in literals, so every theme had to be patched back
     on top of them. Painted in tokens, the base is already right in both
     themes, and all three override blocks are gone. */
  .knowledge-shell { height:calc(100vh - 58px); min-height:650px; display:grid; grid-template-rows:64px 1fr; background:var(--bg); color:var(--text-1); }
  .graph-toolbar { display:flex; gap:10px; align-items:center; padding:0 18px; border-bottom:1px solid var(--border); background:color-mix(in srgb, var(--surface) 96%, transparent); box-shadow:var(--shadow-1); z-index:20; }
  .title-block { min-width:190px; margin-right:auto; } .title-block h2 { overflow-wrap:anywhere; } .title-block h2 { margin:1px 0 0; color:var(--text-1); font-size:var(--text-base); letter-spacing:-.01em; } /* Shared `.eyebrow` sets the type; muted here because the graph toolbar
     already carries the accent. */ .eyebrow { color:var(--text-2); }
  .search { flex:0 1 min(380px, 42vw); display:flex; align-items:center; gap:8px; height:36px; padding:0 11px; border:1px solid var(--border-strong); border-radius:7px; background:var(--surface); color:var(--text-2); } .search:focus-within { border-color:var(--accent); box-shadow:0 0 0 2px var(--accent-soft); } .search input { width:100%; border:0; outline:0; background:transparent; color:var(--text-1); font:inherit; font-size:var(--text-sm); }
  .icon-button { border:0; color:var(--text-2); background:transparent; cursor:pointer; }
  .icon-button { display:grid; place-items:center; width:34px; height:34px; border:1px solid var(--border-strong); border-radius:7px; font-size:var(--text-xl); } .icon-button:hover { color:var(--accent-strong); border-color:var(--accent-border); background:var(--accent-soft); }
  .graph-workspace { position:relative; min-height:0; overflow:hidden; touch-action:none; cursor:grab; background:radial-gradient(circle at 50% 45%, var(--raised) 0%, var(--surface) 45%, var(--bg) 100%); } .graph-workspace:active { cursor:grabbing; } .graph-workspace:fullscreen { width:100vw; height:100vh; }
  .vignette { position:absolute; inset:0; pointer-events:none; background:radial-gradient(ellipse at center, transparent 48%, color-mix(in srgb, var(--overlay) 25%, transparent) 100%); z-index:1; }
  .graph-stage { position:absolute; inset:0; z-index:2; overflow:visible; }
  line { stroke:color-mix(in srgb, var(--text-3) 55%, transparent); stroke-width:calc(var(--link-width) * 1px); transition:opacity .15s, stroke .15s; } line.highlighted { stroke:var(--accent); stroke-width:calc(var(--link-width) * 1.8px); } line.instruction { stroke-dasharray:3 7; stroke:color-mix(in srgb, var(--text-3) 70%, transparent); }
  .particle { filter:drop-shadow(0 0 3px currentColor); opacity:.8; }
  .graph-node { cursor:pointer; outline:none; transition:opacity .15s; } .graph-node.dimmed { opacity:.12; } .node-circle { stroke-width:1.2px; filter:drop-shadow(0 0 3px color-mix(in srgb, var(--text-1) 14%, transparent)); transition:r .15s, filter .15s, stroke-width .15s; } .halo { opacity:.06; transition:opacity .15s; } .graph-node:hover .halo,.graph-node.selected .halo { opacity:.24; } .graph-node:hover .node-circle,.graph-node.selected .node-circle { stroke:var(--accent-strong); stroke-width:2px; filter:drop-shadow(0 0 8px color-mix(in srgb, var(--accent) 72%, transparent)); } .graph-node.virtual .node-circle { opacity:.8; } .node-circle.unresolved { stroke-dasharray:2.5 2.5; stroke-width:1.6px; }
  .node-label { fill:var(--text-1); paint-order:stroke; stroke:var(--surface); stroke-width:3px; stroke-linejoin:round; font-size:11px; font-family:var(--font-sans); pointer-events:none; }
  .empty-copy { position:absolute; z-index:4; left:50%; top:20px; transform:translateX(-50%); display:grid; gap:4px; width:min(520px, 80%); text-align:center; pointer-events:none; } .empty-copy strong { font-size:var(--text-md); } .empty-copy span { color:var(--text-2); font-size:var(--text-xs); line-height:1.45; }
  .summary-pill,.viewport-controls,.graph-meta,.depth-control { position:absolute; z-index:5; display:flex; align-items:center; border:1px solid var(--border-strong); background:color-mix(in srgb, var(--surface) 94%, transparent); backdrop-filter:blur(14px); color:var(--text-2); box-shadow:var(--shadow-2); }
  .summary-pill { left:16px; top:16px; gap:8px; border-radius:20px; padding:7px 11px; font:inherit; font-size:var(--text-2xs); cursor:pointer; } .summary-pill i { width:3px; height:3px; border-radius:50%; background:var(--text-3); }
  .summary-popover { position:absolute; z-index:8; left:16px; top:56px; width:230px; padding:14px; border:1px solid var(--border-strong); border-radius:10px; background:color-mix(in srgb, var(--raised) 96%, transparent); box-shadow:var(--shadow-2); } .summary-popover h3 { margin:0 0 10px; font-size:var(--text-sm); } .summary-popover p { display:flex; justify-content:space-between; margin:6px 0; color:var(--text-2); font-size:var(--text-xs); } .summary-popover p b { color:var(--text-1); } .summary-popover small { display:flex; gap:5px; align-items:center; margin-top:12px; padding-top:10px; border-top:1px solid var(--border); color:var(--accent); font-size:var(--text-2xs); }
  .viewport-controls { right:16px; bottom:16px; border-radius:8px; overflow:hidden; } .viewport-controls button { height:32px; min-width:34px; border:0; border-right:1px solid var(--border); background:transparent; color:var(--text-2); cursor:pointer; } .viewport-controls button:first-child { padding:0 11px; font-size:var(--text-2xs); } .viewport-controls span { min-width:46px; text-align:center; font-size:var(--text-2xs); }
  .graph-meta { left:16px; bottom:16px; gap:7px; padding:7px 10px; border-radius:7px; font-size:var(--text-2xs); } .graph-meta button { border:0; background:transparent; color:var(--accent); font:inherit; cursor:pointer; } .live-dot { width:6px; height:6px; border-radius:50%; background:var(--success); box-shadow:0 0 7px var(--success); }
  .depth-control { left:50%; bottom:16px; transform:translateX(-50%); gap:10px; padding:8px 12px; border-radius:8px; font-size:var(--text-2xs); } .depth-control input { width:130px; accent-color:var(--accent); }
  /* Below this the bottom-left status and the bottom-right zoom controls are
     wider together than the window, so they overlapped and each hid half of the
     other. Stacked rather than shrunk: both are already at their smallest. */
  @media (max-width: 34rem) {
    /* The page header already says "Knowledge Map"; the eyebrow above it wrapped
       to two lines here and said the same thing a second time. */
    .eyebrow { display:none; }
    .title-block { min-width:0; }
    .graph-meta { bottom:60px; }
    .depth-control { left:16px; right:16px; bottom:104px; transform:none; justify-content:space-between; }
    .depth-control input { width:auto; flex:1; }
  }
  .settings-panel,.inspector { position:absolute; z-index:10; top:14px; right:14px; bottom:58px; width:300px; overflow:auto; border:1px solid var(--border-strong); border-radius:11px; background:color-mix(in srgb, var(--surface) 96%, transparent); backdrop-filter:blur(18px); box-shadow:var(--shadow-2); cursor:default; }
  /* VIS-06 — "Graph settings" is the heading of the panel it sits on, not a
     status marker. At 2xs in caps with .1em tracking it was the smallest and
     hardest-to-read text in a panel it is supposed to title. */
  .panel-title { position:sticky; top:0; z-index:2; display:flex; justify-content:space-between; align-items:center; padding:15px 16px 12px; border-bottom:1px solid var(--border); background:var(--raised); font-size:var(--text-sm); font-weight:650; } .panel-title small { display:block; margin-top:4px; color:var(--text-3); text-transform:none; letter-spacing:0; } .panel-title button,.close { border:0; background:transparent; color:var(--text-2); cursor:pointer; font-size:var(--text-xl); }
  details { border-bottom:1px solid var(--border); padding:12px 16px; } summary { color:var(--text-1); cursor:pointer; font-size:var(--text-xs); font-weight:650; letter-spacing:.04em; } details > :not(summary) { margin-top:10px; }
  .group-form input { min-width:0; width:100%; border:0; outline:0; background:transparent; color:var(--text-1); font:inherit; font-size:var(--text-2xs); }
  .check-row,.range-row { display:flex; align-items:center; justify-content:space-between; gap:10px; color:var(--text-2); font-size:var(--text-2xs); margin:8px 0 0 !important; } .check-row { justify-content:flex-start; } input[type="checkbox"],input[type="radio"] { accent-color:var(--accent); } .range-row input { width:120px; accent-color:var(--accent); }
  .group-row { display:flex; align-items:center; gap:8px; } .group-row i,.record-kicker i { width:8px; height:8px; flex:none; border-radius:50%; box-shadow:0 0 5px currentColor; } .group-row span { display:grid; } .group-row b { color:var(--text-1); font-size:var(--text-2xs); } .group-row small { color:var(--text-3); font-size:var(--text-2xs); } .text-action { border:0; padding:0; background:transparent; color:var(--accent); font:inherit; font-size:var(--text-2xs); cursor:pointer; }
  .group-form { display:grid; gap:7px; padding:9px; border:1px solid var(--border); border-radius:6px; background:var(--sunken); } .group-form input { padding:6px; border:1px solid var(--border); border-radius:4px; } .group-form label { display:flex; justify-content:space-between; align-items:center; color:var(--text-2); font-size:var(--text-2xs); } .group-form label input { width:38px; padding:0; } .group-form button { border:0; border-radius:4px; padding:6px; background:var(--accent); color:var(--text-inverse); cursor:pointer; }
  .motion-options { display:grid; grid-template-columns:repeat(3, 1fr); gap:4px; } .motion-options label { display:flex; align-items:center; gap:3px; color:var(--text-2); font-size:var(--text-2xs); }
  .inspector { padding:18px; width:280px; bottom:14px; } .inspector .close,.source-modal .close { position:absolute; right:12px; top:9px; } .record-kicker { display:flex; align-items:center; gap:7px; color:var(--text-3); text-transform:uppercase; letter-spacing:.05em; font-size:var(--text-2xs); } .inspector h3 { margin:10px 24px 4px 0; font-size:var(--text-base); } .status-line { display:flex; gap:8px; color:var(--text-3); font-size:var(--text-2xs); } .status-line span { padding:3px 6px; border:1px solid var(--border); border-radius:4px; } .inspector > p { color:var(--text-2); font-size:var(--text-xs); line-height:1.55; } /* VIS-06 — a section heading inside the inspector. */ .inspector h4 { margin:20px 0 7px; color:var(--text-3); font-size:var(--text-xs); font-weight:650; }
  .relationship { display:grid; width:100%; gap:2px; padding:8px 0; border:0; border-bottom:1px solid var(--border); background:transparent; text-align:left; cursor:pointer; } .relationship span { color:var(--text-3); font-size:var(--text-2xs); } .relationship b { color:var(--text-1); font-size:var(--text-xs); } .inspector-actions { display:grid; gap:7px; margin-top:18px; } .inspector-actions button { border:1px solid var(--border); border-radius:6px; padding:7px; background:var(--sunken); color:var(--text-2); cursor:pointer; }
  .relationship-row { display:grid; grid-template-columns:1fr auto; align-items:center; border-bottom:1px solid var(--border); } .relationship-row .relationship { border:0; } .relationship-row small { grid-column:1/-1; color:var(--text-3); font-size:var(--text-2xs); overflow-wrap:anywhere; } .reject-link { border:0; background:transparent; color:var(--danger); font-size:var(--text-2xs); cursor:pointer; }
  .source-modal::backdrop { background:var(--overlay); backdrop-filter:blur(5px); } .source-modal { position:relative; width:min(480px, calc(100vw - 32px)); max-height:80vh; overflow:auto; padding:24px; border:1px solid var(--border-strong); border-radius:13px; background:var(--raised); color:var(--text-1); box-shadow:var(--shadow-2); } .source-modal h2 { margin:6px 0; font-size:var(--text-xl); } .source-modal > p { color:var(--text-2); font-size:var(--text-xs); line-height:1.5; } .source-modal form label { display:grid; gap:6px; color:var(--text-2); font-size:var(--text-2xs); } .source-modal form input { border:1px solid var(--border); border-radius:6px; padding:10px; background:var(--sunken); color:var(--text-1); } .primary { width:100%; margin-top:12px; border:0; border-radius:6px; padding:9px; background:var(--accent); color:var(--text-inverse); cursor:pointer; } .error { color:var(--danger) !important; } .current-source { display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px solid var(--border); color:var(--text-2); font-size:var(--text-2xs); } .current-source button { border:0; background:transparent; color:var(--danger); cursor:pointer; }
  /* A root reads as a place, not a row: the label answers "where is this?" and
     the detail answers "what is in it?" before anything is opened. */
  .source-browser button.scope-root { display:grid; gap:2px; padding:9px; } .source-browser button.scope-root b { font-size:var(--text-xs); } .source-browser button.scope-root small { padding:0; color:var(--text-3); font-size:var(--text-2xs); line-height:1.45; } .source-browser button.scope-root span { width:auto; }
  .source-browser button.disabled { cursor:default; opacity:.72; }
  .source-browser button.revoke { justify-content:flex-end; padding:5px 9px 9px; color:var(--danger); font-size:var(--text-2xs); }
  .from-computer { margin-top:16px; padding-top:14px; border-top:1px solid var(--border); } .from-computer h3 { margin:0 0 8px; font-size:var(--text-sm); } .from-computer form button { width:100%; margin-top:8px; border:1px solid var(--border); border-radius:6px; padding:8px; background:transparent; color:var(--text-2); cursor:pointer; } .upload { margin-top:14px; display:grid; gap:8px; color:var(--text-2); font-size:var(--text-2xs); } .upload input[type="file"] { color:var(--text-2); font-size:var(--text-2xs); } .consent { display:flex !important; align-items:flex-start; gap:8px; line-height:1.45; }
  .source-browser { display:grid; max-height:280px; overflow:auto; margin:0 0 12px; border:1px solid var(--border); border-radius:7px; } .source-browser button { display:flex; gap:8px; border:0; border-bottom:1px solid var(--border); padding:7px 9px; background:transparent; color:var(--text-2); text-align:left; cursor:pointer; } .source-browser button:hover,.source-browser button.selected { background:var(--accent-soft); } .source-browser button span { width:42px; color:var(--text-3); font-size:var(--text-2xs); } .source-browser button b { font-size:var(--text-2xs); } .source-browser small { padding:8px; color:var(--text-3); } .source-review { margin-top:12px; padding:12px; border:1px solid var(--border); border-radius:7px; background:var(--sunken); } .source-review h3 { margin:0 0 6px; } .source-review p { font-size:var(--text-2xs); } .source-review .warning { color:var(--warn); }
  .context-menu { position:fixed; z-index:120; display:grid; min-width:160px; padding:5px; border:1px solid var(--border-strong); border-radius:7px; background:var(--raised); box-shadow:var(--shadow-2); } .context-menu button { border:0; border-radius:4px; padding:7px 9px; background:transparent; color:var(--text-1); text-align:left; cursor:pointer; font-size:var(--text-2xs); } .context-menu button:hover { background:var(--accent-soft); }
  @media (prefers-reduced-motion: reduce) { .particle { display:none; } }
  @media (max-width:800px) { .graph-toolbar { flex-wrap:wrap; } .search { flex:1 0 100%; order:2; margin-bottom:8px; } .knowledge-shell { grid-template-rows:auto 1fr; } .title-block { min-width:0; } .settings-panel,.inspector { width:min(300px, calc(100% - 28px)); } }
</style>
