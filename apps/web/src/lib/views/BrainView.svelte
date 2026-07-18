<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { BrainNode, BrainView as BrainData } from "../apiTypes";

  type PositionedNode = BrainNode & { x: number; y: number; phase: number };

  // Column anchors per node type, laid out left→right across the canvas. The
  // exact x is jittered per-node so the graph reads as an organic Obsidian-style
  // cloud rather than a strict grid.
  const COLUMN: Record<string, number> = {
    user: 10,
    session: 22,
    folder: 34,
    file: 46,
    schedule: 38,
    task: 58,
    agent: 70,
    approval: 80,
    memory: 84,
    tool: 92,
    backup: 95,
  };
  const ACTIVE = new Set(["queued", "running", "paused"]);

  let brain = $state<BrainData | null>(null);
  let loadError = $state<string | null>(null);
  let selectedId = $state<string | null>(null);
  let refreshing = $state(false);
  let sourcePath = $state("");
  let sourceKind = $state<"folder" | "file">("folder");
  let sourceError = $state<string | null>(null);
  let sourceBusy = $state(false);

  async function load() {
    refreshing = true;
    loadError = null;
    try {
      brain = await api.brain();
      selectedId ??= brain.nodes[0]?.node_id ?? null;
    } catch (error) {
      loadError = error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
    } finally {
      refreshing = false;
    }
  }

  onMount(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15_000);
    return () => window.clearInterval(timer);
  });

  // Deterministic pseudo-random in [0,1) from a string so node positions are
  // stable between renders (no layout thrash) but look organic.
  function hash(str: string): number {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return ((h >>> 0) % 10000) / 10000;
  }

  function positions(nodes: BrainNode[]): PositionedNode[] {
    const totals = new Map<string, number>();
    for (const node of nodes) totals.set(node.node_type, (totals.get(node.node_type) ?? 0) + 1);
    const counts = new Map<string, number>();
    return nodes.map((node) => {
      const index = counts.get(node.node_type) ?? 0;
      counts.set(node.node_type, index + 1);
      const total = totals.get(node.node_type) ?? 1;
      const baseX = COLUMN[node.node_type] ?? 50;
      const jitterX = (hash(node.node_id) - 0.5) * 9;
      const baseY = 10 + ((index + 1) * 80) / (total + 1);
      const jitterY = (hash(node.node_id + "y") - 0.5) * 6;
      return {
        ...node,
        x: Math.max(4, Math.min(96, baseX + jitterX)),
        y: Math.max(6, Math.min(94, baseY + jitterY)),
        phase: hash(node.node_id + "p") * 6.283,
      };
    });
  }

  const graphNodes = $derived(positions(brain?.nodes ?? []));
  const positionsById = $derived(new Map(graphNodes.map((node) => [node.node_id, node])));
  const graphEdges = $derived(
    (brain?.edges ?? []).filter((edge) => positionsById.has(edge.source) && positionsById.has(edge.target)),
  );
  const selected = $derived(graphNodes.find((node) => node.node_id === selectedId) ?? null);
  const tasks = $derived(graphNodes.filter((node) => node.node_type === "task"));
  const waiting = $derived(graphNodes.filter((node) => node.node_type === "schedule"));
  const folders = $derived(graphNodes.filter((node) => node.node_type === "folder"));
  const files = $derived(graphNodes.filter((node) => node.node_type === "file"));
  const memoryNodes = $derived(graphNodes.filter((node) => node.node_type === "memory"));
  const sourceRoots = $derived(graphNodes.filter((node) => (node.node_type === "file" || node.node_type === "folder") && node.status === "selected"));
  const flow = $derived([
    { label: "Planning", count: tasks.length },
    { label: "Retrieval", count: graphNodes.filter((node) => node.node_type === "tool" && /retriev|recall|memory/i.test(node.label)).length },
    { label: "Tools", count: graphNodes.filter((node) => node.node_type === "tool").length },
    { label: "Memory", count: memoryNodes.length },
    { label: "Approvals", count: graphNodes.filter((node) => node.node_type === "approval").length },
    { label: "Waiting", count: waiting.length },
  ]);

  function edgePosition(id: string): PositionedNode | undefined {
    return positionsById.get(id);
  }

  // Human-readable status for the inspector panel (backend stores snake_case).
  function statusLabel(status: string): string {
    switch (status) {
      case "running": return "Working";
      case "idle": return "Idle";
      case "queued": return "Queued";
      case "paused": return "Paused";
      case "waiting": return "Waiting";
      case "completed": return "Done";
      case "failed": return "Failed";
      case "active": return "Active";
      case "selected": return "Selected";
      default: return status.charAt(0).toUpperCase() + status.slice(1);
    }
  }

  // Quadratic-bezier control point for a curved edge — gives the graph the
  // flowing, organic feel of Obsidian rather than straight rule lines.
  function curve(ax: number, ay: number, bx: number, by: number): string {
    const mx = (ax + bx) / 2 + (by - ay) * 0.18;
    const my = (ay + by) / 2 - (bx - ax) * 0.18;
    return `Q ${mx} ${my} ${bx} ${by}`;
  }

  async function addSource() {
    if (!sourcePath.trim()) return;
    sourceBusy = true;
    sourceError = null;
    try {
      await api.addBrainSource(sourcePath.trim());
      sourcePath = "";
      await load();
    } catch (error) {
      sourceError = error instanceof ApiError ? "Choose an existing file or folder inside this Raiker workspace." : "Could not add this source.";
    } finally {
      sourceBusy = false;
    }
  }

  async function removeSource(path: string) {
    sourceError = null;
    try {
      await api.removeBrainSource(path);
      await load();
    } catch {
      sourceError = "Could not remove this source.";
    }
  }
