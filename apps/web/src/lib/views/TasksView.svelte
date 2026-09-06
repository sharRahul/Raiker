<script lang="ts">
  import WorkMeta from "../components/WorkMeta.svelte";
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ModelReadinessStrip from "../components/ModelReadinessStrip.svelte";
  import ExecutionEnvironmentBadge from "../components/ExecutionEnvironmentBadge.svelte";
  import ModelCapacityBadge from "../components/ModelCapacityBadge.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
  import { createFileDrop } from "../fileDrop.svelte";
  import { api, ApiError } from "../api";
  import { rememberSurfaceModel, surfaceModel, type Surface } from "../surfaceModel.svelte";
  import { takeScheduleRequest } from "../scheduleHandoff";
  import type { ApprovalView, PromptAttachment, TaskView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { AGENT_CADENCES, cadenceLabel } from "../agentCadence";
  import { ACTIVE_TASK_STATES, isActiveTask, taskBadge, taskStatusLabel } from "../statusMaps";
  import { chatProfiles, refreshModels } from "../models.svelte";
  import { blocksSending, openModelSetup, readinessForSelection } from "../modelReadiness.svelte";

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
  let cadence = $state<"now" | "once" | "routine" | "background">("now");
  // Backlog #10 — the composer offered "Daily" and nothing else, so an owner who
  // wanted hourly or weekly had to go to Build's side panel for it, and the four
  // cadences the runtime honours read as one. The chip now names the *shape* of
  // the work and this names the interval, which is the axis they actually vary
  // on. `continuous` is the shortest cadence the scheduler offers, not a loop.
  let routineEvery = $state("daily");
  let titleEl: HTMLInputElement | undefined = $state();
  let scheduledAt = $state("");
  let modelProfile = $state("");
  let model = $state("");
  const attachStore = createAttachmentStore();
  // A file dropped on the task composer rides with the task, exactly as if it
  // had been picked from the attach panel (BUG-252).
  const composerDrop = createFileDrop({
    onFiles: (files) => void attachStore.acceptFiles(files),
    enabled: () => !creating && !attachStore.full,
  });
  const profiles = $derived(chatProfiles());
  // One composer creates both, and the cadence chips say which: a schedule
  // captures its model onto every future run, so it is worth remembering apart
  // from a one-off task.
  const surface = $derived<Surface>(
    cadence === "once" || cadence === "routine" ? "schedule" : "tasks",
  );
  // Whether this composition wants a start time at all. A routine anchors every
  // later run to the slot the owner picked, so "daily" without one means "daily
  // from whenever I happened to press the button" — which is the thing backlog
  // #10 says is not a schedule anybody chose.
  const wantsStartTime = $derived(cadence === "once" || cadence === "routine");
  // Re-reads whenever the cadence chips change which surface is being composed,
  // so switching from Task to Routine offers the routine's own model.
  $effect(() => {
    const active = surface;
    void surfaceModel(active).then((remembered) => {
      if (remembered === null || surface !== active || modelProfile) return;
      modelProfile = remembered.profileId;
      model = remembered.model;
    });
  });
  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);
  const activeProfile = $derived(
    profiles.find((profile) => profile.profile_id === modelProfile && (!model || profile.model === model)) ?? selectedProfile,
  );
  const modelReadiness = $derived(readinessForSelection(activeProfile));
  // BUG-238 — a stale observation never blocks: the server re-checks it
  // before admitting the turn, so the only thing that stops a send is a
  // model problem the owner can actually fix.
  const modelBlocked = $derived(blocksSending(modelReadiness));

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

  // BUG-220 — how many delegated tasks a parked parent is still waiting on.
  // Counted from the list the page already has rather than fetched: the parent
  // and its children are always loaded together, and a second request would
  // make the card's number and the tree below it able to disagree.
  function childCount(task: TaskView): number {
    return (tasks ?? []).filter(
      (child) => child.parent_task_id === task.task_id && isActiveTask(child.status),
    ).length;
  }

  function scheduleLabel(task: TaskView) {
    if (!task.scheduled_at) return "Ready when you run it";
    const when = new Date(task.scheduled_at).toLocaleString();
    if (task.recurrence === "background") return task.status === "running" ? "Background agent working" : "Background agent ready to start";
    // Backlog #10 — a routine used to read as "Scheduled for …" unless it was
    // daily, so an hourly or weekly one looked like a one-shot and its next slot
    // looked like its only one.
    if (task.recurrence) return `${cadenceLabel(task.recurrence)}, next ${when}`;
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

  // Backlog #23 — which working method this task's cycles run under. Named
  // `workMethod` rather than `surface` because `surface` above already means
  // which *model picker* is being composed ("tasks" or "schedule"), and one word
  // meaning two things in one file is how the wrong one gets read.
  //
  // Build's method is a repository it can read, so it needs a project; the
  // control appears only inside one rather than letting the request come back
  // refused.
  let workMethod = $state("chat");
  const buildAvailable = $derived(Boolean(projectId));

  async function createTask() {
    if (!title.trim() || !objective.trim() || modelBlocked || attachStore.uploading || (wantsStartTime && !scheduledAt)) return;
    creating = true; notice = null;
    const attachments = wireAttachments(attachStore.take());
    try {
      await api.createTask({
        title: title.trim(), description: objective.trim(), priority,
        ...(parentTaskId ? { parent_task_id: parentTaskId } : {}),
        ...(wantsStartTime ? { scheduled_at: new Date(scheduledAt).toISOString() } : {}),
        ...(cadence === "routine" ? { recurrence: routineEvery } : cadence === "background" ? { recurrence: "background" } : {}),
        ...(projectId ? { project_id: projectId } : {}),
        ...(workMethod === "build" ? { surface: "build" } : {}),
        ...(modelProfile && model ? { model_profile: modelProfile, model } : {}),
        ...(attachments ? { attachments } : {}),
      });
      title = ""; objective = ""; parentTaskId = ""; priority = "normal"; cadence = "now"; routineEvery = "daily"; scheduledAt = ""; modelProfile = ""; model = ""; workMethod = "chat";
      notice = "Saved to your work queue.";
      attachStore.clear();
      await load();
    } catch (error) {
      if (error instanceof ApiError && error.reasonCode === "model_not_ready") {
        await refreshModels();
        openModelSetup(activeProfile);
        notice = "The selected model is not ready. Your task draft is preserved.";
      } else notice = error instanceof ApiError ? `Could not save task (${error.status}).` : "Could not save task.";
    }
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

  async function runTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    try {
      await api.runTask(task.task_id);
      notice = `Starting “${task.title}”.`;
      await load();
    } catch (error) {
      notice = error instanceof ApiError
        ? `Could not run this task (${error.reasonCode ?? error.status}).`
        : "Could not run this task.";
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
  // The `raiker:task-compose` handoff this used to listen for came from the
  // Workbench composer, which no longer exists: the Workbench is a board over the
  // work that is already running, and planning a task happens in the form on this
  // page. A listener for an event nothing dispatches is a handoff the product
  // claims and never performs, so it is gone with its sender.
  onMount(() => {
    // Chat's `/schedule` asks this surface to open on **Schedule once**. It
    // arranges the form and stops: nothing is created and nothing is scheduled.
    if (takeScheduleRequest()) {
      cadence = "once";
      queueMicrotask(() => titleEl?.focus());
    }
    void refreshModels();
    const timer = window.setInterval(() => void load(), 15_000);
    return () => window.clearInterval(timer);
  });
</script>

<section class="tasks">
  <header>  <GuideLink route="tasks" />
<button type="button" class="btn btn-ghost btn-sm" onclick={load}><Icon name="refresh" size="sm" /> Refresh</button></header>

  <form
    class="card composer"
    class:drop-active={composerDrop.over}
    ondragenter={composerDrop.ondragenter}
    ondragover={composerDrop.ondragover}
    ondragleave={composerDrop.ondragleave}
    ondrop={composerDrop.ondrop}
    onsubmit={(event) => { event.preventDefault(); void createTask(); }}
  >
    <div class="composer-heading"><div><h3>Plan work</h3></div><div class="cadence chip-row" role="group" aria-label="When to run"><button type="button" class="chip" aria-pressed={cadence === "now"} onclick={() => cadence = "now"}>Task</button><button type="button" class="chip" aria-pressed={cadence === "once"} onclick={() => cadence = "once"}>Once</button><button type="button" class="chip" aria-pressed={cadence === "routine"} onclick={() => cadence = "routine"}>Routine</button><button type="button" class="chip" aria-pressed={cadence === "background"} onclick={() => cadence = "background"}>Background</button></div></div>
    <!-- Backlog #23 — the chip row above says *when*; this says *how*. Build's
         method is a repository it can read, so it appears only inside a project. -->
    {#if buildAvailable}
      <div class="chip-row" role="group" aria-label="How to work">
        <button type="button" class="chip" aria-pressed={workMethod === "chat"} onclick={() => workMethod = "chat"}>Chat</button>
        <button type="button" class="chip" aria-pressed={workMethod === "build"} onclick={() => workMethod = "build"}>Build</button>
      </div>
    {/if}
    <label>Title<input class="input" aria-label="Task title" bind:this={titleEl} bind:value={title} required maxlength="240" placeholder={cadence === "background" ? "e.g. Research local AI news" : cadence === "routine" ? "e.g. Review today’s priorities" : "What should Raiker work on?"} /></label>
    <label>Instructions *<textarea class="textarea" aria-label="Instructions" aria-invalid={Boolean(title.trim() && !objective.trim())} aria-describedby={title.trim() && !objective.trim() ? "instructions-error" : undefined} bind:value={objective} required placeholder="Add the outcome, context, or constraints for this work."></textarea></label>
    {#if title.trim() && !objective.trim()}<p id="instructions-error" class="field-error" role="alert">Instructions are required.</p>{/if}
    {#if composerDrop.over}<p class="drop-note" role="status">Drop to attach</p>{/if}
    <ComposerChips store={attachStore} disabled={creating} />
    <ComposerAttachPanel store={attachStore} disabled={creating} idPrefix="task" />
    <div class="fields"><label>Parent work<select class="select" aria-label="Parent work" bind:value={parentTaskId}><option value="">No parent — top-level work</option>{#each tasks ?? [] as task (task.task_id)}<option value={task.task_id}>{task.title}</option>{/each}</select></label><label>Priority<select class="select" aria-label="Priority" bind:value={priority}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>{#if cadence === "routine"}<label>Repeat<select class="select" aria-label="Repeat" bind:value={routineEvery}>{#each AGENT_CADENCES.filter((option) => option.id !== "background") as option (option.id)}<option value={option.id}>{option.label}</option>{/each}</select></label>{/if}{#if wantsStartTime}<label>{cadence === "routine" ? "First run" : "Start time"}<input class="input" aria-label={cadence === "routine" ? "First run" : "Start time"} type="datetime-local" bind:value={scheduledAt} required /></label>{/if}</div>
    <div class="task-model"><span>{cadence === "now" ? "Task model" : "Model for each run"}</span><ModelPicker {profiles} {selectedProfile} bind:profileId={modelProfile} bind:model onchosen={(profileId, chosen) => void rememberSurfaceModel(surface, profileId, chosen)} /><ExecutionEnvironmentBadge /><ModelCapacityBadge tokens={activeProfile?.context_window_tokens} source={activeProfile?.context_window_source} /></div>
    <ModelReadinessStrip readiness={modelReadiness} draftPreserved={Boolean(title.trim() || objective.trim())} />
    <button class="btn btn-primary" disabled={creating || attachStore.uploading || modelBlocked || !title.trim() || !objective.trim() || (wantsStartTime && !scheduledAt)}>{creating ? "Saving…" : attachStore.uploading ? "Uploading…" : cadence === "background" ? "Start background agent" : cadence === "routine" ? "Create routine" : cadence === "once" ? "Schedule task" : "Create task"}</button>
  </form>

  {#if notice}<p class="notice" role="status">{notice}</p>{/if}
  {#if loadError}<PageState state="error" title="Couldn't load tasks" detail={loadError} />
  {:else if tasks === null}<PageState state="loading" title="Loading tasks…" lines={3} />
  {:else}
    <div class="summary"><span><strong>{active.length}</strong> open</span><span><strong>{scheduled.length}</strong> scheduled</span><span><strong>{history.length}</strong> finished</span></div>
    {#if rows.length === 0}<div class="card">
        <EmptyState
          icon="tasks"
          title="No work queued"
          body="Give Raiker work that can continue after you leave."
        >
          {#snippet action()}
            <!-- VIS-12 — the plan form is already on this page, above the empty
                 state. Naming where it is would be worse than putting the
                 cursor in it. -->
            <button type="button" class="btn btn-primary" onclick={() => titleEl?.focus()}>
              Plan your first task
            </button>
          {/snippet}
        </EmptyState>
      </div>
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
                  <span><Icon name="file" size="sm" /> {attachmentLabel(attachment)}</span>
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
                <Icon name="refresh" size="sm" /> Approved — continuing this run now.
              </p>
            {:else if pending.length > 0}
              <p class="blocked" role="status">
                <Icon name="approvals" size="sm" />
                Waiting on {pending.length === 1 ? "a decision" : `${pending.length} decisions`} before this can continue.
                <a href={`#/approvals?session=${encodeURIComponent(task.session_id)}`}>Review {pending.length === 1 ? "it" : "them"}</a>
              </p>
            {:else if task.status === "waiting_for_children"}
              <!-- BUG-220 — the row this replaces said "completed" while a
                   child was still parked. The count is the point: it is what
                   the owner would otherwise have to work out by reading the
                   tree themselves. -->
              <p class="blocked" role="status">
                <Icon name="tasks" size="sm" />
                Its own run finished. Waiting on {childCount(task)} delegated {childCount(task) === 1 ? "task" : "tasks"}.
              </p>
            {:else if task.status === "waiting_for_approval"}
              <!-- BUG-39 — granting the decision starts the continuation on its
                   own, so this button is the recovery path, not the fast one.
                   It is styled and labelled as one: quiet, and stated as what
                   to press when a granted run has not moved. -->
              <p class="blocked" role="status">
                <Icon name="approvals" size="sm" />
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
              <!-- VIS-14 — the same order a thread and a project use: where the
                   work lives, what it is doing, when it last moved. The state
                   badge is above, on the title row, because a task's status is
                   the first thing this card is read for.

                   Backlog #23 — the working method is said only when it is not
                   the default, so the common case stays quiet and a Build child
                   stands out on the board. -->
              <WorkMeta
                project={task.surface === "build" ? "Build" : null}
                detail={scheduleLabel(task)}
                activityAt={task.updated_at}
              />
              <span class="task-actions">
                <!-- C11 — background work used to finish into a status line.
                     Each task now runs its cycles in a conversation of its own,
                     so "what did the overnight run find?" is a thread the owner
                     opens and replies in — and because the next cycle runs in
                     the same conversation, the reply is context that cycle
                     reads rather than a note nobody acts on.

                     Only offered once there is something to read: a link to an
                     empty transcript is a dead end, and a routine that has not
                     run yet has one. -->
                {#if task.thread_session_id && (task.thread_turns ?? 0) > 0}
                  <a class="btn btn-ghost btn-sm thread-link" href={`#/new-chat?session=${task.thread_session_id}`}>
                    <Icon name="chat" size="sm" />
                    Thread · {task.thread_turns}
                  </a>
                {/if}
                {#if ACTIVE_TASK_STATES.includes(task.status)}
                  {#if task.status === "queued" && !task.scheduled_at}
                    <button type="button" class="btn btn-primary btn-sm" onclick={() => runTask(task)} disabled={busyTask === task.task_id}>{busyTask === task.task_id ? "Starting…" : "Run now"}</button>
                  {/if}
                  <button type="button" class="btn btn-danger btn-sm" onclick={() => stopTask(task)} disabled={busyTask === task.task_id}>{busyTask === task.task_id ? "Stopping…" : "Stop"}</button>
                {/if}
              </span>
            </footer>
          </article>
        {/each}
      </section>
    {/if}
    {#if history.length > 0}<section class="history"><h3>Finished work</h3>{#each history as task (task.task_id)}<div class="history-row"><div class="history-main"><span class="history-title">{task.title}</span><p class="outcome">{outcome(task)}</p></div><Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} /><span>{relativeTime(task.updated_at)}</span></div>{/each}</section>{/if}
  {/if}
</section>

<style>
  .tasks{width:100%}.tasks header,.composer-heading,.task-main,footer,.history-row{align-items:flex-start;display:flex;gap:var(--space-3);justify-content:space-between}.tasks header{margin-bottom:var(--space-4)}h3,h4{margin:0}.composer p,.task p{color:var(--text-2);font-size:var(--text-sm);margin:.35rem 0 0}.composer{display:grid;gap:var(--space-3);max-width:64rem}.composer label{color:var(--text-2);display:grid;font-size:var(--text-sm);gap:.35rem}.composer .field-error{color:var(--danger);font-size:var(--text-sm);margin:calc(var(--space-3) * -.5) 0 0}.fields{display:grid;gap:var(--space-3);grid-template-columns:repeat(3,minmax(0,1fr))}.summary{display:flex;gap:var(--space-4);margin:var(--space-4) 0}.summary span{color:var(--text-2);font-size:var(--text-sm)}.summary strong{color:var(--text-1);font-size:var(--text-base)}.work-list,.history{display:grid;gap:var(--space-2);margin-top:var(--space-4)}.task{margin-left:calc(var(--depth) * 1.15rem);max-width:calc(100% - var(--depth) * 1.15rem)}.task-title{display:flex;gap:.5rem}.branch{color:var(--accent);min-width:.8rem}.task h4{font-size:var(--text-base)}.task-attachments{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.7rem}.task-attachments span{align-items:center;background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-sm);color:var(--text-2);display:flex;font-size:var(--text-xs);gap:.3rem;max-width:100%;overflow-wrap:anywhere;padding:.35rem .5rem}.step{color:var(--accent)!important}.continuing{align-items:center;background:var(--accent-soft);border:1px solid var(--accent-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;font-size:var(--text-sm);gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.blocked{align-items:center;background:var(--warn-soft);border:1px solid var(--warn-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;flex-wrap:wrap;font-size:var(--text-sm);gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.recovery{align-items:center;display:flex;flex-wrap:wrap;gap:.35rem;margin-left:auto}.recovery-note{color:var(--text-3);font-size:var(--text-xs)}.progress{background:var(--sunken);border-radius:var(--r-pill);height:6px;margin-top:.7rem;overflow:hidden}.progress div{background:var(--accent);height:100%}footer{align-items:center;color:var(--text-3);font-size:var(--text-xs);margin-top:.8rem}.task-actions{align-items:center;display:flex;flex-wrap:wrap;gap:.4rem}.thread-link{align-items:center;display:inline-flex;gap:.3rem;text-decoration:none}.history-row{align-items:center;border-bottom:1px solid var(--border);padding:.65rem 0}.history-row span:last-child{color:var(--text-3);font-size:var(--text-sm)}.history-main{display:grid;gap:.15rem;min-width:0}.history-title{color:var(--text-1)}.outcome{color:var(--text-2);font-size:var(--text-sm);margin:.4rem 0 0}.history-main .outcome{margin:0}.notice{color:var(--success);margin:var(--space-3) 0}@media(max-width:42rem){.tasks header,.composer-heading{flex-direction:column}.fields{grid-template-columns:1fr}.task{margin-left:0;max-width:none}}
</style>
