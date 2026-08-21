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
    user: "#f3f5fa", workspace: "#77d5ee", project: "#a78bfa", source: "#60a5fa",
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
    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(([entry]) => {
      graphWidth = Math.max(320, entry.contentRect.width);
      graphHeight = Math.max(420, entry.contentRect.height);
      simulation?.force("center", forceCenter(graphWidth / 2, graphHeight / 2).strength(centerStrength)).alpha(0.2).restart();
    });
    if (graphElement) resize?.observe(graphElement);
    return () => { window.clearInterval(timer); resize?.disconnect(); simulation?.stop(); };
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
      .on("tick", () => { nodes.forEach((node) => positionCache.set(node.node_id, node)); renderedNodes = [...nodes]; renderedLinks = [...links]; });
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
  function fitGraph() { transform = { x: 0, y: 0, k: 1 }; simulation?.alpha(0.18).restart(); }
  async function toggleFullscreen() { if (!document.fullscreenElement) await graphElement?.requestFullscreen(); else await document.exitFullscreen(); }

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
      <label class="search"><Icon name="search" size={16} /><input bind:value={search} placeholder="Search records or use type:, status:…" aria-label="Search records" /></label>
      <div class="mode-switch" role="group" aria-label="Graph scope"><button class:active={graphMode === "global"} onclick={() => graphMode = "global"}>Global</button><button class:active={graphMode === "local"} disabled={!centreId} onclick={() => graphMode = "local"}>Local</button></div>
      <button class="icon-button" aria-label="Add workspace source" title="Add source" onclick={() => void openSourcePicker()}>+</button>
      <button class="icon-button" aria-label="Graph settings" aria-expanded={settingsOpen} onclick={() => settingsOpen = !settingsOpen}><Icon name="settings" size={17} /></button>
      <button class="icon-button" aria-label="Enter fullscreen" onclick={toggleFullscreen}>⛶</button>
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
      {#if summaryOpen}<section class="summary-popover"><h3>Workspace summary</h3>{#each summary as item}<p><span>{item[0]}</span><b>{item[1]}</b></p>{/each}<small><Icon name="shield" size={13} /> Governed workspace boundary</small></section>{/if}

      <div class="viewport-controls"><button aria-label="Fit graph" onclick={fitGraph}>Fit</button><button aria-label="Zoom out" onclick={() => transform = { ...transform, k: Math.max(.35, transform.k - .15) }}>−</button><span>{Math.round(transform.k * 100)}%</span><button aria-label="Zoom in" onclick={() => transform = { ...transform, k: Math.min(3, transform.k + .15) }}>+</button></div>
      <div class="graph-meta"><span class="live-dot"></span>{updatedAt ? "Live workspace graph" : "Loading"}<button onclick={(event) => { event.stopPropagation(); void load(); }} disabled={refreshing}>{refreshing ? "Updating…" : "Refresh"}</button></div>

      {#if settingsOpen}
        <aside class="settings-panel" aria-label="Graph settings">
          <div class="panel-title"><div><span>Graph settings</span><small>Personal workspace view</small></div><button aria-label="Close graph settings" onclick={() => settingsOpen = false}>×</button></div>
          <details open><summary>Filters</summary><label class="panel-search"><Icon name="search" size={14} /><input bind:value={search} placeholder="Search records…" /></label>{#each FILTER_TYPES as type}<label class="check-row"><input type="checkbox" checked={enabledTypes[type]} onchange={(event) => enabledTypes = { ...enabledTypes, [type]: event.currentTarget.checked }} /><span>{FILTER_LABELS[type] ?? type.charAt(0).toUpperCase() + type.slice(1) + "s"}</span></label>{/each}<label class="check-row"><input type="checkbox" bind:checked={showOrphans} /><span>Orphan records</span></label></details>
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
        <div class="depth-control"><span>Relationship depth</span><input type="range" min="1" max="3" step="1" bind:value={depth} aria-label="Relationship depth" /><b>{depth}</b></div>
      {/if}
    </div>
  </section>

  <!-- The picker names its own boundary before it lists anything. It opens on
       the places Raiker holds an owner's work plus the folders they granted —
       it never lists the workspace root, which is what made it offer Raiker's
       whole installation as something to index. -->
  {#if sourceOpen}<dialog use:modal class="source-modal" aria-labelledby="source-title" oncancel={closeSourceDialog} onclick={(event) => { if (event.target === event.currentTarget) closeSourceDialog(); }}><button class="close" aria-label="Close add source" onclick={() => closeSourceDialog()}>×</button><span class="eyebrow">Knowledge boundary</span><h2 id="source-title">Add a source</h2><p>Raiker can read the places it keeps your work, and any folder you grant it. Nothing else on this computer is visible here. Review what would be indexed, then confirm — sources never become approved memory automatically.</p>
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
  .knowledge-shell { height:calc(100vh - 58px); min-height:650px; display:grid; grid-template-rows:64px 1fr; background:#17181c; color:#eef0f6; }
  .graph-toolbar { display:grid; grid-template-columns:auto minmax(220px, 620px) auto auto auto auto; gap:10px; align-items:center; padding:0 18px; border-bottom:1px solid rgba(180,188,205,.12); background:rgba(23,24,28,.96); z-index:20; }
  .title-block { min-width:190px; } .title-block h2 { margin:1px 0 0; color:#eef0f6; font-size:1.06rem; letter-spacing:-.01em; } .eyebrow { color:#9da7bd; font-size:.7rem; letter-spacing:.13em; text-transform:uppercase; }
  .search { display:flex; align-items:center; gap:8px; height:36px; padding:0 11px; border:1px solid rgba(180,188,205,.15); border-radius:7px; background:rgba(255,255,255,.045); color:#8f98ad; } .search:focus-within { border-color:#708db8; box-shadow:0 0 0 2px rgba(112,141,184,.15); } .search input { width:100%; border:0; outline:0; background:transparent; color:#eef0f6; font:inherit; font-size:.78rem; }
  .mode-switch { display:flex; padding:3px; border:1px solid rgba(180,188,205,.14); border-radius:7px; background:#111216; } .mode-switch button,.icon-button { border:0; color:#9ba4b8; background:transparent; cursor:pointer; } .mode-switch button { padding:6px 10px; border-radius:5px; font:inherit; font-size:.72rem; } .mode-switch button.active { background:#30333b; color:#f3f5fa; box-shadow:0 1px 3px #0008; } .mode-switch button:disabled { opacity:.38; cursor:not-allowed; }
  .icon-button { display:grid; place-items:center; width:34px; height:34px; border:1px solid rgba(180,188,205,.13); border-radius:7px; font-size:1.25rem; } .icon-button:hover { color:white; border-color:rgba(180,188,205,.3); background:rgba(255,255,255,.05); }
  .graph-workspace { position:relative; min-height:0; overflow:hidden; touch-action:none; cursor:grab; background:radial-gradient(circle at 50% 45%, #242834 0%, #1a1c22 38%, #141519 100%); } .graph-workspace:active { cursor:grabbing; } .graph-workspace:fullscreen { width:100vw; height:100vh; }
  .vignette { position:absolute; inset:0; pointer-events:none; background:radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,.33) 100%); z-index:1; }
  .graph-stage { position:absolute; inset:0; z-index:2; overflow:visible; }
  line { stroke:rgba(180,188,205,.22); stroke-width:calc(var(--link-width) * 1px); transition:opacity .15s, stroke .15s; } line.highlighted { stroke:rgba(137,180,250,.9); stroke-width:calc(var(--link-width) * 1.8px); } line.instruction { stroke-dasharray:3 7; stroke:rgba(180,188,205,.36); }
  .particle { filter:drop-shadow(0 0 3px currentColor); opacity:.8; }
  .graph-node { cursor:pointer; outline:none; transition:opacity .15s; } .graph-node.dimmed { opacity:.12; } .node-circle { stroke-width:1.2px; filter:drop-shadow(0 0 3px rgba(255,255,255,.12)); transition:r .15s, filter .15s, stroke-width .15s; } .halo { opacity:.06; transition:opacity .15s; } .graph-node:hover .halo,.graph-node.selected .halo { opacity:.24; } .graph-node:hover .node-circle,.graph-node.selected .node-circle { stroke:#dbeafe; stroke-width:2px; filter:drop-shadow(0 0 8px rgba(137,180,250,.72)); } .graph-node.virtual .node-circle { opacity:.8; } .node-circle.unresolved { stroke-dasharray:2.5 2.5; stroke-width:1.6px; }
  .node-label { fill:rgba(238,240,246,.88); paint-order:stroke; stroke:#17181c; stroke-width:3px; stroke-linejoin:round; font-size:11px; font-family:var(--font-sans); pointer-events:none; }
  .empty-copy { position:absolute; z-index:4; left:50%; top:20px; transform:translateX(-50%); display:grid; gap:4px; width:min(520px, 80%); text-align:center; pointer-events:none; } .empty-copy strong { font-size:.92rem; } .empty-copy span { color:rgba(210,215,228,.56); font-size:.75rem; line-height:1.45; }
  .summary-pill,.viewport-controls,.graph-meta,.depth-control { position:absolute; z-index:5; display:flex; align-items:center; border:1px solid rgba(180,188,205,.14); background:rgba(20,21,25,.82); backdrop-filter:blur(14px); color:#b9c0cf; box-shadow:0 8px 24px #0005; }
  .summary-pill { left:16px; top:16px; gap:8px; border-radius:20px; padding:7px 11px; font:inherit; font-size:.7rem; cursor:pointer; } .summary-pill i { width:3px; height:3px; border-radius:50%; background:#647089; }
  .summary-popover { position:absolute; z-index:8; left:16px; top:56px; width:230px; padding:14px; border:1px solid rgba(180,188,205,.15); border-radius:10px; background:rgba(25,27,33,.96); box-shadow:0 16px 35px #0007; } .summary-popover h3 { margin:0 0 10px; font-size:.78rem; } .summary-popover p { display:flex; justify-content:space-between; margin:6px 0; color:#9da6b9; font-size:.72rem; } .summary-popover p b { color:#f0f2f7; } .summary-popover small { display:flex; gap:5px; align-items:center; margin-top:12px; padding-top:10px; border-top:1px solid #ffffff12; color:#6da9b8; font-size:.65rem; }
  .viewport-controls { right:16px; bottom:16px; border-radius:8px; overflow:hidden; } .viewport-controls button { height:32px; min-width:34px; border:0; border-right:1px solid #ffffff12; background:transparent; color:#bac1cf; cursor:pointer; } .viewport-controls button:first-child { padding:0 11px; font-size:.68rem; } .viewport-controls span { min-width:46px; text-align:center; font-size:.65rem; }
  .graph-meta { left:16px; bottom:16px; gap:7px; padding:7px 10px; border-radius:7px; font-size:.65rem; } .graph-meta button { border:0; background:transparent; color:#8ab4f8; font:inherit; cursor:pointer; } .live-dot { width:6px; height:6px; border-radius:50%; background:#58d68d; box-shadow:0 0 7px #58d68d; }
  .depth-control { left:50%; bottom:16px; transform:translateX(-50%); gap:10px; padding:8px 12px; border-radius:8px; font-size:.68rem; } .depth-control input { width:130px; accent-color:#8ab4f8; }
  .settings-panel,.inspector { position:absolute; z-index:10; top:14px; right:14px; bottom:58px; width:300px; overflow:auto; border:1px solid rgba(180,188,205,.16); border-radius:11px; background:rgba(24,26,32,.96); backdrop-filter:blur(18px); box-shadow:0 18px 50px #0009; cursor:default; }
  .panel-title { position:sticky; top:0; z-index:2; display:flex; justify-content:space-between; align-items:center; padding:15px 16px 12px; border-bottom:1px solid #ffffff12; background:#191b20; text-transform:uppercase; letter-spacing:.1em; font-size:.68rem; } .panel-title small { display:block; margin-top:4px; color:#6f788b; text-transform:none; letter-spacing:0; } .panel-title button,.close { border:0; background:transparent; color:#8c95a7; cursor:pointer; font-size:1.3rem; }
  details { border-bottom:1px solid #ffffff10; padding:12px 16px; } summary { color:#d9dde7; cursor:pointer; font-size:.72rem; font-weight:650; letter-spacing:.04em; } details > :not(summary) { margin-top:10px; }
  .panel-search { display:flex; align-items:center; gap:7px; height:31px; padding:0 8px; border:1px solid #ffffff17; border-radius:6px; color:#778196; background:#121318; } .panel-search input,.group-form input { min-width:0; width:100%; border:0; outline:0; background:transparent; color:#e6e9f0; font:inherit; font-size:.7rem; }
  .check-row,.range-row { display:flex; align-items:center; justify-content:space-between; gap:10px; color:#aab2c2; font-size:.7rem; margin:8px 0 0 !important; } .check-row { justify-content:flex-start; } input[type="checkbox"],input[type="radio"] { accent-color:#8ab4f8; } .range-row input { width:120px; accent-color:#8ab4f8; }
  .group-row { display:flex; align-items:center; gap:8px; } .group-row i,.record-kicker i { width:8px; height:8px; flex:none; border-radius:50%; box-shadow:0 0 5px currentColor; } .group-row span { display:grid; } .group-row b { color:#bfc6d3; font-size:.69rem; } .group-row small { color:#687286; font-size:.6rem; } .text-action { border:0; padding:0; background:transparent; color:#8ab4f8; font:inherit; font-size:.68rem; cursor:pointer; }
  .group-form { display:grid; gap:7px; padding:9px; border:1px solid #ffffff12; border-radius:6px; background:#111216; } .group-form input { padding:6px; border:1px solid #ffffff12; border-radius:4px; } .group-form label { display:flex; justify-content:space-between; align-items:center; color:#8992a5; font-size:.65rem; } .group-form label input { width:38px; padding:0; } .group-form button { border:0; border-radius:4px; padding:6px; background:#527ebc; color:white; cursor:pointer; }
  .motion-options { display:grid; grid-template-columns:repeat(3, 1fr); gap:4px; } .motion-options label { display:flex; align-items:center; gap:3px; color:#939caf; font-size:.62rem; }
  .inspector { padding:18px; width:280px; bottom:14px; } .inspector .close,.source-modal .close { position:absolute; right:12px; top:9px; } .record-kicker { display:flex; align-items:center; gap:7px; color:#8892a5; text-transform:uppercase; letter-spacing:.11em; font-size:.6rem; } .inspector h3 { margin:10px 24px 4px 0; font-size:1.05rem; } .status-line { display:flex; gap:8px; color:#7f899e; font-size:.66rem; } .status-line span { padding:3px 6px; border:1px solid #ffffff12; border-radius:4px; } .inspector > p { color:#a5adbd; font-size:.73rem; line-height:1.55; } .inspector h4 { margin:20px 0 7px; color:#7f899e; text-transform:uppercase; letter-spacing:.1em; font-size:.62rem; }
  .relationship { display:grid; width:100%; gap:2px; padding:8px 0; border:0; border-bottom:1px solid #ffffff0e; background:transparent; text-align:left; cursor:pointer; } .relationship span { color:#687286; font-size:.6rem; } .relationship b { color:#cbd1dd; font-size:.72rem; } .inspector-actions { display:grid; gap:7px; margin-top:18px; } .inspector-actions button { border:1px solid #ffffff16; border-radius:6px; padding:7px; background:#ffffff08; color:#c2c9d6; cursor:pointer; }
  .relationship-row { display:grid; grid-template-columns:1fr auto; align-items:center; border-bottom:1px solid #ffffff0e; } .relationship-row .relationship { border:0; } .relationship-row small { grid-column:1/-1; color:#7d8799; font-size:.58rem; overflow-wrap:anywhere; } .reject-link { border:0; background:transparent; color:#d86f79; font-size:.62rem; cursor:pointer; }
  .source-modal::backdrop { background:#08090dbb; backdrop-filter:blur(5px); } .source-modal { position:relative; width:min(480px, calc(100vw - 32px)); max-height:80vh; overflow:auto; padding:24px; border:1px solid #ffffff1c; border-radius:13px; background:#1c1e24; color:#eef0f6; box-shadow:0 25px 80px #000c; } .source-modal h2 { margin:6px 0; font-size:1.15rem; } .source-modal > p { color:#9ba4b6; font-size:.75rem; line-height:1.5; } .source-modal form label { display:grid; gap:6px; color:#a9b0bf; font-size:.7rem; } .source-modal form input { border:1px solid #ffffff18; border-radius:6px; padding:10px; background:#111216; color:white; } .primary { width:100%; margin-top:12px; border:0; border-radius:6px; padding:9px; background:#5c87c5; color:white; cursor:pointer; } .error { color:#ff8c98 !important; } .current-source { display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px solid #ffffff0e; color:#aeb6c5; font-size:.7rem; } .current-source button { border:0; background:transparent; color:#ef7885; cursor:pointer; }
  /* A root reads as a place, not a row: the label answers "where is this?" and
     the detail answers "what is in it?" before anything is opened. */
  .source-browser button.scope-root { display:grid; gap:2px; padding:9px; } .source-browser button.scope-root b { font-size:.76rem; } .source-browser button.scope-root small { padding:0; color:#8892a5; font-size:.65rem; line-height:1.45; } .source-browser button.scope-root span { width:auto; }
  .source-browser button.disabled { cursor:default; opacity:.72; }
  .source-browser button.revoke { justify-content:flex-end; padding:5px 9px 9px; color:#ef7885; font-size:.65rem; }
  .from-computer { margin-top:16px; padding-top:14px; border-top:1px solid #ffffff14; } .from-computer h3 { margin:0 0 8px; font-size:.82rem; } .from-computer form button { width:100%; margin-top:8px; border:1px solid #ffffff1c; border-radius:6px; padding:8px; background:transparent; color:#cbd1dc; cursor:pointer; } .upload { margin-top:14px; display:grid; gap:8px; color:#a9b0bf; font-size:.7rem; } .upload input[type="file"] { color:#cbd1dc; font-size:.68rem; } .consent { display:flex !important; align-items:flex-start; gap:8px; line-height:1.45; }
  .source-browser { display:grid; max-height:280px; overflow:auto; margin:0 0 12px; border:1px solid #ffffff16; border-radius:7px; } .source-browser button { display:flex; gap:8px; border:0; border-bottom:1px solid #ffffff0d; padding:7px 9px; background:transparent; color:#cbd1dc; text-align:left; cursor:pointer; } .source-browser button:hover,.source-browser button.selected { background:#ffffff0c; } .source-browser button span { width:42px; color:#7f899e; font-size:.62rem; } .source-browser button b { font-size:.7rem; } .source-browser small { padding:8px; color:#7f899e; } .source-review { margin-top:12px; padding:12px; border:1px solid #ffffff16; border-radius:7px; background:#ffffff08; } .source-review h3 { margin:0 0 6px; } .source-review p { font-size:.7rem; } .source-review .warning { color:#d89b45; }
  .context-menu { position:fixed; z-index:120; display:grid; min-width:160px; padding:5px; border:1px solid #ffffff20; border-radius:7px; background:#202229; box-shadow:0 14px 35px #000b; } .context-menu button { border:0; border-radius:4px; padding:7px 9px; background:transparent; color:#cbd1dc; text-align:left; cursor:pointer; font-size:.7rem; } .context-menu button:hover { background:#ffffff0c; }

  /* The graph keeps the Obsidian interaction model while using Raiker's
     calm light control-deck palette and existing surface language. */
  .knowledge-shell { background:#f3f7f7; color:#183047; }
  .graph-toolbar { border-color:#d8e2e4; background:rgba(250,252,252,.97); box-shadow:0 1px 4px #38556b12; }
  .title-block h2 { color:#173047; } .eyebrow { color:#536a7b; }
  .search { border-color:#cedadd; background:#fff; color:#718697; } .search:focus-within { border-color:#79b8b5; box-shadow:0 0 0 2px #bce3e147; } .search input { color:#173047; }
  .mode-switch { border-color:#cfdbde; background:#edf3f3; } .mode-switch button,.icon-button { color:#5d7487; } .mode-switch button.active { background:#cce9e7; color:#0b716e; box-shadow:0 1px 3px #38556b20; }
  .icon-button { border-color:#cfdbde; background:#fff; } .icon-button:hover { color:#087b77; border-color:#8cc5c2; background:#e9f6f5; }
  .graph-workspace { background:radial-gradient(circle at 50% 42%, #fbfdfd 0%, #f1f6f6 48%, #e7eeee 100%); }
  .vignette { background:radial-gradient(ellipse at center, transparent 54%, rgba(75,105,119,.1) 100%); }
  line { stroke:rgba(76,100,116,.25); } line.highlighted { stroke:#118b87; } line.instruction { stroke:rgba(58,105,113,.42); }
  .node-circle { filter:drop-shadow(0 0 3px rgba(53,85,100,.16)); } .graph-node:hover .node-circle,.graph-node.selected .node-circle { stroke:#087b77; filter:drop-shadow(0 0 8px rgba(17,139,135,.42)); }
  .node-label { fill:#29465d; stroke:#f5f9f9; }
  .empty-copy span { color:#738797; }
  .summary-pill,.viewport-controls,.graph-meta,.depth-control { border-color:#cedbdd; background:rgba(255,255,255,.9); color:#536b7e; box-shadow:0 8px 24px #38556b1f; }
  .summary-popover { border-color:#cfdbde; background:rgba(255,255,255,.97); box-shadow:0 16px 35px #38556b2b; } .summary-popover p { color:#6e8292; } .summary-popover p b { color:#173047; } .summary-popover small { border-color:#dce6e8; color:#15827e; }
  .viewport-controls button { border-color:#dce5e7; color:#526b7e; } .graph-meta button { color:#087b77; } .live-dot { background:#24a97b; box-shadow:0 0 7px #61c99f; }
  .settings-panel,.inspector { border-color:#c9d6d9; background:rgba(255,255,255,.97); box-shadow:0 18px 50px #38556b35; }
  .panel-title { border-color:#dce5e7; background:#f8fbfb; } .panel-title small { color:#748899; } .panel-title button,.close { color:#6d8293; }
  details { border-color:#e0e8e9; } summary { color:#29465d; }
  .panel-search { border-color:#d2dddf; color:#718697; background:#f7fafa; } .panel-search input,.group-form input { color:#29465d; }
  .check-row,.range-row { color:#607689; } input[type="checkbox"],input[type="radio"],.range-row input,.depth-control input { accent-color:#118b87; }
  .group-row b { color:#3d566b; } .group-row small { color:#7b8e9e; } .text-action { color:#087b77; }
  .group-form { border-color:#dce5e7; background:#f6f9f9; } .group-form input { border-color:#d4dfe1; } .group-form label,.motion-options label { color:#607689; }
  .inspector .record-kicker,.status-line,.inspector h4 { color:#6e8292; } .status-line span,.relationship,.inspector-actions button { border-color:#dde6e8; } .inspector > p { color:#607689; } .relationship span { color:#778b9b; } .relationship b { color:#29465d; } .inspector-actions button { background:#f2f7f7; color:#36566b; }
  .source-modal::backdrop { background:#26415052; } .source-modal { border-color:#c8d5d8; background:#fff; color:#183047; box-shadow:0 25px 80px #38556b4d; } .source-modal > p,.source-modal form label { color:#607689; } .source-modal form input { border-color:#cad8da; background:#f8fbfb; color:#183047; } .primary { background:#178d88; } .current-source { border-color:#e0e8e9; color:#526b7e; }
  .source-browser button.scope-root small { color:#607689; } .from-computer { border-color:#e0e8e9; } .from-computer form button { border-color:#cad8da; color:#36566b; } .upload { color:#607689; } .upload input[type="file"] { color:#36566b; }
  .source-browser { border-color:#d6e0e2; } .source-browser button { border-color:#e6edef; color:#36566b; } .source-browser button:hover,.source-browser button.selected,.source-review { background:#f0f7f7; } .source-review { border-color:#d6e0e2; }
  .context-menu { border-color:#cbd8da; background:#fff; box-shadow:0 14px 35px #38556b3d; } .context-menu button { color:#36566b; } .context-menu button:hover { background:#edf6f5; }
  :global(:root[data-theme="dark"]) .knowledge-shell { background:var(--bg); color:var(--text-1); }
  :global(:root[data-theme="dark"]) .graph-toolbar { border-color:var(--border); background:color-mix(in srgb, var(--surface) 96%, transparent); box-shadow:var(--shadow-1); }
  :global(:root[data-theme="dark"]) .title-block h2 { color:var(--text-1); } :global(:root[data-theme="dark"]) .eyebrow { color:var(--text-2); }
  :global(:root[data-theme="dark"]) .search,:global(:root[data-theme="dark"]) .icon-button { border-color:var(--border-strong); background:var(--surface); color:var(--text-2); } :global(:root[data-theme="dark"]) .search input { color:var(--text-1); }
  :global(:root[data-theme="dark"]) .mode-switch { border-color:var(--border-strong); background:var(--sunken); } :global(:root[data-theme="dark"]) .mode-switch button.active { background:var(--accent-soft); color:var(--accent-strong); }
  :global(:root[data-theme="dark"]) .graph-workspace { background:radial-gradient(circle at 50% 45%, #18272a 0%, var(--surface) 45%, var(--bg) 100%); } :global(:root[data-theme="dark"]) .vignette { background:radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,.35) 100%); }
  :global(:root[data-theme="dark"]) line { stroke:rgba(154,167,180,.25); } :global(:root[data-theme="dark"]) line.highlighted { stroke:var(--accent); } :global(:root[data-theme="dark"]) .node-label { fill:var(--text-1); stroke:var(--surface); }
  :global(:root[data-theme="dark"]) .empty-copy span { color:var(--text-2); }
  :global(:root[data-theme="dark"]) .summary-pill,:global(:root[data-theme="dark"]) .viewport-controls,:global(:root[data-theme="dark"]) .graph-meta,:global(:root[data-theme="dark"]) .depth-control,:global(:root[data-theme="dark"]) .summary-popover,:global(:root[data-theme="dark"]) .settings-panel,:global(:root[data-theme="dark"]) .inspector { border-color:var(--border-strong); background:color-mix(in srgb, var(--surface) 94%, transparent); color:var(--text-2); box-shadow:var(--shadow-2); }
  :global(:root[data-theme="dark"]) .summary-popover p { color:var(--text-2); } :global(:root[data-theme="dark"]) .summary-popover p b,:global(:root[data-theme="dark"]) summary { color:var(--text-1); }
  :global(:root[data-theme="dark"]) .panel-title { border-color:var(--border); background:var(--raised); } :global(:root[data-theme="dark"]) details { border-color:var(--border); } :global(:root[data-theme="dark"]) .panel-search,:global(:root[data-theme="dark"]) .group-form { border-color:var(--border); background:var(--sunken); } :global(:root[data-theme="dark"]) .panel-search input,:global(:root[data-theme="dark"]) .group-form input { color:var(--text-1); }
  :global(:root[data-theme="dark"]) .check-row,:global(:root[data-theme="dark"]) .range-row,:global(:root[data-theme="dark"]) .motion-options label,:global(:root[data-theme="dark"]) .inspector > p { color:var(--text-2); } :global(:root[data-theme="dark"]) .group-row b,:global(:root[data-theme="dark"]) .relationship b { color:var(--text-1); }

  /* The same overrides for the viewer who never chose a theme. The palette
     above is the light one, and the block above it is keyed on the explicit
     `data-theme="dark"` attribute — which "system" deliberately does not set
     (see `lib/theme.ts`). Without this the Knowledge Map stayed light inside
     an otherwise dark app on every machine set to follow the OS. */
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme="light"])) .knowledge-shell { background:var(--bg); color:var(--text-1); }
    :global(:root:not([data-theme="light"])) .graph-toolbar { border-color:var(--border); background:color-mix(in srgb, var(--surface) 96%, transparent); box-shadow:var(--shadow-1); }
    :global(:root:not([data-theme="light"])) .title-block h2 { color:var(--text-1); } :global(:root:not([data-theme="light"])) .eyebrow { color:var(--text-2); }
    :global(:root:not([data-theme="light"])) .search,:global(:root:not([data-theme="light"])) .icon-button { border-color:var(--border-strong); background:var(--surface); color:var(--text-2); } :global(:root:not([data-theme="light"])) .search input { color:var(--text-1); }
    :global(:root:not([data-theme="light"])) .mode-switch { border-color:var(--border-strong); background:var(--sunken); } :global(:root:not([data-theme="light"])) .mode-switch button.active { background:var(--accent-soft); color:var(--accent-strong); }
    :global(:root:not([data-theme="light"])) .graph-workspace { background:radial-gradient(circle at 50% 45%, #18272a 0%, var(--surface) 45%, var(--bg) 100%); } :global(:root:not([data-theme="light"])) .vignette { background:radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,.35) 100%); }
    :global(:root:not([data-theme="light"])) line { stroke:rgba(154,167,180,.25); } :global(:root:not([data-theme="light"])) line.highlighted { stroke:var(--accent); } :global(:root:not([data-theme="light"])) .node-label { fill:var(--text-1); stroke:var(--surface); }
    :global(:root:not([data-theme="light"])) .empty-copy span { color:var(--text-2); }
    :global(:root:not([data-theme="light"])) .summary-pill,:global(:root:not([data-theme="light"])) .viewport-controls,:global(:root:not([data-theme="light"])) .graph-meta,:global(:root:not([data-theme="light"])) .depth-control,:global(:root:not([data-theme="light"])) .summary-popover,:global(:root:not([data-theme="light"])) .settings-panel,:global(:root:not([data-theme="light"])) .inspector { border-color:var(--border-strong); background:color-mix(in srgb, var(--surface) 94%, transparent); color:var(--text-2); box-shadow:var(--shadow-2); }
    :global(:root:not([data-theme="light"])) .summary-popover p { color:var(--text-2); } :global(:root:not([data-theme="light"])) .summary-popover p b,:global(:root:not([data-theme="light"])) summary { color:var(--text-1); }
    :global(:root:not([data-theme="light"])) .panel-title { border-color:var(--border); background:var(--raised); } :global(:root:not([data-theme="light"])) details { border-color:var(--border); } :global(:root:not([data-theme="light"])) .panel-search,:global(:root:not([data-theme="light"])) .group-form { border-color:var(--border); background:var(--sunken); } :global(:root:not([data-theme="light"])) .panel-search input,:global(:root:not([data-theme="light"])) .group-form input { color:var(--text-1); }
    :global(:root:not([data-theme="light"])) .check-row,:global(:root:not([data-theme="light"])) .range-row,:global(:root:not([data-theme="light"])) .motion-options label,:global(:root:not([data-theme="light"])) .inspector > p { color:var(--text-2); } :global(:root:not([data-theme="light"])) .group-row b,:global(:root:not([data-theme="light"])) .relationship b { color:var(--text-1); }
  }
  :global(:root[data-theme="dark"]) .source-modal { border-color:var(--border-strong); background:var(--raised); color:var(--text-1); } :global(:root[data-theme="dark"]) .source-modal > p,:global(:root[data-theme="dark"]) .source-modal form label { color:var(--text-2); } :global(:root[data-theme="dark"]) .source-modal form input { border-color:var(--border-strong); background:var(--sunken); color:var(--text-1); }
  :global(:root[data-theme="dark"]) .context-menu { border-color:var(--border-strong); background:var(--raised); } :global(:root[data-theme="dark"]) .context-menu button { color:var(--text-1); } :global(:root[data-theme="dark"]) .context-menu button:hover { background:var(--accent-soft); }
  @media (prefers-reduced-motion: reduce) { .particle { display:none; } }
  @media (max-width:800px) { .graph-toolbar { grid-template-columns:1fr auto auto auto; } .search { grid-row:2; grid-column:1/-1; margin-bottom:8px; } .knowledge-shell { grid-template-rows:auto 1fr; } .title-block { min-width:0; } .mode-switch { margin-left:auto; } .settings-panel,.inspector { width:min(300px, calc(100% - 28px)); } }
</style>