</script>

<div class="head-row">
  <div>
    <p class="page-lead">A live map of the stored runtime records behind Raiker’s work: sessions, tasks, agents, tools, approvals, memory, schedules, and backups.</p>
    <p class="truth-note"><Icon name="activity" size={15} /> {brain?.illustrative_motion_notice ?? "Loading the governed runtime graph…"}</p>
  </div>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} disabled={refreshing}>
    <Icon name="refresh" size={15} /> {refreshing ? "Refreshing…" : "Refresh"}
  </button>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load the brain graph" detail={loadError} />
{:else if brain === null}
  <PageState state="loading" title="Loading the brain graph…" />
{:else}
  <section class="flow card" aria-label="Brain function">
    <div><h2>Brain Function</h2><p>Each count is a current record in this workspace.</p></div>
    <div class="flow-list">
      {#each flow as stage (stage.label)}
        <span class:has-work={stage.count > 0}>{stage.label} <b>{stage.count}</b></span>
      {/each}
    </div>
  </section>

  <section class="card sources" aria-labelledby="sources-heading">
    <div><h2 id="sources-heading">Workspace sources</h2><p>Add files or folders you have deliberately placed inside this Raiker instance’s workspace. Their actual paths and children become graph nodes; nothing outside the workspace is read.</p></div>
    <form onsubmit={(event) => { event.preventDefault(); void addSource(); }}>
      <div class="source-form">
        <div class="kind-toggle" role="radiogroup" aria-label="Source kind">
          <button type="button" class:chosen={sourceKind === "folder"} aria-pressed={sourceKind === "folder"} onclick={() => sourceKind = "folder"}><Icon name="projects" size={14} /> Folder</button>
          <button type="button" class:chosen={sourceKind === "file"} aria-pressed={sourceKind === "file"} onclick={() => sourceKind = "file"}><Icon name="file" size={14} /> File</button>
        </div>
        <input class="input" bind:value={sourcePath} placeholder={sourceKind === "folder" ? "documents/research" : "notes/ideas.md"} disabled={sourceBusy} aria-label="Workspace-relative path" />
        <button class="btn btn-primary btn-sm" disabled={sourceBusy || !sourcePath.trim()}>{sourceBusy ? "Adding…" : `Add ${sourceKind}`}</button>
      </div>
    </form>
    {#if sourceError}<p class="error" role="alert">{sourceError}</p>{/if}
    {#if sourceRoots.length}
      <div class="source-list">{#each sourceRoots as source (source.node_id)}<span class="source-chip"><Icon name={source.node_type === "folder" ? "projects" : "file"} size={12} />{source.detail}<button type="button" aria-label={`Remove ${source.detail} from graph`} onclick={() => void removeSource(source.detail ?? "")}>×</button></span>{/each}</div>
    {:else}
      <p class="source-empty">Nothing added to memory yet. Folders and files you add above show up here and as nodes in the graph.</p>
    {/if}
  </section>

  <div class="brain-layout">
    <section class="card graph-card" aria-label="Raiker Brain relationship graph">
      <div class="graph-heading"><div><h2>Runtime connectivity</h2><p>Click a node to inspect its stored status.</p></div><span class="motion-key">Visual pulse</span></div>
      {#if graphNodes.length === 0}
        <p class="empty-graph">No sessions or work records yet. This graph only grows from stored runtime activity.</p>
      {:else}
        <div class="graph" aria-label="Interactive runtime relationship graph">
          <div class="graph-bg" aria-hidden="true"></div>
          <svg class="edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {#each graphEdges as edge (`${edge.source}:${edge.target}:${edge.relationship}`)}
              {@const source = edgePosition(edge.source)}
              {@const target = edgePosition(edge.target)}
              {#if source && target}
                <path class:active={edge.is_active} d={`M ${source.x} ${source.y} ${curve(source.x, source.y, target.x, target.y)}`} />
              {/if}
            {/each}
          </svg>
          {#each graphNodes as node (node.node_id)}
            {@const isFolder = node.node_type === "folder"}
            {@const isFile = node.node_type === "file"}
            <button
              type="button"
              class="node node-{node.node_type}"
              class:selected={node.node_id === selectedId}
              class:active-node={ACTIVE.has(node.status)}
              class:idle-node={node.status === "idle" || node.status === "waiting"}
              style={`left:${node.x}%;top:${node.y}%;--phase:${node.phase}s`}
              onclick={() => selectedId = node.node_id}
              aria-pressed={node.node_id === selectedId}
            >
              {#if node.node_type === "agent"}
                <span class="agent-face" aria-hidden="true"><i></i><i></i></span>
              {:else if isFolder}
                <span class="folder-mark" aria-hidden="true"></span>
              {:else if isFile}
                <span class="file-mark" aria-hidden="true"></span>
              {:else}
                <span class="node-dot" aria-hidden="true"></span>
              {/if}
              <span class="node-label">{node.label}</span>
            </button>
          {/each}
        </div>
        <div class="legend"><span><i class="dot task-dot"></i> work</span><span><i class="dot agent-dot"></i> subagent</span><span><i class="dot memory-dot"></i> memory</span><span><i class="dot folder-dot"></i> folder</span><span><i class="dot file-dot"></i> file</span><span><i class="dot tool-dot"></i> recorded tool/event</span></div>
      {/if}
    </section>

    <aside class="inspector-panel">
      <section class="card inspector">
        <h2>{selected?.label ?? "Select a node"}</h2>
        {#if selected}
          <p class="status"><span></span>{statusLabel(selected.status)}</p>
          <p class="inspector-detail">{selected.detail ?? "No additional stored metadata."}</p>
          {#if selected.progress_percent !== null}
            <div class="progress" aria-label={`${selected.label} progress`}><div style={`width:${selected.progress_percent}%`}></div></div>
          {/if}
        {:else}<p class="inspector-detail">Choose a node in the graph.</p>{/if}
      </section>
      <section class="card memory-card">
        <h2>In memory</h2>
        <p class="muted">Folders, files, and memory records you’ve added to the graph.</p>
        <ul class="memory-list">
          {#each folders as folder (folder.node_id)}<li class="kind-folder"><Icon name="projects" size={13} /> {folder.label}</li>{/each}
          {#each files as file (file.node_id)}<li class="kind-file"><Icon name="file" size={13} /> {file.label}</li>{/each}
          {#each memoryNodes as mem (mem.node_id)}<li class="kind-memory"><Icon name="spark" size={13} /> {mem.label}</li>{/each}
          {#if folders.length + files.length + memoryNodes.length === 0}<li class="empty-li">Nothing recorded yet.</li>{/if}
        </ul>
      </section>
    </aside>
  </div>
{/if}

<style>
  .head-row { display:flex; justify-content:space-between; gap:var(--space-4); align-items:flex-start; margin-bottom:var(--space-4); }
  .page-lead { max-width:850px; margin:0; color:var(--text-2); }
  .truth-note { display:flex; align-items:center; gap:6px; color:var(--text-2); font-size:0.85rem; margin:var(--space-2) 0 0; }
  .flow { display:flex; justify-content:space-between; align-items:center; gap:var(--space-4); margin-bottom:var(--space-4); }
  .flow h2,.graph-heading h2,.inspector h2,.sources h2,.memory-card h2 { font-size:1rem; margin:0; }
  .flow p,.graph-heading p,.inspector p,.sources p,.memory-card p { color:var(--text-2); font-size:0.85rem; margin:4px 0 0; }
  .flow-list { display:flex; flex-wrap:wrap; gap:8px; }
  .flow-list span { border:1px solid var(--border); border-radius:var(--r-pill); color:var(--text-2); font-size:0.8rem; padding:5px 9px; }
  .flow-list .has-work { border-color:var(--accent); color:var(--text-1); }
  .flow-list b { margin-left:4px; }
  .sources { display:grid; gap:var(--space-3); margin-bottom:var(--space-4); }
  .source-form { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .source-form .input { flex:1; min-width:12rem; }
  .kind-toggle { display:inline-flex; border:1px solid var(--border-strong); border-radius:var(--r-sm); overflow:hidden; }
  .kind-toggle button { display:inline-flex; align-items:center; gap:5px; border:0; background:var(--surface); color:var(--text-2); font:inherit; font-size:0.8rem; padding:.32rem .6rem; cursor:pointer; }
  .kind-toggle button.chosen { background:var(--accent-soft); color:var(--accent); }
  .source-list { display:flex; gap:7px; flex-wrap:wrap; }
  .source-chip { display:flex; align-items:center; gap:5px; border:1px solid var(--accent-border); border-radius:var(--r-pill); color:var(--text-1); background:var(--accent-soft); font-size:0.78rem; padding:4px 8px; }
  .source-chip button { appearance:none; border:0; background:transparent; color:inherit; cursor:pointer; font-size:16px; line-height:1; }
  .source-empty { color:var(--text-3); font-size:0.8rem; margin:0; }

  .brain-layout { display:grid; grid-template-columns:minmax(0, 1fr) minmax(220px, 280px); gap:var(--space-4); }
  .graph-card { min-width:0; }
  .graph-heading { display:flex; justify-content:space-between; gap:var(--space-3); }
  .motion-key { color:var(--text-3); font-size:0.72rem; }
  .empty-graph { color:var(--text-2); font-size:0.85rem; }
  .graph { position:relative; height:520px; margin-top:var(--space-3); overflow:hidden; border:1px solid var(--border); border-radius:var(--r-md); background:radial-gradient(circle at 50% 40%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 55%); }
  .graph-bg { position:absolute; inset:0; background-image:radial-gradient(color-mix(in srgb, var(--text-3) 18%, transparent) 1px, transparent 1px); background-size:22px 22px; opacity:.35; animation:drift 22s linear infinite; }
  .edges { position:absolute; inset:0; width:100%; height:100%; }
  path { fill:none; stroke:var(--border-strong); stroke-width:.32; vector-effect:non-scaling-stroke; opacity:.85; }
  path.active { stroke:var(--accent); stroke-width:.5; stroke-dasharray:3 4; animation:travel 1.6s linear infinite; }

  .node { position:absolute; transform:translate(-50%, -50%); display:flex; flex-direction:column; align-items:center; gap:4px; padding:0; border:0; background:transparent; color:var(--text-1); font-size:0.7rem; line-height:1.05; cursor:pointer; animation:node-float 5.2s ease-in-out infinite; animation-delay:var(--phase, 0s); }
  .node:hover .node-label,.node.selected .node-label { color:var(--accent); font-weight:700; }
  .node-label { max-width:96px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:center; color:var(--text-2); transition:color 120ms var(--ease); }
  .node-dot,.folder-mark,.file-mark { display:block; border-radius:50%; background:var(--text-3); transition:transform 160ms var(--ease), box-shadow 160ms var(--ease); }
  .node-dot { width:9px; height:9px; }
  .folder-mark { width:11px; height:11px; border-radius:2px; background:#c89528; }
  .file-mark { width:9px; height:11px; border-radius:1px; background:#4781be; }
  .node:hover .node-dot,.node:hover .folder-mark,.node:hover .file-mark,.node.selected .node-dot,.node.selected .folder-mark,.node.selected .file-mark { transform:scale(1.45); box-shadow:0 0 0 4px color-mix(in srgb, var(--accent) 22%, transparent); }
  .node.active-node .node-dot,.node.active-node .folder-mark,.node.active-node .file-mark { animation:ping 1.7s ease-in-out infinite; }
  .node.idle-node { opacity:.78; }
  .node-task .node-dot { background:#7c5cff; }
  .node-memory .node-dot { background:#d7833f; }
  .node-tool .node-dot { background:#3c9f91; }
  .node-approval .node-dot { background:#ce5e78; }
  .node-schedule .node-dot { background:#c89528; }
  .node-backup .node-dot { background:#4781be; }

  .agent-face { width:18px; height:18px; border-radius:48% 48% 42% 42%; background:#e7a55f; display:flex; align-items:center; justify-content:center; gap:3px; position:relative; box-shadow:0 0 0 0 color-mix(in srgb, #e7a55f 40%, transparent); }
  .agent-face::after { content:""; position:absolute; width:7px; height:3px; border-bottom:1px solid #523b2d; border-radius:50%; top:11px; }
  .agent-face i { width:2px; height:2px; border-radius:50%; background:#523b2d; }

  .legend { display:flex; flex-wrap:wrap; gap:12px; color:var(--text-3); font-size:0.72rem; margin-top:var(--space-3); }
  .legend span { display:flex; align-items:center; gap:5px; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--text-3); display:inline-block; }
  .task-dot { background:#7c5cff; } .agent-dot { background:#e7a55f; } .memory-dot { background:#d7833f; } .tool-dot { background:#3c9f91; } .folder-dot { background:#c89528; border-radius:2px; } .file-dot { background:#4781be; border-radius:1px; }

  .inspector-panel { display:grid; align-content:start; gap:var(--space-4); }
  .status { display:flex; align-items:center; gap:6px; text-transform:capitalize; }
  .status span { width:7px; height:7px; border-radius:50%; background:var(--accent); }
  .inspector-detail { color:var(--text-2); font-size:0.85rem; }
  .progress { height:6px; overflow:hidden; border-radius:4px; background:var(--sunken); margin-top:var(--space-3); }
  .progress div { height:100%; background:var(--accent); }
  .memory-card .muted { color:var(--text-3); font-size:0.78rem; }
  .memory-list { list-style:none; margin:var(--space-2) 0 0; padding:0; display:grid; gap:5px; }
  .memory-list li { display:flex; align-items:center; gap:6px; color:var(--text-1); font-size:0.82rem; }
  .kind-folder { color:#c89528; } .kind-file { color:#4781be; } .kind-memory { color:#d7833f; }
  .empty-li { color:var(--text-3); font-size:0.78rem; }
  .error { color:var(--danger); }

  @keyframes node-float { 0%,100% { transform:translate(-50%, -50%); } 50% { transform:translate(-50%, -54%); } }
  @keyframes ping { 50% { transform:scale(1.5); box-shadow:0 0 0 6px color-mix(in srgb, var(--accent) 30%, transparent); } }
  @keyframes travel { to { stroke-dashoffset:-14; } }
  @keyframes drift { to { background-position:22px -22px; } }
  @media (max-width: 900px) { .brain-layout { grid-template-columns:1fr; } .graph { height:440px; } .flow { align-items:flex-start; flex-direction:column; } }
  @media (max-width: 600px) { .head-row { flex-direction:column; } .graph { height:380px; } .node-label { font-size:0.62rem; } }
</style>
