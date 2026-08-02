<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ExecutionEnvironmentBadge from "../components/ExecutionEnvironmentBadge.svelte";
  import ModelCapacityBadge from "../components/ModelCapacityBadge.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
  import { api, ApiError } from "../api";
  import type { ApprovalView, PromptAttachment, TaskView } from "../apiTypes";
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
  const attachStore = createAttachmentStore();
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
    if (["queued", "running", "continuing", "paused"].includes(task.status)) return null;
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

  function wireAttachments(items: ComposerAttachment[]): PromptAttachment[] | undefined {
    const attachments = items.map((item) => item.kind === "image"
      ? { type: "image" as const, attachment_id: item.attachmentId ?? "" }
      : item.kind === "document"
        ? { type: "document" as const, attachment_id: item.attachmentId ?? "" }
        : { type: "path" as const, path: item.path ?? "" });
    return attachments.length ? attachments : undefined;
  }

  function attachmentLabel(attachment: PromptAttachment): string {
    return attachment.type === "path"
      ? attachment.path
      : `${attachment.type === "image" ? "Image" : "Document"} ${attachment.attachment_id}`;
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
    if (!title.trim() || !objective.trim() || attachStore.uploading || ((cadence === "once" || cadence === "daily") && !scheduledAt)) return;
    creating = true; notice = null;
    const attachments = wireAttachments(attachStore.take());
    try {
      await api.createTask({
        title: title.trim(), description: objective.trim(), priority,
        ...(parentTaskId ? { parent_task_id: parentTaskId } : {}),
        ...((cadence === "once" || cadence === "daily") ? { scheduled_at: new Date(scheduledAt).toISOString() } : {}),
        ...(cadence === "daily" ? { recurrence: "daily" } : cadence === "background" ? { recurrence: "background" } : {}),
        ...(projectId ? { project_id: projectId } : {}),
        ...(modelProfile && model ? { model_profile: modelProfile, model } : {}),
        ...(attachments ? { attachments } : {}),
      });
      title = ""; objective = ""; parentTaskId = ""; priority = "normal"; cadence = "now"; scheduledAt = ""; modelProfile = ""; model = "";
      notice = "Saved to your work queue.";
      attachStore.clear();
      await load();
    } catch (error) { notice = error instanceof ApiError ? `Could not save task (${error.status}).` : "Could not save task."; }
    finally { creating = false; }
  }

  // BUG-25/BUG-39 — the owner's retry. Granting the approval now signals the
  // host directly, so a parked scheduled run starts continuing immediately and
  // this is purely the recovery path: what to press when that could not proceed
  // (another tab claimed it, the host was down when the decision landed, the
  // continuation threw). It is the same governed path, so pressing it can never
  // continue something the automatic pass would have refused, and it never
  // re-runs a turn that already ran.
  async function resumeTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    try {
      const result = await api.resumeTask(task.task_id);
      notice = result.ok
        ? `Continuing “${task.title}”.`
        : result.reason_code === "no_resolved_approval"
          ? "No decision has been recorded yet, so there is nothing to continue."
          : `Could not continue this run (${result.reason_code ?? "unknown reason"}).`;
      await load();
    } catch (error) {
      notice = error instanceof ApiError
        ? `Could not continue this run (${error.reasonCode ?? error.status}).`
        : "Could not continue this run.";
    } finally {
      busyTask = null;
    }
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
      const detail = (event as CustomEvent<{
        text: string;
        cadence?: "now" | "once";
        scheduledAt?: string;
        profileId?: string | null;
        model?: string | null;
        attachments?: ComposerAttachment[];
      }>).detail;
      if (!detail?.text.trim()) return;
      objective = detail.text;
      title = detail.text.slice(0, 80);
      cadence = detail.cadence ?? "now";
      // The Workbench schedule composer picks the time; carrying it through
      // means the handoff arrives complete rather than as a half-filled form
      // whose required field the owner has to notice.
      scheduledAt = detail.scheduledAt ?? "";
      modelProfile = detail.profileId ?? "";
      model = detail.model ?? "";
      if (detail.attachments?.length) attachStore.set([...detail.attachments]);
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
    <ComposerChips store={attachStore} disabled={creating} />
    <ComposerAttachPanel store={attachStore} disabled={creating} idPrefix="task" />
    <div class="fields"><label>Parent work<select class="select" aria-label="Parent work" bind:value={parentTaskId}><option value="">No parent — top-level work</option>{#each tasks ?? [] as task (task.task_id)}<option value={task.task_id}>{task.title}</option>{/each}</select></label><label>Priority<select class="select" aria-label="Priority" bind:value={priority}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>{#if cadence === "once" || cadence === "daily"}<label>Start time<input class="input" aria-label="Start time" type="datetime-local" bind:value={scheduledAt} required /></label>{/if}</div>
    <div class="task-model"><span>{cadence === "now" ? "Task model" : "Model for each run"}</span><ModelPicker {profiles} {selectedProfile} bind:profileId={modelProfile} bind:model /><ExecutionEnvironmentBadge /><ModelCapacityBadge tokens={(profiles.find((profile) => profile.profile_id === modelProfile && (!model || profile.model === model)) ?? selectedProfile)?.context_window_tokens} source={(profiles.find((profile) => profile.profile_id === modelProfile && (!model || profile.model === model)) ?? selectedProfile)?.context_window_source} /></div>
    <button class="btn btn-primary" disabled={creating || attachStore.uploading || !title.trim() || !objective.trim() || ((cadence === "once" || cadence === "daily") && !scheduledAt)}>{creating ? "Saving…" : attachStore.uploading ? "Uploading…" : cadence === "background" ? "Start background agent" : cadence === "daily" ? "Create daily routine" : cadence === "once" ? "Schedule task" : "Create task"}</button>
  </form>

  {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  {#if loadError}<PageState state="error" title="Couldn't load tasks" detail={loadError} />
  {:else if tasks === null}<PageState state="loading" title="Loading tasks…" lines={3} />
  {:else}
    <div class="summary"><span><strong>{active.length}</strong> open</span><span><strong>{scheduled.length}</strong> scheduled</span><span><strong>{history.length}</strong> finished</span></div>
    {#if rows.length === 0}<div class="card"><EmptyState icon="tasks" title="No work queued" body="Create a task for immediate work, or schedule a routine for later." /></div>
    {:else}
      <section class="work-list" aria-labelledby="open-work">
        <h3 id="open-work">Open work</h3>
        {#each rows as row (row.task.task_id)}
          {@const task = row.task}
          {@const pending = blockedBy(task)}
          <article class="card task" style={`--depth:${row.depth}`}>
            <div class="task-main">
              <div class="task-title">
                <span class="branch" aria-hidden="true">{row.depth > 0 ? "↳" : ""}</span>
                <div><h4>{task.title}</h4><p>{task.objective || "No additional instructions."}</p></div>
              </div>
              <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
            </div>
            {#if (task.attachments ?? []).length > 0}
              <div class="task-attachments" aria-label="Files attached to this task">
                {#each task.attachments ?? [] as attachment}
                  <span><Icon name="file" size={14} /> {attachmentLabel(attachment)}</span>
                {/each}
              </div>
            {/if}

            <!-- BUG-25 — the whole life of an approval, on the card that owns
                 it. Waiting names the decision and links to it; continuing says
                 the granted decision is being replayed right now; a parked run
                 whose automatic continuation could not proceed states why and
                 offers the retry, so a granted approval is never a dead end. -->
            {#if task.status === "continuing"}
              <p class="continuing" role="status">
                <Icon name="refresh" size={14} /> Approved — continuing this run now.
              </p>
            {:else if pending.length > 0}
              <p class="blocked" role="status">
                <Icon name="approvals" size={14} />
                Waiting on {pending.length === 1 ? "a decision" : `${pending.length} decisions`} before this can continue.
                <a href={`#/approvals?session=${encodeURIComponent(task.session_id)}`}>Review {pending.length === 1 ? "it" : "them"}</a>
              </p>
            {:else if task.status === "waiting_for_approval"}
              <!-- BUG-39 — granting the decision starts the continuation on its
                   own, so this button is the recovery path, not the fast one.
                   It is styled and labelled as one: quiet, and stated as what
                   to press when a granted run has not moved. -->
              <p class="blocked" role="status">
                <Icon name="approvals" size={14} />
                {outcome(task) ?? "This run is waiting for your approval to continue."}
                <span class="recovery">
                  <span class="recovery-note">Approving continues this run automatically.</span>
                  <button type="button" class="btn btn-ghost btn-sm" onclick={() => resumeTask(task)} disabled={busyTask === task.task_id}>
                    {busyTask === task.task_id ? "Continuing…" : "Continue now"}
                  </button>
                </span>
              </p>
            {:else if outcome(task)}
              <p class="outcome" role="status">{outcome(task)}</p>
            {/if}

            {#if task.current_step}<p class="step">Now: {task.current_step}</p>{/if}
            {#if task.progress_percent !== null}
              <div class="progress" role="progressbar" aria-valuenow={task.progress_percent} aria-valuemin="0" aria-valuemax="100"><div style={`width:${task.progress_percent}%`}></div></div>
            {/if}
            <footer>
              <span title={task.scheduled_at ?? task.updated_at}>{scheduleLabel(task)} · updated {relativeTime(task.updated_at)}</span>
              {#if ACTIVE_TASK_STATES.includes(task.status)}
                <button type="button" class="btn btn-danger btn-sm" onclick={() => stopTask(task)} disabled={busyTask === task.task_id}>{busyTask === task.task_id ? "Stopping…" : "Stop"}</button>
              {/if}
            </footer>
          </article>
        {/each}
      </section>
    {/if}
    {#if history.length > 0}<section class="history"><h3>Finished work</h3>{#each history as task (task.task_id)}<div class="history-row"><div class="history-main"><span class="history-title">{task.title}</span><p class="outcome">{outcome(task)}</p></div><Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} /><span>{relativeTime(task.updated_at)}</span></div>{/each}</section>{/if}
  {/if}
</section>

<style>
  .tasks{max-width:64rem}.tasks header,.composer-heading,.task-main,footer,.history-row{align-items:flex-start;display:flex;gap:var(--space-3);justify-content:space-between}.tasks header{margin-bottom:var(--space-4)}h3,h4{margin:0}.tasks header .page-lead{margin:0;max-width:60ch}.composer p,.task p{color:var(--text-2);font-size:.85rem;margin:.35rem 0 0}.composer{display:grid;gap:var(--space-3)}.composer label{color:var(--text-2);display:grid;font-size:.8rem;gap:.35rem}.composer .field-error{color:var(--danger);font-size:.8rem;margin:calc(var(--space-3) * -.5) 0 0}.fields{display:grid;gap:var(--space-3);grid-template-columns:repeat(3,minmax(0,1fr))}.summary{display:flex;gap:var(--space-4);margin:var(--space-4) 0}.summary span{color:var(--text-2);font-size:.85rem}.summary strong{color:var(--text-1);font-size:1.1rem}.work-list,.history{display:grid;gap:var(--space-2);margin-top:var(--space-4)}.task{margin-left:calc(var(--depth) * 1.15rem);max-width:calc(100% - var(--depth) * 1.15rem)}.task-title{display:flex;gap:.5rem}.branch{color:var(--accent);min-width:.8rem}.task h4{font-size:.96rem}.task-attachments{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.7rem}.task-attachments span{align-items:center;background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-sm);color:var(--text-2);display:flex;font-size:.75rem;gap:.3rem;max-width:100%;overflow-wrap:anywhere;padding:.35rem .5rem}.step{color:var(--accent)!important}.continuing{align-items:center;background:var(--accent-soft);border:1px solid var(--accent-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;font-size:.8rem;gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.blocked{align-items:center;background:var(--warn-soft);border:1px solid var(--warn-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;flex-wrap:wrap;font-size:.8rem;gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.recovery{align-items:center;display:flex;flex-wrap:wrap;gap:.35rem;margin-left:auto}.recovery-note{color:var(--text-3);font-size:.74rem}.progress{background:var(--sunken);border-radius:var(--r-pill);height:6px;margin-top:.7rem;overflow:hidden}.progress div{background:var(--accent);height:100%}footer{align-items:center;color:var(--text-3);font-size:.76rem;margin-top:.8rem}.history-row{align-items:center;border-bottom:1px solid var(--border);padding:.65rem 0}.history-row span:last-child{color:var(--text-3);font-size:.8rem}.history-main{display:grid;gap:.15rem;min-width:0}.history-title{color:var(--text-1)}.outcome{color:var(--text-2);font-size:.82rem;margin:.4rem 0 0}.history-main .outcome{margin:0}.notice{color:var(--success);margin:var(--space-3) 0}@media(max-width:42rem){.tasks header,.composer-heading{flex-direction:column}.fields{grid-template-columns:1fr}.task{margin-left:0;max-width:none}}
</style>
