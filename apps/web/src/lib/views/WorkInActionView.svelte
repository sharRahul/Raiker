<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { BrainNode, BrainView } from "../apiTypes";

  // `continuing` is a granted approval being replayed into a parked scheduled
// run (BUG-25): unfinished, so it belongs on the live board.
const ACTIVE = new Set(["queued", "running", "continuing", "paused", "waiting_for_approval", "waiting_for_children"]);
  // A run that ended is still the thing the owner most needs to read, because
  // the reason it ended lives nowhere else on this page (BUG-09).
  const FINISHED = new Set(["completed", "failed", "cancelled"]);
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
  const finished = $derived(nodes.filter((node) => node.node_type === "task" && FINISHED.has(node.status)).slice(0, 10));
  const schedules = $derived(nodes.filter((node) => node.node_type === "schedule"));

  // Cartoon character state derives from the agent's runtime status.
  function mood(status: string): "working" | "idle" | "queued" | "paused" {
    if (status === "running" || status === "continuing") return "working";
    if (status === "queued") return "queued";
    if (status === "paused") return "paused";
    return "idle";
  }

  // Plain-English label for the mood badge (the internal mood token is never
  // shown to the user).
  function moodLabel(m: string): string {
    switch (m) {
      case "working": return "Working";
      case "idle": return "Idle";
      case "queued": return "Queued";
      case "paused": return "Paused";
      default: return m;
    }
  }

  function statusText(node: BrainNode): string {
    const progress = node.progress_percent !== null ? ` · ${node.progress_percent}%` : "";
    const label = statusLabel(node.status);
    return `${label}${progress}${node.detail ? ` · ${node.detail}` : ""}`;
  }

  // Human-readable status (the backend stores snake_case identifiers).
  function statusLabel(status: string): string {
    switch (status) {
      case "running": return "Working";
      case "idle": return "Idle";
      case "queued": return "Queued";
      case "paused": return "Paused";
      case "waiting": return "Waiting";
      case "waiting_for_approval": return "Waiting for approval";
      case "continuing": return "Continuing after approval";
      case "cancelled": return "Stopped";
      case "completed": return "Done";
      case "failed": return "Failed";
      case "active": return "Active";
      case "selected": return "Selected";
      default: return status.charAt(0).toUpperCase() + status.slice(1);
    }
  }
</script>

