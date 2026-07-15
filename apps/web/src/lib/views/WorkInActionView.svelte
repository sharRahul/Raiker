<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { BrainNode, BrainView } from "../apiTypes";

  const ACTIVE = new Set(["queued", "running", "paused"]);
  let brain = $state<BrainView | null>(null);
  let loadError = $state<string | null>(null);
  let refreshing = $state(false);

  async function load() {
    refreshing = true;
    loadError = null;
    try {
      brain = await api.brain();
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

  const nodes = $derived(brain?.nodes ?? []);
  const agents = $derived(nodes.filter((node) => node.node_type === "agent"));
  const tasks = $derived(nodes.filter((node) => node.node_type === "task" && ACTIVE.has(node.status)));
  const schedules = $derived(nodes.filter((node) => node.node_type === "schedule"));

  function statusText(node: BrainNode): string {
    const progress = node.progress_percent !== null ? ` · ${node.progress_percent}%` : "";
    return `${node.status}${progress}${node.detail ? ` · ${node.detail}` : ""}`;
  }
</script>

<div class="head-row">
  <div><p class="page-lead">Live operational view for this Raiker instance. Every task, status, schedule, and assignment comes from stored runtime records.</p><p class="truth-note"><Icon name="activity" size={15} /> Idle character movement is visual-only; it does not mean the agent is working.</p></div>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} disabled={refreshing}><Icon name="refresh" size={15} /> {refreshing ? "Refreshing…" : "Refresh"}</button>
</div>

{#if loadError}
  <p class="error" role="alert">{loadError}</p>
{:else if brain === null}
  <p class="loading">Loading work in action…</p>
{:else}
  <div class="work-layout">
    <section class="card agents"><h2>Subagents</h2>{#if agents.length}{#each agents as agent (agent.node_id)}<article class:busy={agent.status === "running"} class:idle={agent.status === "idle"} class="agent"><span class="agent-face" aria-hidden="true"><i></i><i></i></span><div><h3>{agent.label}</h3><p>{statusText(agent)}</p></div></article>{/each}{:else}<p class="empty">No subagents have been recorded for this instance.</p>{/if}</section>
    <section class="card tasks"><h2>Tasks in action</h2>{#if tasks.length}{#each tasks as task (task.node_id)}<article class="task"><div><h3>{task.label}</h3><p>{statusText(task)}</p></div>{#if task.progress_percent !== null}<div class="progress" role="progressbar" aria-label={`${task.label} progress`} aria-valuenow={task.progress_percent} aria-valuemin="0" aria-valuemax="100"><div style={`width:${task.progress_percent}%`}></div></div>{/if}</article>{/each}{:else}<p class="empty">No active, queued, or paused tasks are stored right now.</p>{/if}</section>
    <section class="card schedules"><h2>Scheduled work</h2>{#if schedules.length}{#each schedules as schedule (schedule.node_id)}<article><span class="wait-mark" aria-hidden="true"></span><div><h3>{schedule.label}</h3><p>Waiting · {schedule.detail}</p></div></article>{/each}{:else}<p class="empty">No scheduled work is stored right now.</p>{/if}</section>
  </div>
{/if}

<style>
  .head-row { display:flex; justify-content:space-between; align-items:flex-start; gap:var(--space-4); margin-bottom:var(--space-4); }.page-lead { margin:0; max-width:760px; color:var(--text-muted); }.truth-note { display:flex; align-items:center; gap:6px; margin:var(--space-2) 0 0; color:var(--text-muted); font-size:var(--text-sm); }
  .work-layout { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:var(--space-4); align-items:start; }.work-layout h2 { margin:0 0 var(--space-3); font-size:var(--text-base); }.work-layout article { display:flex; gap:10px; padding:12px 0; border-bottom:1px solid var(--border); }.work-layout article:last-child { border:0; }.work-layout h3 { margin:0; font-size:var(--text-sm); }.work-layout p { margin:3px 0 0; color:var(--text-muted); font-size:var(--text-sm); }.empty { color:var(--text-muted); font-size:var(--text-sm); }.agent-face { width:32px; height:32px; flex:0 0 auto; border-radius:48% 48% 42% 42%; background:#e7a55f; display:flex; align-items:center; justify-content:center; gap:5px; position:relative; }.agent-face::after { content:""; position:absolute; width:11px; height:4px; border-bottom:1px solid #523b2d; border-radius:50%; top:19px; }.agent-face i { width:3px; height:3px; border-radius:50%; background:#523b2d; }.agent.busy .agent-face { animation:work-bob 1.1s ease-in-out infinite; }.agent.idle .agent-face { animation:idle-float 3.4s ease-in-out infinite; }.task { display:grid !important; grid-template-columns:1fr; }.progress { height:6px; overflow:hidden; border-radius:4px; background:var(--border); }.progress div { height:100%; background:var(--accent); }.schedules article { align-items:center; }.wait-mark { width:18px; height:18px; flex:0 0 auto; border-radius:50%; background:#c89528; }.error { color:var(--danger); } @keyframes work-bob { 50% { transform:translateY(-3px); } } @keyframes idle-float { 50% { transform:translateY(-2px); } } @media(max-width:900px){.work-layout{grid-template-columns:1fr;}} @media(max-width:600px){.head-row{flex-direction:column;}}
</style>
