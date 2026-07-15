<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { BrainNode, BrainView as BrainData } from "../apiTypes";

  type PositionedNode = BrainNode & { x: number; y: number };

  const COLUMN: Record<string, number> = {
    user: 8,
    session: 24,
    folder: 35,
    file: 48,
    schedule: 37,
    task: 46,
    agent: 63,
    approval: 76,
    memory: 79,
    tool: 91,
    backup: 94,
  };
  const ACTIVE = new Set(["queued", "running", "paused"]);

  let brain = $state<BrainData | null>(null);
  let loadError = $state<string | null>(null);
  let selectedId = $state<string | null>(null);
  let refreshing = $state(false);
  let sourcePath = $state("");
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

  function positions(nodes: BrainNode[]): PositionedNode[] {
    const totals = new Map<string, number>();
    for (const node of nodes) totals.set(node.node_type, (totals.get(node.node_type) ?? 0) + 1);
    const counts = new Map<string, number>();
    return nodes.map((node) => {
      const index = counts.get(node.node_type) ?? 0;
      counts.set(node.node_type, index + 1);
      return {
        ...node,
        x: COLUMN[node.node_type] ?? 50,
        y: 8 + ((index + 1) * 84) / ((totals.get(node.node_type) ?? 0) + 1),
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
  const sourceRoots = $derived(graphNodes.filter((node) => (node.node_type === "file" || node.node_type === "folder") && node.status === "selected"));
  const flow = $derived([
    { label: "Planning", count: tasks.length },
    { label: "Retrieval", count: graphNodes.filter((node) => node.node_type === "tool" && /retriev|recall|memory/i.test(node.label)).length },
    { label: "Tools", count: graphNodes.filter((node) => node.node_type === "tool").length },
    { label: "Memory", count: graphNodes.filter((node) => node.node_type === "memory").length },
    { label: "Approvals", count: graphNodes.filter((node) => node.node_type === "approval").length },
    { label: "Waiting", count: waiting.length },
  ]);

  function edgePosition(id: string): PositionedNode | undefined {
    return positionsById.get(id);
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
  <p class="error" role="alert">{loadError}</p>
{:else if brain === null}
  <p class="loading">Loading Raiker Brain…</p>
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
      <label for="brain-source">Workspace-relative path</label>
      <div class="source-form"><input id="brain-source" class="input" bind:value={sourcePath} placeholder="documents/research" disabled={sourceBusy} /><button class="btn btn-primary btn-sm" disabled={sourceBusy || !sourcePath.trim()}>{sourceBusy ? "Adding…" : "Add source"}</button></div>
    </form>
    {#if sourceError}<p class="error" role="alert">{sourceError}</p>{/if}
    {#if sourceRoots.length}
      <div class="source-list">{#each sourceRoots as source (source.node_id)}<span>{source.detail}<button type="button" aria-label={`Remove ${source.detail} from graph`} onclick={() => void removeSource(source.detail ?? "")}>×</button></span>{/each}</div>
    {/if}
  </section>

  <div class="brain-layout">
    <section class="card graph-card" aria-label="Raiker Brain relationship graph">
      <div class="graph-heading"><div><h2>Runtime connectivity</h2><p>Click a node to inspect its stored status.</p></div><span class="motion-key">Visual pulse</span></div>
      {#if graphNodes.length === 1}
        <p class="empty-graph">No sessions or work records yet. This graph only grows from stored runtime activity.</p>
      {/if}
      <div class="graph" aria-label="Interactive runtime relationship graph">
        <svg class="edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {#each graphEdges as edge (`${edge.source}:${edge.target}:${edge.relationship}`)}
            {@const source = edgePosition(edge.source)}
            {@const target = edgePosition(edge.target)}
            {#if source && target}
              <line class:active={edge.is_active} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />
            {/if}
          {/each}
        </svg>
        {#each graphNodes as node (node.node_id)}
          <button
            type="button"
            class="node node-{node.node_type}"
            class:selected={node.node_id === selectedId}
            class:active-node={ACTIVE.has(node.status)}
            class:idle-node={node.status === "idle" || node.status === "waiting"}
            style={`left:${node.x}%;top:${node.y}%`}
            onclick={() => selectedId = node.node_id}
            aria-pressed={node.node_id === selectedId}
          >
            {#if node.node_type === "agent"}
              <span class="agent-face" aria-hidden="true"><i></i><i></i></span>
            {:else}
              <span class="node-dot" aria-hidden="true"></span>
            {/if}
            <span>{node.label}</span>
          </button>
        {/each}
      </div>
      <div class="legend"><span><i class="dot task-dot"></i> work</span><span><i class="dot agent-dot"></i> subagent</span><span><i class="dot memory-dot"></i> memory</span><span><i class="dot tool-dot"></i> recorded tool/event</span></div>
    </section>

    <aside class="inspector-panel">
      <section class="card inspector">
        <h2>{selected?.label ?? "Select a node"}</h2>
        {#if selected}
          <p class="status"><span></span>{selected.status}</p>
          <p>{selected.detail ?? "No additional stored metadata."}</p>
          {#if selected.progress_percent !== null}
            <div class="progress" aria-label={`${selected.label} progress`}><div style={`width:${selected.progress_percent}%`}></div></div>
          {/if}
        {:else}<p>Choose a node in the graph.</p>{/if}
      </section>
    </aside>
  </div>
{/if}

<style>
  .head-row { display:flex; justify-content:space-between; gap:var(--space-4); align-items:flex-start; margin-bottom:var(--space-4); }
  .page-lead { max-width:850px; margin:0; color:var(--text-muted); }
  .truth-note { display:flex; align-items:center; gap:6px; color:var(--text-muted); font-size:var(--text-sm); margin:var(--space-2) 0 0; }
  .flow { display:flex; justify-content:space-between; align-items:center; gap:var(--space-4); margin-bottom:var(--space-4); }
  .flow h2,.graph-heading h2,.inspector h2,.sources h2 { font-size:var(--text-base); margin:0; }
  .flow p,.graph-heading p,.inspector p,.sources p { color:var(--text-muted); font-size:var(--text-sm); margin:4px 0 0; }
  .flow-list { display:flex; flex-wrap:wrap; gap:8px; }
  .flow-list span { border:1px solid var(--border); border-radius:999px; color:var(--text-muted); font-size:var(--text-sm); padding:5px 9px; }
  .flow-list .has-work { border-color:var(--accent); color:var(--text); }
  .flow-list b { margin-left:4px; }
  .sources { display:grid; gap:var(--space-3); margin-bottom:var(--space-4); }.sources label { display:block; color:var(--text-muted); font-size:var(--text-xs); margin-bottom:4px; }.source-form { display:flex; gap:8px; }.source-form input { flex:1; }.source-list { display:flex; gap:7px; flex-wrap:wrap; }.source-list span { display:flex; align-items:center; gap:5px; border:1px solid var(--border); border-radius:999px; color:var(--text-muted); font-size:var(--text-xs); padding:4px 7px; }.source-list button { appearance:none; border:0; background:transparent; color:inherit; cursor:pointer; font-size:16px; line-height:1; }
  .brain-layout { display:grid; grid-template-columns:minmax(0, 1fr) minmax(220px, 280px); gap:var(--space-4); }
  .graph-card { min-width:0; }
  .graph-heading { display:flex; justify-content:space-between; gap:var(--space-3); }
  .motion-key { color:var(--text-muted); font-size:var(--text-xs); }
  .empty-graph { color:var(--text-muted); font-size:var(--text-sm); }
  .graph { position:relative; height:500px; margin-top:var(--space-3); overflow:hidden; border:1px solid var(--border); border-radius:var(--radius-md); background:radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--accent) 8%, transparent), transparent 48%); }
  .edges { position:absolute; inset:0; width:100%; height:100%; }
  line { stroke:var(--border); stroke-width:.35; vector-effect:non-scaling-stroke; }
  line.active { stroke:var(--accent); stroke-dasharray:4 4; animation:travel 1.8s linear infinite; }
  .node { position:absolute; transform:translate(-50%, -50%); max-width:116px; display:flex; align-items:center; gap:5px; padding:5px 8px; border:1px solid var(--border); border-radius:999px; color:var(--text); background:var(--surface); font-size:11px; line-height:1.1; box-shadow:0 2px 9px color-mix(in srgb, #000 12%, transparent); }
  .node:hover,.node.selected { border-color:var(--accent); outline:2px solid color-mix(in srgb, var(--accent) 23%, transparent); }
  .node.active-node .node-dot { animation:pulse 1.7s ease-in-out infinite; }
  .node.idle-node { animation:idle-float 3.4s ease-in-out infinite; }
  .node-dot,.dot { width:8px; height:8px; flex:0 0 auto; border-radius:50%; background:var(--text-muted); }
  .node-task .node-dot,.task-dot { background:#7c5cff; }.node-memory .node-dot,.memory-dot { background:#d7833f; }.node-tool .node-dot,.tool-dot { background:#3c9f91; }.node-approval .node-dot { background:#ce5e78; }.node-schedule .node-dot { background:#c89528; }.node-backup .node-dot { background:#4781be; }
  .agent-face,.mini-agent { width:18px; height:18px; flex:0 0 auto; border-radius:48% 48% 42% 42%; background:#e7a55f; display:flex; align-items:center; justify-content:center; gap:3px; position:relative; }
  .agent-face::after,.mini-agent::after { content:""; position:absolute; width:7px; height:3px; border-bottom:1px solid #523b2d; border-radius:50%; top:11px; }.agent-face i { width:2px; height:2px; border-radius:50%; background:#523b2d; }
  .legend { display:flex; flex-wrap:wrap; gap:12px; color:var(--text-muted); font-size:var(--text-xs); margin-top:var(--space-3); }.legend span { display:flex; align-items:center; gap:5px; }
  .inspector-panel { display:grid; align-content:start; gap:var(--space-4); }.status { display:flex; align-items:center; gap:6px; text-transform:capitalize; }.status span { width:7px; height:7px; border-radius:50%; background:var(--accent); }.progress { height:6px; overflow:hidden; border-radius:4px; background:var(--border); margin-top:var(--space-3); }.progress div { height:100%; background:var(--accent); }
  @keyframes pulse { 50% { opacity:.45; transform:scale(1.35); } } @keyframes travel { to { stroke-dashoffset:-16; } } @keyframes idle-float { 50% { margin-top:-3px; } }
  @media (max-width: 900px) { .brain-layout { grid-template-columns:1fr; }.graph { height:420px; }.flow { align-items:flex-start; flex-direction:column; } }
  @media (max-width: 600px) { .head-row { flex-direction:column; }.graph { height:360px; }.node { max-width:85px; font-size:10px; } }
</style>