<div class="head-row">
  <div><p class="page-lead">Live operational view for this Raiker instance. Every task, status, schedule, and assignment comes from stored runtime records.</p><p class="truth-note"><Icon name="activity" size="sm" /> Idle character movement is visual-only; it does not mean the agent is working.</p></div>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} disabled={refreshing}><Icon name="refresh" size="sm" /> {refreshing ? "Refreshing…" : "Refresh"}</button>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load live work" detail={loadError} />
{:else if brain === null}
  <PageState state="loading" title="Loading live work…" />
{:else}
  <section class="card floor" aria-label="Agent workstations">
    <div class="floor-head"><h2>Workstations</h2><p>Each character is a recorded subagent. Their movement reflects stored status only.</p></div>
    {#if agents.length}
      <div class="desks">
        {#each agents as agent (agent.node_id)}
          {@const m = mood(agent.status)}
          <article class="desk" data-mood={m}>
            <div class="scene">
              <div class="lamp"></div>
              <div class="character">
                <span class="body"></span>
                <span class="face">
                  <span class="eye left"></span>
                  <span class="eye right"></span>
                  <span class="mouth"></span>
                </span>
                <span class="arm left"></span>
                <span class="arm right"></span>
                {#if m === "idle"}<span class="zzz" aria-hidden="true">z</span><span class="zzz z2" aria-hidden="true">z</span><span class="zzz z3" aria-hidden="true">Z</span>{/if}
                {#if m === "working"}<span class="sweat" aria-hidden="true"></span>{/if}
              </div>
              <div class="desk-surface"></div>
              <div class="screen" class:lit={m === "working"}></div>
              {#if m === "working"}<span class="motion-lines" aria-hidden="true"><i></i><i></i><i></i></span>{/if}
              {#if m === "queued"}<span class="wait-clock" aria-hidden="true"></span>{/if}
            </div>
            <div class="desk-label">
              <h3>{agent.label}</h3>
              <p>{statusText(agent)}</p>
              <span class="mood-tag" data-mood={m}>{moodLabel(m)}</span>
            </div>
          </article>
        {/each}
      </div>
    {:else}
      <p class="empty">No subagents have been recorded for this instance.</p>
    {/if}
  </section>

  <div class="work-layout">
    <section class="card tasks">
      <h2>Tasks in action</h2>
      {#if tasks.length}
        <ul class="conveyor">
          {#each tasks as task (task.node_id)}
            <li class="crate" style="--step:{task.progress_percent ?? 0}%">
              <div class="crate-body">
                <h3>{task.label}</h3>
                <p>{statusText(task)}</p>
              </div>
              {#if task.progress_percent !== null}
                <div class="progress" role="progressbar" aria-label={`${task.label} progress`} aria-valuenow={task.progress_percent} aria-valuemin="0" aria-valuemax="100"><div style={`width:${task.progress_percent}%`}></div></div>
              {/if}
            </li>
          {/each}
        </ul>
      {:else}<p class="empty">No task is queued, running, paused, or waiting for approval right now.</p>{/if}

      {#if finished.length}
        <h3 class="finished-head">How the last runs ended</h3>
        <ul class="finished">
          {#each finished as task (task.node_id)}
            <li>
              <div><h4>{task.label}</h4><p>{statusLabel(task.status)} · {task.detail ?? "No reason was recorded for this outcome."}</p></div>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="card schedules">
      <h2>Scheduled work</h2>
      {#if schedules.length}
        <ul class="waitlist">
          {#each schedules as schedule (schedule.node_id)}
            <li>
              <span class="wait-mark" aria-hidden="true"></span>
              <div><h3>{schedule.label}</h3><p>Waiting · {schedule.detail}</p></div>
            </li>
          {/each}
        </ul>
      {:else}<p class="empty">No scheduled work is stored right now.</p>{/if}
    </section>
  </div>
{/if}

<style>
  /* Layout comes from the shared `.head-row` in app.css; only the spacing
     below it is this view's own. */
  .head-row { margin-bottom:var(--space-4); }
  .page-lead { margin:0; max-width:760px; color:var(--text-2); }
  .truth-note { display:flex; align-items:center; gap:6px; margin:var(--space-2) 0 0; color:var(--text-2); font-size:var(--text-sm); }

  /* ── Workstations: cartoon agents at desks ── */
  .floor { margin-bottom:var(--space-4); }
  .floor-head h2 { margin:0; font-size:var(--text-base); }
  .floor-head p { margin:4px 0 0; color:var(--text-2); font-size:var(--text-sm); }
  .desks { display:grid; grid-template-columns:repeat(auto-fill, minmax(180px, 1fr)); gap:var(--space-4); margin-top:var(--space-4); }
  .desk { display:grid; gap:10px; justify-items:center; }
  .scene { position:relative; width:160px; height:120px; border:1px solid var(--border); border-radius:var(--r-md); background:linear-gradient(180deg, var(--sunken), var(--surface)); overflow:hidden; }
  .lamp { position:absolute; top:8px; left:14px; width:14px; height:14px; border-radius:50%; background:radial-gradient(circle, #ffd87a, #f5b942); box-shadow:0 0 14px #f5b94266; animation:lamp-glow 3.4s ease-in-out infinite; }
  .desk-surface { position:absolute; bottom:0; left:0; right:0; height:14px; background:linear-gradient(180deg, #8b5e34, #6b4524); border-top:2px solid #a87a4a; }
  .screen { position:absolute; bottom:16px; right:12px; width:42px; height:30px; background:#1c2630; border:2px solid #3a4a55; border-radius:4px; transition:background 200ms var(--ease); }
  .screen.lit { background:linear-gradient(180deg, #11303a, #0f2a33); box-shadow:0 0 12px color-mix(in srgb, var(--accent) 50%, transparent); animation:screen-flicker 1.4s steps(2) infinite; }

  .character { position:absolute; bottom:14px; left:54px; width:42px; height:54px; animation:char-bob 2.6s ease-in-out infinite; }
  .desk[data-mood="working"] .character { animation:char-work 0.9s ease-in-out infinite; }
  .desk[data-mood="idle"] .character { animation:char-sleep 3.6s ease-in-out infinite; }
  .desk[data-mood="queued"] .character { animation:char-tap 1.4s ease-in-out infinite; }
  .desk[data-mood="paused"] .character { animation:none; }

  .body { position:absolute; bottom:0; left:6px; width:30px; height:34px; background:linear-gradient(180deg, #e7a55f, #d18a44); border-radius:48% 48% 42% 42%; box-shadow:inset -3px -3px 0 #b97534; }
  .face { position:absolute; top:6px; left:0; right:0; display:flex; justify-content:center; gap:7px; }
  .eye { width:4px; height:4px; border-radius:50%; background:#3b2a1d; transition:all 200ms var(--ease); }
  .desk[data-mood="idle"] .eye { height:1.5px; border-radius:1px; }
  .mouth { position:absolute; top:11px; width:8px; height:3px; border-bottom:1.5px solid #3b2a1d; border-radius:0 0 6px 6px; }
  .desk[data-mood="working"] .mouth { border-bottom-color:#3b2a1d; animation:mouth-talk 0.45s steps(2) infinite; }
  .desk[data-mood="idle"] .mouth { width:6px; height:5px; border:1.5px solid #3b2a1d; border-top:0; border-radius:0 0 6px 6px; }
  .arm { position:absolute; bottom:8px; width:4px; height:16px; background:#d18a44; border-radius:2px; }
  .arm.left { left:2px; transform:rotate(8deg); }
  .arm.right { right:2px; transform:rotate(-8deg); }
  .desk[data-mood="working"] .arm.right { animation:arm-type 0.5s ease-in-out infinite; transform-origin:top center; }
  .desk[data-mood="queued"] .arm.right { animation:arm-tap 1.4s ease-in-out infinite; transform-origin:top center; }

  .zzz { position:absolute; top:-6px; left:18px; color:var(--text-3); font-size:var(--text-2xs); font-weight:700; opacity:0; animation:zzz 3.6s ease-in-out infinite; }
  .z2 { left:26px; animation-delay:1.2s; } .z3 { left:34px; font-size:var(--text-md); animation-delay:2.4s; }
  .sweat { position:absolute; top:2px; right:4px; width:5px; height:7px; background:#9ed1ff; border-radius:50% 50% 50% 50% / 60% 60% 40% 40%; animation:sweat 1.8s ease-in infinite; opacity:0; }
  .motion-lines { position:absolute; top:14px; right:-4px; display:flex; flex-direction:column; gap:3px; }
  .motion-lines i { display:block; width:6px; height:1.5px; background:var(--accent); opacity:0; animation:motion 0.6s ease-out infinite; }
  .motion-lines i:nth-child(2) { animation-delay:0.2s; } .motion-lines i:nth-child(3) { animation-delay:0.4s; }
  .wait-clock { position:absolute; top:10px; right:10px; width:16px; height:16px; border:2px solid var(--text-3); border-radius:50%; animation:clock-tick 1.4s ease-in-out infinite; }
  .wait-clock::before { content:""; position:absolute; top:50%; left:50%; width:1.5px; height:5px; background:var(--text-3); transform-origin:bottom center; transform:translate(-50%,-100%) rotate(0deg); }
  .wait-clock::after { content:""; position:absolute; top:50%; left:50%; width:1.5px; height:3px; background:var(--text-3); transform-origin:bottom center; transform:translate(-50%,-100%) rotate(90deg); }

  .desk-label { text-align:center; }
  .desk-label h3 { margin:0; font-size:var(--text-sm); }
  .desk-label p { margin:3px 0 0; color:var(--text-2); font-size:var(--text-sm); }
  .mood-tag { display:inline-block; margin-top:5px; font-size:var(--text-2xs); font-weight:700; text-transform:uppercase; letter-spacing:0.06em; padding:2px 7px; border-radius:var(--r-pill); border:1px solid var(--border); color:var(--text-2); }
  .mood-tag[data-mood="working"] { color:var(--accent); border-color:var(--accent-border); background:var(--accent-soft); }
  .mood-tag[data-mood="idle"] { color:var(--text-3); }
  .mood-tag[data-mood="queued"] { color:var(--warn); border-color:var(--warn-border); background:var(--warn-soft); }
  .mood-tag[data-mood="paused"] { color:var(--danger); border-color:var(--danger-border); background:var(--danger-soft); }

  /* ── Tasks (conveyor) + schedules (waitlist) ── */
  .work-layout { display:grid; grid-template-columns:1.4fr 1fr; gap:var(--space-4); align-items:start; }
  .work-layout h2 { margin:0 0 var(--space-3); font-size:var(--text-base); }
  .conveyor { list-style:none; margin:0; padding:0; display:grid; gap:10px; }
  .crate { position:relative; display:grid; grid-template-columns:1fr; gap:8px; padding:12px 14px; border:1px solid var(--border); border-radius:var(--r-md); background:var(--surface); box-shadow:var(--shadow-1); animation:crate-glide 0.6s var(--ease) both; }
  .crate-body h3 { margin:0; font-size:var(--text-md); } .crate-body p { margin:3px 0 0; color:var(--text-2); font-size:var(--text-sm); }
  .progress { height:6px; overflow:hidden; border-radius:4px; background:var(--sunken); } .progress div { height:100%; background:var(--accent); transition:width 400ms var(--ease); }
  .finished-head { margin:var(--space-4) 0 8px; font-size:var(--text-sm); color:var(--text-2); }
  .finished { list-style:none; margin:0; padding:0; display:grid; gap:8px; }
  .finished li { padding:8px 0; border-bottom:1px solid var(--border); }
  .finished li:last-child { border:0; }
  .finished h4 { margin:0; font-size:var(--text-sm); } .finished p { margin:2px 0 0; color:var(--text-2); font-size:var(--text-sm); }

  .waitlist { list-style:none; margin:0; padding:0; display:grid; gap:8px; }
  .waitlist li { display:flex; gap:10px; align-items:center; padding:10px 0; border-bottom:1px solid var(--border); }
  .waitlist li:last-child { border:0; }
  .waitlist h3 { margin:0; font-size:var(--text-sm); } .waitlist p { margin:2px 0 0; color:var(--text-2); font-size:var(--text-sm); }
  .wait-mark { width:14px; height:14px; flex:0 0 auto; border-radius:50%; background:#c89528; animation:wait-pulse 2.2s ease-in-out infinite; }
  .empty { color:var(--text-2); font-size:var(--text-sm); }

  @keyframes char-bob { 50% { transform:translateY(-2px); } }
  @keyframes char-work { 0%,100% { transform:translateY(0) rotate(-1deg); } 50% { transform:translateY(-4px) rotate(1deg); } }
  @keyframes char-sleep { 0%,100% { transform:translateY(0) rotate(-3deg); } 50% { transform:translateY(1px) rotate(-3deg); } }
  @keyframes char-tap { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-1px); } }
  @keyframes arm-type { 0%,100% { transform:rotate(-8deg); } 50% { transform:rotate(-32deg); } }
  @keyframes arm-tap { 0%,100% { transform:rotate(-8deg); } 50% { transform:rotate(-24deg); } }
  @keyframes mouth-talk { 0%,100% { height:3px; } 50% { height:5px; } }
  @keyframes zzz { 0% { opacity:0; transform:translate(0,0); } 30% { opacity:1; } 100% { opacity:0; transform:translate(6px,-14px); } }
  @keyframes sweat { 0% { opacity:0; transform:translateY(0); } 30% { opacity:1; } 100% { opacity:0; transform:translateY(8px); } }
  @keyframes motion { 0% { opacity:0; transform:translateX(0); } 50% { opacity:1; } 100% { opacity:0; transform:translateX(6px); } }
  @keyframes lamp-glow { 50% { box-shadow:0 0 22px #f5b94288; } }
  @keyframes screen-flicker { 50% { opacity:.85; } }
  @keyframes clock-tick { 50% { transform:rotate(8deg); } }
  @keyframes wait-pulse { 50% { opacity:.5; } }
  @keyframes crate-glide { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:translateX(0); } }

  @media (max-width:900px) { .work-layout { grid-template-columns:1fr; } .desks { grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); } }
  @media (max-width:600px) { .desks { grid-template-columns:1fr; } }
</style>
