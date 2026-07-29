<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import { api, ApiError } from "../api";
  import type { ApprovalView, TaskView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { ACTIVE_TASK_STATES, taskBadge, taskStatusLabel } from "../statusMaps";
  import { chatProfiles, refreshModels } from "../models.svelte";

  let { projectId = null, sessionId = null }: { projectId?: string | null; sessionId?: string | null } = $props();
  let tasks = $state<TaskView[] | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let creating = $state(false);
  let busyTask = $state<string | null>(null);
  let title = $state("");
  let objective = $state("");
  let priority = $state("normal");
  let parentTaskId = $state("");
  let cadence = $state<"now" | "once" | "daily" | "background">("now");
  let scheduledAt = $state("");
  let modelProfile = $state("");
  let model = $state("");
  const profiles = $derived(chatProfiles());
  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);

  // Reverse approval links. A task that is blocked should say so where you are
  // looking at the task, rather than making you go and find the queue. Matching
  // is by session: an approval raised inside a task's session is what is holding
  // that task up. A failed read leaves the task list intact — the pointer is
  // supplementary, and the decision queue is still the source of truth.
  let approvals = $state<ApprovalView[]>([]);

  function blockedBy(task: TaskView): ApprovalView[] {
    if (task.session_id === "") return [];
    return approvals.filter((approval) => approval.session_id === task.session_id);
  }

  // Unfinished work, including a run parked on a decision: it has not failed and
  // it has not finished, so it belongs in the open list where it can be reviewed
  // or stopped.
  const active = $derived((tasks ?? []).filter((task) => ACTIVE_TASK_STATES.includes(task.status)));
  const scheduled = $derived(active.filter((task) => task.scheduled_at));
  const history = $derived((tasks ?? []).filter((task) => !ACTIVE_TASK_STATES.includes(task.status)));
  const rows = $derived(flatten(active));

  // A finished or blocked run always states why. The backend refuses to record a
  // terminal task without a reason (BUG-09); this is the line that shows it, so
  // "failed" is never the whole story the owner gets.
  function outcome(task: TaskView): string | null {
    if (["queued", "running", "paused"].includes(task.status)) return null;
    return task.summary?.trim() || "No reason was recorded for this outcome.";
  }

  function flatten(items: TaskView[]): Array<{ task: TaskView; depth: number }> {
    const ids = new Set(items.map((task) => task.task_id));
    const children = new Map<string, TaskView[]>();
    for (const task of items) {
      if (task.parent_task_id && ids.has(task.parent_task_id)) {
        children.set(task.parent_task_id, [...(children.get(task.parent_task_id) ?? []), task]);
      }
    }
    const result: Array<{ task: TaskView; depth: number }> = [];
    const visit = (task: TaskView, depth: number) => {
      result.push({ task, depth });
      for (const child of children.get(task.task_id) ?? []) visit(child, depth + 1);
    };
    for (const task of items) if (!task.parent_task_id || !ids.has(task.parent_task_id)) visit(task, 0);
    return result;
  }

  function scheduleLabel(task: TaskView) {
    if (!task.scheduled_at) return "Ready when you run it";
    const when = new Date(task.scheduled_at).toLocaleString();
    if (task.recurrence === "daily") return `Every day, next run ${when}`;
    if (task.recurrence === "background") return task.status === "running" ? "Background agent working" : "Background agent ready to start";
    return `Scheduled for ${when}`;
  }

  async function load() {
    try {
      loadError = null;
      tasks = await api.tasks({
        ...(projectId ? { project_id: projectId } : {}),
        ...(sessionId ? { session_id: sessionId } : {}),
      });
    }
    catch (error) { tasks = null; loadError = error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable"; }
    try { approvals = await api.approvals(); } catch { approvals = []; }
  }

  async function createTask() {
    if (!title.trim() || !objective.trim() || ((cadence === "once" || cadence === "daily") && !scheduledAt)) return;
    creating = true; notice = null;
    try {
      await api.createTask({
        title: title.trim(), description: objective.trim(), priority,
        ...(parentTaskId ? { parent_task_id: parentTaskId } : {}),
        ...((cadence === "once" || cadence === "daily") ? { scheduled_at: new Date(scheduledAt).toISOString() } : {}),
        ...(cadence === "daily" ? { recurrence: "daily" } : cadence === "background" ? { recurrence: "background" } : {}),
        ...(projectId ? { project_id: projectId } : {}),
        ...(cadence === "now" && modelProfile && model ? { model_profile: modelProfile, model } : {}),
      });
      title = ""; objective = ""; parentTaskId = ""; priority = "normal"; cadence = "now"; scheduledAt = ""; modelProfile = ""; model = "";
      notice = "Saved to your work queue.";
      await load();
    } catch (error) { notice = error instanceof ApiError ? `Could not save task (${error.status}).` : "Could not save task."; }
    finally { creating = false; }
  }

  async function stopTask(task: TaskView) {
    busyTask = task.task_id; notice = null;
    try {
      await api.interrupt({ session_id: task.session_id, task_id: task.task_id, action_type: "cancel", reason: "user stopped this task (web UI)" });
      notice = `Requested a safe-boundary stop for “${task.title}”.`; await load();
    } catch { notice = "Could not request the stop."; }
    finally { busyTask = null; }
  }

  $effect(() => { void projectId; void sessionId; void load(); });

  // Tasks run outside this page: a queued run is claimed, works, and finishes
  // while the list sits still. Without this the page kept showing "queued" long
  // after the run had ended (BUG-09), and only a manual Refresh disagreed.
  onMount(() => {
    void refreshModels();
    const onCompose = (event: Event) => {
      const detail = (event as CustomEvent<{ text: string; cadence?: "now" | "once"; profileId?: string | null; model?: string | null }>).detail;
      if (!detail?.text.trim()) return;
      objective = detail.text;
      title = detail.text.slice(0, 80);
      cadence = detail.cadence ?? "now";
      modelProfile = detail.profileId ?? "";
      model = detail.model ?? "";
    };
    window.addEventListener("raiker:task-compose", onCompose);
    const timer = window.setInterval(() => void load(), 15_000);
    return () => { window.clearInterval(timer); window.removeEventListener("raiker:task-compose", onCompose); };
  });
</script>

<section class="tasks">
  <header><p class="page-lead">Create a task, nest it under another task, schedule a routine, or start a persistent background researcher. Every run remains governed and can be stopped at a safe boundary.</p><button type="button" class="btn btn-ghost btn-sm" onclick={load}><Icon name="refresh" size={15} /> Refresh</button></header>

  <form class="card composer" onsubmit={(event) => { event.preventDefault(); void createTask(); }}>
    <div class="composer-heading"><div><h3>Plan work</h3><p>A routine is a recurring task; a child task becomes a subtask or subroutine. A background agent runs asynchronously until its work is complete or you stop it.</p></div><div class="cadence chip-row" role="group" aria-label="When to run"><button type="button" class="chip" aria-pressed={cadence === "now"} onclick={() => cadence = "now"}>Task</button><button type="button" class="chip" aria-pressed={cadence === "once"} onclick={() => cadence = "once"}>Schedule once</button><button type="button" class="chip" aria-pressed={cadence === "daily"} onclick={() => cadence = "daily"}>Daily routine</button><button type="button" class="chip" aria-pressed={cadence === "background"} onclick={() => cadence = "background"}>Background agent</button></div></div>
    <label>Title<input class="input" aria-label="Task title" bind:value={title} required maxlength="240" placeholder={cadence === "background" ? "e.g. Research local AI news" : cadence === "daily" ? "e.g. Review today’s priorities" : "What should Raiker work on?"} /></label>
    <label>Instructions *<textarea class="textarea" aria-label="Instructions" aria-invalid={Boolean(title.trim() && !objective.trim())} aria-describedby={title.trim() && !objective.trim() ? "instructions-error" : undefined} bind:value={objective} required placeholder="Add the outcome, context, or constraints for this work."></textarea></label>
    {#if title.trim() && !objective.trim()}<p id="instructions-error" class="field-error" role="alert">Instructions are required.</p>{/if}
    <div class="fields"><label>Parent work<select class="select" aria-label="Parent work" bind:value={parentTaskId}><option value="">No parent — top-level work</option>{#each tasks ?? [] as task (task.task_id)}<option value={task.task_id}>{task.title}</option>{/each}</select></label><label>Priority<select class="select" aria-label="Priority" bind:value={priority}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>{#if cadence === "once" || cadence === "daily"}<label>Start time<input class="input" aria-label="Start time" type="datetime-local" bind:value={scheduledAt} required /></label>{/if}</div>
    {#if cadence === "now"}
      <div class="task-model"><span>Task model</span><ModelPicker {profiles} {selectedProfile} bind:profileId={modelProfile} bind:model /></div>
    {:else}
      <p class="schedule-model-note">Uses the global model active when this run begins.</p>
    {/if}
    <button class="btn btn-primary" disabled={creating || !title.trim() || !objective.trim() || ((cadence === "once" || cadence === "daily") && !scheduledAt)}>{creating ? "Saving…" : cadence === "background" ? "Start background agent" : cadence === "daily" ? "Create daily routine" : cadence === "once" ? "Schedule task" : "Create task"}</button>
  </form>

  {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  {#if loadError}<PageState state="error" title="Couldn't load tasks" detail={loadError} />
  {:else if tasks === null}<PageState state="loading" title="Loading tasks…" />
  {:else}
    <div class="summary"><span><strong>{active.length}</strong> open</span><span><strong>{scheduled.length}</strong> scheduled</span><span><strong>{history.length}</strong> finished</span></div>
    {#if rows.length === 0}<div class="card"><EmptyState icon="tasks" title="No work queued" body="Create a task for immediate work, or schedule a routine for later." /></div>
    {:else}<section class="work-list" aria-labelledby="open-work"><h3 id="open-work">Open work</h3>{#each rows as row (row.task.task_id)}<article class="card task" style={`--depth:${row.depth}`}><div class="task-main"><div class="task-title"><span class="branch" aria-hidden="true">{row.depth > 0 ? "↳" : ""}</span><div><h4>{row.task.title}</h4><p>{row.task.objective || "No additional instructions."}</p></div></div><Badge variant={taskBadge(row.task.status)} label={taskStatusLabel(row.task.status)} /></div>{#if blockedBy(row.task).length > 0}<p class="blocked" role="status"><Icon name="approvals" size={14} /> Waiting on {blockedBy(row.task).length === 1 ? "a decision" : `${blockedBy(row.task).length} decisions`} before this can continue. <a href={`#/approvals?session=${encodeURIComponent(row.task.session_id)}`}>Review {blockedBy(row.task).length === 1 ? "it" : "them"}</a></p>{:else if outcome(row.task)}<p class="outcome" role="status">{outcome(row.task)}</p>{/if}{#if row.task.current_step}<p class="step">Now: {row.task.current_step}</p>{/if}{#if row.task.progress_percent !== null}<div class="progress" role="progressbar" aria-valuenow={row.task.progress_percent} aria-valuemin="0" aria-valuemax="100"><div style={`width:${row.task.progress_percent}%`}></div></div>{/if}<footer><span title={row.task.scheduled_at ?? row.task.updated_at}>{scheduleLabel(row.task)} · updated {relativeTime(row.task.updated_at)}</span>{#if ACTIVE_TASK_STATES.includes(row.task.status)}<button type="button" class="btn btn-danger btn-sm" onclick={() => stopTask(row.task)} disabled={busyTask === row.task.task_id}>{busyTask === row.task.task_id ? "Stopping…" : "Stop"}</button>{/if}</footer></article>{/each}</section>{/if}
    {#if history.length > 0}<section class="history"><h3>Finished work</h3>{#each history as task (task.task_id)}<div class="history-row"><div class="history-main"><span class="history-title">{task.title}</span><p class="outcome">{outcome(task)}</p></div><Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} /><span>{relativeTime(task.updated_at)}</span></div>{/each}</section>{/if}
  {/if}
</section>

<style>
  .tasks{max-width:64rem}.tasks header,.composer-heading,.task-main,footer,.history-row{align-items:flex-start;display:flex;gap:var(--space-3);justify-content:space-between}.tasks header{margin-bottom:var(--space-4)}h3,h4{margin:0}.tasks header .page-lead{margin:0;max-width:60ch}.composer p,.task p{color:var(--text-2);font-size:.85rem;margin:.35rem 0 0}.composer{display:grid;gap:var(--space-3)}.composer label{color:var(--text-2);display:grid;font-size:.8rem;gap:.35rem}.composer .field-error{color:var(--danger);font-size:.8rem;margin:calc(var(--space-3) * -.5) 0 0}.fields{display:grid;gap:var(--space-3);grid-template-columns:repeat(3,minmax(0,1fr))}.summary{display:flex;gap:var(--space-4);margin:var(--space-4) 0}.summary span{color:var(--text-2);font-size:.85rem}.summary strong{color:var(--text-1);font-size:1.1rem}.work-list,.history{display:grid;gap:var(--space-2);margin-top:var(--space-4)}.task{margin-left:calc(var(--depth) * 1.15rem);max-width:calc(100% - var(--depth) * 1.15rem)}.task-title{display:flex;gap:.5rem}.branch{color:var(--accent);min-width:.8rem}.task h4{font-size:.96rem}.step{color:var(--accent)!important}.blocked{align-items:center;background:var(--warn-soft);border:1px solid var(--warn-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;flex-wrap:wrap;font-size:.8rem;gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.progress{background:var(--sunken);border-radius:var(--r-pill);height:6px;margin-top:.7rem;overflow:hidden}.progress div{background:var(--accent);height:100%}footer{align-items:center;color:var(--text-3);font-size:.76rem;margin-top:.8rem}.history-row{align-items:center;border-bottom:1px solid var(--border);padding:.65rem 0}.history-row span:last-child{color:var(--text-3);font-size:.8rem}.history-main{display:grid;gap:.15rem;min-width:0}.history-title{color:var(--text-1)}.outcome{color:var(--text-2);font-size:.82rem;margin:.4rem 0 0}.history-main .outcome{margin:0}.notice{color:var(--success);margin:var(--space-3) 0}@media(max-width:42rem){.tasks header,.composer-heading{flex-direction:column}.fields{grid-template-columns:1fr}.task{margin-left:0;max-width:none}}
</style>
