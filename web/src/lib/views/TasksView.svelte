<script lang="ts">
  import WorkMeta from "../components/WorkMeta.svelte";
  import { pickableProjects } from "../projectLifecycle";
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import ModelReadinessStrip from "../components/ModelReadinessStrip.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import Composer from "../components/Composer.svelte";
  import ComposerActionMenu from "../components/ComposerActionMenu.svelte";
  import ComposerContext from "../components/ComposerContext.svelte";
  import { composerMenu } from "../composerCapabilities";
  import { readReadiness, refreshReadCapabilities } from "../readCapabilities.svelte";
  import { setWorkProject, workProject } from "../workProject.svelte";
  import {
    deriveTitle,
    primaryAction,
    cadenceFor,
    nextRuns,
    runModeFor,
    scheduleSummary,
    scheduleZone,
    scheduleZoneName,
    MISSED_RUN_POLICIES,
    type MissedRunPolicy,
    TASK_RUN_MODES,
    TASK_TIMINGS,
    timingFor,
    type TaskRunMode,
    type TaskTiming,
    type TaskCadence,
  } from "../taskComposer";
  import GuideLink from "../components/GuideLink.svelte";
  import TaskHistory from "../components/TaskHistory.svelte";
  import { taskDetailHref } from "../taskHistory";
  import { createAttachmentStore, type ComposerAttachment } from "../composerAttachments.svelte";
  import { createFileDrop } from "../fileDrop.svelte";
  import { api, ApiError } from "../api";
  import { resumeRun, runAgain, startRunNow, stopRun } from "../taskLifecycle";
  import { taskActionLabel, taskActions, taskPhase, taskPhaseLabel, type TaskAction } from "../taskPhase";
  import { forgetSurfaceModel, rememberSurfaceModel, surfaceModel, type Surface } from "../surfaceModel.svelte";
  import { takeScheduleRequest } from "../scheduleHandoff";
  import type {
    ApprovalView,
    CapabilityGate,
    ExecutionEnvironment,
    ProjectsList,
    PromptAttachment,
    TaskDetailView,
    TaskView,
  } from "../apiTypes";
  import { relativeTime } from "../format";
  import { AGENT_CADENCES, cadenceLabel } from "../agentCadence";
  import { ACTIVE_TASK_STATES, isActiveTask, taskBadge, taskStatusLabel } from "../statusMaps";
  import { chatProfiles, refreshModels, modelCatalogues, modelsKnown } from "../models.svelte";
  import { catalogueChoices } from "../modelCatalogue";
  import { blocksSending, openModelSetup, readinessForSelection } from "../modelReadiness.svelte";

  let {
    projectId = null,
    sessionId = null,
    /** The owner's projects, so the composer can name and change the boundary. */
    projects = null,
    /**
     * BUG-299 — the task this address is for. Tasks is still the board; with a
     * task named it opens that task's attempt history above it, so the link
     * Home and Build now carry lands somewhere rather than on a list the owner
     * has to search.
     */
    taskId = null,
  }: {
    projectId?: string | null;
    sessionId?: string | null;
    projects?: ProjectsList | null;
    taskId?: string | null;
  } = $props();
  let tasks = $state<TaskView[] | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  // BUG-299 — where to look when the runtime could not say what happened. Held
  // beside the notice rather than inside it, so the sentence stays a sentence
  // and the remedy stays a link.
  let noticeHref = $state<string | null>(null);
  let creating = $state(false);
  let busyTask = $state<string | null>(null);
  /**
   * COMPOSER-10 — one instruction, and a title derived from it.
   *
   * The form asked for a Title *and* Instructions, both required, at the top of
   * a card of eight controls. Asking Raiker to do something in Chat takes one
   * field; asking it to do the same thing later took ten, which teaches an
   * owner that scheduling is a more administrative kind of act than asking. It
   * is not: a scheduled cycle is one governed turn, the same as a typed prompt.
   *
   * So the title is derived from the instruction and shown in the details,
   * where the owner can override it when the derived one is not what they would
   * have called it. `titleOverride` is empty until they do.
   */
  let titleOverride = $state("");
  let objective = $state("");
  const title = $derived(titleOverride.trim() || deriveTitle(objective));
  let priority = $state("normal");
  let parentTaskId = $state("");
  // REM-TASK-01 — two questions, not one row of four chips. `cadence` is what
  // the runtime is asked for and is derived from both, so the four shapes it
  // accepts are unchanged and no combination it does not have can be composed.
  let timing = $state<TaskTiming>("now");
  let runMode = $state<TaskRunMode>("single");
  const cadence = $derived(cadenceFor(timing, runMode));
  /** COMPOSER-10 — the timing details, opened only when asked for. */
  let detailsOpen = $state(false);
  let composerGates = $state<CapabilityGate[]>([]);
  // Backlog #10 — the composer offered "Daily" and nothing else, so an owner who
  // wanted hourly or weekly had to go to Build's side panel for it, and the four
  // cadences the runtime honours read as one. The chip now names the *shape* of
  // the work and this names the interval, which is the axis they actually vary
  // on. `continuous` is the shortest cadence the scheduler offers, not a loop.
  let routineEvery = $state("daily");
  let instructionEl: HTMLTextAreaElement | undefined = $state();
  let scheduledAt = $state("");
  /**
   * UX-TASK-02 — a routine's end and what it does about a slot Raiker slept
   * through. Both are stored with the task and honoured by the scheduler; the
   * defaults are the behaviour every routine had before they were choices.
   */
  let endsOn = $state("");
  let missedRuns = $state<MissedRunPolicy>("run_once");
  /**
   * UX-TASK-06 — hierarchy is there when asked for. Most work is not part of
   * other work, so the parent picker waits behind one control rather than
   * sitting in every composition as a field to read past.
   */
  let partOfOther = $state(false);
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
  /**
   * REM-TASK-01 — the runs this schedule would actually produce.
   *
   * A cadence and a first run are two abstractions; three timestamps are the
   * thing the owner is choosing. It is computed the way the scheduler computes
   * it, elapsed slots and all, so the preview cannot promise a run the runtime
   * would not take.
   */
  const runUntil = $derived(
    cadence === "routine" && endsOn ? new Date(`${endsOn}T23:59:59`).toISOString() : "",
  );
  const upcoming = $derived(
    nextRuns({
      cadence,
      every: routineEvery,
      startAt: scheduledAt,
      count: cadence === "routine" ? 3 : 1,
      ...(runUntil ? { until: runUntil } : {}),
    }),
  );

  /** A routine whose end comes before its first slot has nothing to run. */
  const endsBeforeFirst = $derived(
    cadence === "routine" && Boolean(scheduledAt) && Boolean(runUntil) && upcoming.length === 0,
  );

  /** The timing, in one line, whether or not the details are open. */
  const schedule = $derived(
    scheduleSummary({
      cadence,
      every: routineEvery,
      everyLabel: cadenceLabel(routineEvery),
      startAt: scheduledAt,
    }),
  );

  /** COMPOSER-10 — the same two menus every other Work composer carries. */
  const readiness = $derived(readReadiness());
  const HANDLED = new Set([
    "attach-file",
    "set-project",
    "web-search",
    "web-read",
    "web-extract",
    "weather",
    "use-mcp",
    "use-connector",
  ]);
  const addItems = $derived(composerMenu("add", "tasks", composerGates, HANDLED, readiness));
  const toolItems = $derived(composerMenu("tools", "tasks", composerGates, HANDLED, readiness));

  /** Where a Tools entry goes. Tasks invokes none of them itself: the model
   *  reaches for one mid-run and the gate judges it then, so the honest thing
   *  this menu can do is name the capability and open where it is governed. */
  const TOOL_ROUTES: Record<string, string> = {
    "web-search": "#/capabilities",
    "web-read": "#/capabilities",
    "web-extract": "#/capabilities",
    weather: "#/settings?tab=general",
    "use-mcp": "#/extensions?tab=mcp",
    "use-connector": "#/extensions?tab=connectors",
  };

  let attachOpen = $state(false);
  let projectPickerOpen = $state(false);

  function runComposerAction(id: string) {
    if (id === "attach-file") {
      attachOpen = true;
      return;
    }
    if (id === "set-project") {
      projectPickerOpen = !projectPickerOpen;
      return;
    }
    const route = TOOL_ROUTES[id];
    if (route !== undefined) window.location.hash = route;
  }

  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);
  const activeProfile = $derived(
    profiles.find((profile) => profile.profile_id === modelProfile && (!model || profile.model === model)) ?? selectedProfile,
  );
  const modelReadiness = $derived(readinessForSelection(activeProfile, catalogueChoices(profiles, modelCatalogues()).length));
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
  // A settled child of open work is listed under its parent, with the rest of
  // that parent's delegated work, rather than a second time down here.
  const openIds = $derived(new Set(active.map((task) => task.task_id)));
  const history = $derived(
    (tasks ?? []).filter(
      (task) =>
        !ACTIVE_TASK_STATES.includes(task.status) &&
        !(task.parent_task_id && openIds.has(task.parent_task_id)),
    ),
  );
  /**
   * UX-TASK-06 — delegated work folds under the task that delegated it. A
   * parent says how much of it is done; its children are one press away rather
   * than a second tree an owner has to read past to find their own work.
   */
  let expanded = $state<string[]>([]);
  const rows = $derived(flatten(active, expanded, tasks ?? []));

  /** A parent's delegated work: how much there is, and how much has settled. */
  function delegated(task: TaskView): { total: number; settled: number } {
    const children = (tasks ?? []).filter((child) => child.parent_task_id === task.task_id);
    return {
      total: children.length,
      settled: children.filter((child) =>
        ["completed", "failed", "stopped"].includes(taskPhase(child)),
      ).length,
    };
  }

  function toggleDelegated(taskId: string) {
    expanded = expanded.includes(taskId)
      ? expanded.filter((id) => id !== taskId)
      : [...expanded, taskId];
  }

  /**
   * UX-TASK-05 — the badge says the phase where the status alone does not. A
   * `queued` row is three different things to an owner: work nobody has started,
   * work waiting for a time, and work about to be claimed.
   */
  function stateLabel(task: TaskView): string {
    return task.status === "queued" ? taskPhaseLabel(taskPhase(task)) : taskStatusLabel(task.status);
  }

  // A finished or blocked run always states why. The backend refuses to record a
  // terminal task without a reason (BUG-09); this is the line that shows it, so
  // "failed" is never the whole story the owner gets.
  function outcome(task: TaskView): string | null {
    if (["queued", "running", "continuing", "paused"].includes(task.status)) return null;
    return task.summary?.trim() || "No reason was recorded for this outcome.";
  }

  function flatten(
    items: TaskView[],
    open: string[] = [],
    everything: TaskView[] = items,
  ): Array<{ task: TaskView; depth: number }> {
    const ids = new Set(items.map((task) => task.task_id));
    // Children are drawn from every task, finished ones included: opening a
    // parent shows all of its delegated work, which is what its count counts.
    const children = new Map<string, TaskView[]>();
    for (const task of everything) {
      if (task.parent_task_id && task.parent_task_id !== task.task_id) {
        children.set(task.parent_task_id, [...(children.get(task.parent_task_id) ?? []), task]);
      }
    }
    const result: Array<{ task: TaskView; depth: number }> = [];
    const visit = (task: TaskView, depth: number) => {
      result.push({ task, depth });
      // A tree the server keeps acyclic; the bound is so a bad row cannot hang the page.
      if (!open.includes(task.task_id) || depth > 16) return;
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
    // Backlog #10 — every repeating cadence reads as a routine, so an hourly or
    // weekly one never looks like a one-shot whose next slot is its only one.
    // UX-TASK-02 — and the terms it runs on, so "which 09:00, until when, and
    // what happens if the machine was off" is on the card rather than in a
    // form that has since closed.
    if (task.recurrence) {
      // DEC-12 step 6 — a paused routine has no next run until the owner
      // continues it; its stored slot is the one that last ran, and printing it
      // as "next" put a date in the past on the card.
      const terms = [
        task.status === "paused"
          ? `${cadenceLabel(task.recurrence)}, paused — no next run until you continue it`
          : `${cadenceLabel(task.recurrence)}, next ${when}`,
      ];
      if (task.schedule_timezone) terms.push(task.schedule_timezone);
      if (task.schedule_until) terms.push(`until ${new Date(task.schedule_until).toLocaleDateString()}`);
      if (task.missed_run_policy === "skip") terms.push("skips missed runs");
      return terms.join(" · ");
    }
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

  // BUG-299 — the named task's attempts. A generation guards it for the same
  // reason NEW-PROJ-01 made Projects guard theirs: two reads can be in flight
  // when the owner moves between tasks, and a header standing over another
  // task's history is the same untruth as a project header over another
  // project's files.
  let detail = $state<TaskDetailView | null>(null);
  let detailError = $state<string | null>(null);
  let detailLoading = $state(false);
  let detailGeneration = 0;

  async function loadDetail(id: string) {
    const generation = ++detailGeneration;
    detailLoading = true;
    try {
      const view = await api.taskDetail(id);
      if (generation !== detailGeneration) return;
      detail = view;
      detailError = null;
    } catch (error) {
      if (generation !== detailGeneration) return;
      detail = null;
      detailError =
        error instanceof ApiError && error.status === 404
          ? "That task is not on this account's board."
          : error instanceof ApiError
            ? `Unavailable (${error.status})`
            : "Unavailable";
    } finally {
      if (generation === detailGeneration) detailLoading = false;
    }
  }

  // Clears immediately on a change of task, so the panel never shows the
  // previous task's attempts under the new task's heading while the read runs.
  $effect(() => {
    const id = taskId;
    if (id === null) {
      detailGeneration += 1;
      detail = null;
      detailError = null;
      detailLoading = false;
      return;
    }
    detail = null;
    detailError = null;
    void loadDetail(id);
  });

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
  const activeProject = $derived(
    (projects?.projects ?? []).find((entry) => entry.project_id === (projectId ?? workProject())) ??
      null,
  );

  /** Where a run executes. Read once; a failed read says so rather than
   *  claiming an environment nothing observed. */
  let environment = $state<ExecutionEnvironment | null>(null);
  let environmentUnavailable = $state(false);
  const environmentLabel = $derived(
    environmentUnavailable
      ? "Environment unavailable"
      : environment
        ? `${environment.name}${environment.available ? "" : " — setup required"}`
        : "Reading environment…",
  );
  const capacityLabel = $derived(
    activeProfile?.context_window_tokens
      ? `${new Intl.NumberFormat(undefined, { notation: "compact" }).format(activeProfile.context_window_tokens)} tokens`
      : "Capacity unknown",
  );

  /** COMPOSER-06 — the boundary this work will run inside, as one line. */
  const contextFacts = $derived([
    ...(activeProject !== null
      ? [
          /*
           * UX-BUILD-05 — the link goes to this project, not to the list of
           * them. Naming the project and then opening a page where the owner
           * has to find it again is the weak return path the review names; the
           * id is already here, so the link can carry it.
           */
          {
            label: "Project",
            value: activeProject.name,
            short: activeProject.name,
            href: `#/projects?project=${encodeURIComponent(activeProject.project_id)}`,
            action: "Open project work",
          },
        ]
      : []),
    {
      label: "Method",
      value: workMethod === "build" ? "Build — reads the project's repository" : "Chat",
      short: workMethod === "build" ? "Build" : "Chat",
    },
    // These two were permanent chips beside the model picker, and
    // they are facts rather than actions: where a run executes, and how much
    // the chosen model can hold. In the context line they are still stated and
    // still one click from the page that changes them, without spending two of
    // the composer's tokens on the ordinary case.
    {
      label: "Runs in",
      value: environmentLabel,
      short: environmentLabel,
      href: "#/settings?tab=runtime",
      action: "Runtime",
    },
    {
      label: "Context",
      value: capacityLabel,
      short: capacityLabel,
      href: "#/models?tab=models",
      action: "Models",
    },
  ]);



  async function createTask() {
    if (!title.trim() || !objective.trim() || modelBlocked || attachStore.uploading || (wantsStartTime && !scheduledAt) || endsBeforeFirst) return;
    creating = true; notice = null; noticeHref = null;
    const attachments = wireAttachments(attachStore.take());
    try {
      await api.createTask({
        title: title.trim(), description: objective.trim(), priority,
        ...(parentTaskId ? { parent_task_id: parentTaskId } : {}),
        ...(wantsStartTime
          ? { scheduled_at: new Date(scheduledAt).toISOString(), timezone: scheduleZoneName() }
          : {}),
        ...(cadence === "routine" ? { missed_runs: missedRuns } : {}),
        ...(runUntil ? { run_until: runUntil } : {}),
        ...(cadence === "routine" ? { recurrence: routineEvery } : cadence === "background" ? { recurrence: "background" } : {}),
        ...(projectId ? { project_id: projectId } : {}),
        ...(workMethod === "build" ? { surface: "build" } : {}),
        ...(modelProfile && model ? { model_profile: modelProfile, model } : {}),
        ...(attachments ? { attachments } : {}),
      });
      titleOverride = ""; objective = ""; parentTaskId = ""; partOfOther = false; endsOn = ""; missedRuns = "run_once"; priority = "normal"; timing = "now"; runMode = "single"; routineEvery = "daily"; scheduledAt = ""; workMethod = "chat";
      // The model stays chosen: it is a choice about how this owner plans work,
      // not part of the draft just filed, and clearing it left the next task's
      // Create button disabled behind "No model is chosen".
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

  // REM-TASK-02 — all three lifecycle controls below go through the shared
  // controller, so one run has one Stop, one Resume and one Run-now meaning
  // wherever the owner presses it, and a refusal is reported apart from a lost
  // response, with the runtime's reason.
  //
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
    noticeHref = null;
    const outcome = await resumeRun(task);
    notice = outcome.notice;
    noticeHref = outcome.detailHref ?? null;
    await load();
    busyTask = null;
  }

  async function runTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    noticeHref = null;
    const outcome = await startRunNow(task);
    notice = outcome.notice;
    noticeHref = outcome.detailHref ?? null;
    await load();
    busyTask = null;
  }

  async function again(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    noticeHref = null;
    const outcome = await runAgain(task);
    notice = outcome.notice;
    await load();
    busyTask = null;
  }

  /** One dispatch for every control the lifecycle offers (UX-TASK-05). */
  function act(task: TaskView, action: TaskAction) {
    if (action === "run_now") return runTask(task);
    if (action === "continue") return resumeTask(task);
    if (action === "run_again") return again(task);
    return stopTask(task);
  }

  function busyLabel(action: TaskAction): string {
    if (action === "run_now") return "Starting…";
    if (action === "continue") return "Continuing…";
    if (action === "run_again") return "Filing…";
    return action === "cancel" ? "Cancelling…" : "Stopping…";
  }

  async function stopTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    noticeHref = null;
    const outcome = await stopRun(task, "user stopped this task (web UI)");
    notice = outcome.notice;
    noticeHref = outcome.detailHref ?? null;
    await load();
    busyTask = null;
  }

  $effect(() => { void projectId; void sessionId; void load(); });

  // Tasks run outside this page: a queued run is claimed, works, and finishes
  // while the list sits still, so the page polls rather than show "queued"
  // after the run has ended (BUG-09).
  onMount(() => {
    // Chat's `/schedule` asks this surface to open on **Schedule once**. It
    // arranges the form and stops: nothing is created and nothing is scheduled.
    if (takeScheduleRequest()) {
      // Asked for by the shape the runtime knows, and translated by the one
      // function that owns that translation.
      const asked: TaskCadence = "once";
      timing = timingFor(asked);
      runMode = runModeFor(asked);
      queueMicrotask(() => instructionEl?.focus());
    }
    void refreshModels();
    void refreshReadCapabilities();
    void api
      .capabilityGates()
      .then((view) => (composerGates = view))
      .catch(() => (composerGates = []));
    void api
      .executionEnvironments()
      .then((view) => {
        environment = view.environments.find((item) => item.selected) ?? null;
        environmentUnavailable = false;
      })
      .catch(() => {
        environment = null;
        environmentUnavailable = true;
      });
    const timer = window.setInterval(() => {
      void load();
      // BUG-299 — an open history is a live view of the same records the board
      // is polling, so it moves on the same tick rather than going stale behind
      // a board that is up to date.
      if (taskId !== null) void loadDetail(taskId);
    }, 15_000);
    return () => window.clearInterval(timer);
  });
</script>

<section class="tasks">
  <header>  <GuideLink route="tasks" />
<button type="button" class="btn btn-ghost btn-sm" onclick={load}><Icon name="refresh" size="sm" /> Refresh</button></header>

  <!-- BUG-299 — the address Home's rows, Build's panel and the Stop control's
       "refresh to see the run's current state" all needed. It opens above the
       board rather than replacing it, so following a link never costs the owner
       the page they were on. -->
  {#if taskId}
    <TaskHistory
      detail={detail}
      loading={detailLoading}
      error={detailError}
      onrefresh={() => void loadDetail(taskId)}
      onclose={() => {
        detail = null;
        detailError = null;
      }}
    />
  {/if}

  <!-- COMPOSER-10 — the same shell Chat, Build and Design use. What differs is
       the primary action and the one control specific to planning work: when
       it should run. Title, parent, priority, repeat, start time and model are
       derived or behind Details. -->
  <Composer
    ariaLabel="Plan work"
    cardClass="composer-task"
    inputId="task-instruction"
    inputLabel="What should Raiker do?"
    bind:value={objective}
    bind:inputEl={instructionEl}
    dropActive={composerDrop.over}
    dropHandlers={{
      ondragenter: composerDrop.ondragenter,
      ondragover: composerDrop.ondragover,
      ondragleave: composerDrop.ondragleave,
      ondrop: composerDrop.ondrop,
    }}
    inputProps={{
      placeholder:
        cadence === "background"
          ? "e.g. Research local AI news and tell me what changed"
          : cadence === "routine"
            ? "e.g. Review today's priorities and flag what slipped"
            : "Describe the work, the outcome you want, and anything it must not do.",
      disabled: creating,
    }}
    onsubmit={() => void createTask()}
  >
    {#snippet above()}
      <!-- REM-TASK-01 — when it runs, then how it runs. The second question is
           only asked where the runtime has an answer for it: a background agent
           starts now, so it is not offered beside a start time. -->
      <div class="cadence chip-row" role="group" aria-label="When to run">
        {#each TASK_TIMINGS as entry (entry.id)}
          <button
            type="button"
            class="chip"
            aria-pressed={timing === entry.id}
            onclick={() => (timing = entry.id)}>{entry.label}</button
          >
        {/each}
      </div>
      {#if timing === "now"}
        <div class="cadence chip-row" role="group" aria-label="How it runs">
          {#each TASK_RUN_MODES as entry (entry.id)}
            <button
              type="button"
              class="chip"
              aria-pressed={runMode === entry.id}
              onclick={() => (runMode = entry.id)}>{entry.label}</button
            >
          {/each}
        </div>
      {/if}
      <ComposerChips store={attachStore} disabled={creating} />
      {#if attachOpen}
        <ComposerAttachPanel store={attachStore} disabled={creating} idPrefix="task" />
      {/if}
      {#if projectPickerOpen}
        <div class="project-choice" role="group" aria-label="Choose a project">
          <label for="task-project-choice">Project for this work</label>
          <select
            id="task-project-choice"
            class="bar-select"
            value={workProject()}
            onchange={(event) => {
              projectPickerOpen = false;
              setWorkProject((event.currentTarget as HTMLSelectElement).value);
            }}
          >
            <option value="">No project — this work stands alone</option>
            {#each pickableProjects(projects, workProject()) as entry (entry.project_id)}
              <option value={entry.project_id}>{entry.name}</option>
            {/each}
          </select>
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            onclick={() => (projectPickerOpen = false)}>Done</button
          >
        </div>
      {/if}
    {/snippet}

    {#snippet below()}
      {#if detailsOpen}
        <!-- COMPOSER-10 — "scheduling details expand only after requested". The
             summary above stays visible while they are open, so opening the
             details never becomes the only place the choice is legible. -->
        <!-- UX-TASK-03 — two groups, because they answer two questions. When
             the work runs comes first and is the one an owner checks before
             committing; how it is organised is detail most work never needs. -->
        <div class="task-details" id="task-details">
          {#if wantsStartTime}
            <fieldset class="detail-group" aria-label="Schedule">
              <legend>Schedule</legend>
              {#if cadence === "routine"}
                <label>
                  Repeat
                  <select class="select" aria-label="Repeat" bind:value={routineEvery}>
                    {#each AGENT_CADENCES.filter((option) => option.id !== "background") as option (option.id)}
                      <option value={option.id}>{option.label}</option>
                    {/each}
                  </select>
                </label>
              {/if}
              <label>
                {cadence === "routine" ? "First run" : "Start time"}
                <input
                  class="input"
                  aria-label={cadence === "routine" ? "First run" : "Start time"}
                  type="datetime-local"
                  bind:value={scheduledAt}
                  required
                />
                <!-- REM-TASK-01 / UX-TASK-02 — the field reads this machine's
                     zone, and the zone is now stored with the task, so a daily
                     09:00 stays 09:00 here when the clocks change. -->
                <small class="zone">Times are {scheduleZone()}.</small>
              </label>
              {#if cadence === "routine"}
                <label>
                  Ends
                  <input
                    class="input"
                    type="date"
                    aria-label="Last day it runs"
                    bind:value={endsOn}
                  />
                  <small class="zone">{endsOn ? "Its last run is on or before this day." : "Leave empty to keep going until you stop it."}</small>
                </label>
                <label>
                  If Raiker was not running
                  <select class="select" aria-label="If a run is missed" bind:value={missedRuns}>
                    {#each MISSED_RUN_POLICIES as option (option.id)}
                      <option value={option.id}>{option.label}</option>
                    {/each}
                  </select>
                </label>
              {/if}
              {#if upcoming.length > 0}
                <div class="preview" role="status" aria-label="Next runs">
                  <span class="preview-heading">Next {upcoming.length === 1 ? "run" : "runs"}</span>
                  <ol>
                    {#each upcoming as run, index (index)}
                      <li>{run.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</li>
                    {/each}
                  </ol>
                  {#if cadence === "routine"}
                    <small>
                      {missedRuns === "skip"
                        ? "A slot Raiker was not running for is skipped; the routine waits for its next one."
                        : "If Raiker was not running at a slot, it runs once when it is back, and never twice."}
                    </small>
                  {/if}
                </div>
              {:else if scheduledAt && cadence === "routine"}
                <p class="preview-empty" role="status">This schedule ends before its first run.</p>
              {/if}
            </fieldset>
          {/if}
          <fieldset class="detail-group" aria-label="Organisation">
            <legend>Organisation</legend>
            <label>
              Title
              <input
                class="input"
                aria-label="Task title"
                maxlength="240"
                placeholder={title || "Derived from your instruction"}
                bind:value={titleOverride}
              />
            </label>
            <label>
              Priority
              <select class="select" aria-label="Priority" bind:value={priority}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </select>
            </label>
            {#if buildAvailable}
              <div class="chip-row method" role="group" aria-label="How to work">
                <button
                  type="button"
                  class="chip"
                  aria-pressed={workMethod === "chat"}
                  onclick={() => (workMethod = "chat")}>Chat</button
                >
                <button
                  type="button"
                  class="chip"
                  aria-pressed={workMethod === "build"}
                  onclick={() => (workMethod = "build")}>Build</button
                >
              </div>
            {/if}
            <!-- UX-TASK-06 — hierarchy when asked for. A parent waits for
                 its children before it settles, which is worth choosing on
                 purpose rather than by reading past a select. -->
            {#if partOfOther || parentTaskId}
              <label class="parent">
                Part of
                <select class="select" aria-label="Parent work" bind:value={parentTaskId}>
                  <option value="">No parent — top-level work</option>
                  {#each tasks ?? [] as task (task.task_id)}
                    <option value={task.task_id}>{task.title}</option>
                  {/each}
                </select>
                <small class="zone">The parent finishes only when this does.</small>
              </label>
            {:else if (tasks ?? []).length > 0}
              <button
                type="button"
                class="btn btn-ghost btn-sm parent-toggle"
                onclick={() => (partOfOther = true)}>Make this part of other work…</button
              >
            {/if}
          </fieldset>
        </div>
      {/if}
      <ModelReadinessStrip
        readiness={modelsKnown() ? modelReadiness : null}
        draftPreserved={Boolean(objective.trim())}
      />
    {/snippet}

    {#snippet left()}
      <ComposerActionMenu
        kind="add"
        items={addItems}
        disabled={creating}
        onchoose={runComposerAction}
      />
      <ComposerActionMenu
        kind="tools"
        items={toolItems}
        disabled={creating}
        onchoose={runComposerAction}
      />
      <!-- The one control planning work needs that asking a question does not.
           Collapsed it still says what was chosen, so the details being hidden
           never means the timing is invisible. -->
      <button
        type="button"
        class="composer-control schedule-toggle"
        aria-expanded={detailsOpen}
        aria-controls="task-details"
        onclick={() => (detailsOpen = !detailsOpen)}
      >
        <Icon name="clock" size="sm" />
        <span>{schedule}</span>
      </button>
      <ComposerContext facts={contextFacts} disabled={creating} />
    {/snippet}

    {#snippet right()}
      <ModelPicker
        {profiles}
        catalogues={modelCatalogues()}
        {selectedProfile}
        bind:profileId={modelProfile}
        bind:model
        onchosen={(profileId, chosen) => void rememberSurfaceModel(surface, profileId, chosen)}
        onreset={() => void forgetSurfaceModel(surface)}
      />
      <button
        type="submit"
        class="btn btn-primary send"
        disabled={creating ||
          attachStore.uploading ||
          modelBlocked ||
          !objective.trim() ||
          (wantsStartTime && !scheduledAt) ||
          endsBeforeFirst}
      >
        <Icon name={creating ? "clock" : "send"} size="sm" />
        <span class="send-label"
          >{creating
            ? "Saving…"
            : attachStore.uploading
              ? "Uploading…"
              : primaryAction(cadence)}</span
        >
      </button>
    {/snippet}

    {#snippet hint()}
      {schedule} · {title ? `Filed as “${title}”` : "Write an instruction to begin"}
    {/snippet}
  </Composer>

  {#if notice}<p class="notice" role="status">
      {notice}
      {#if noticeHref}<a href={noticeHref}>Open its history</a>{/if}
    </p>{/if}
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
            <!-- The plan form is already on this page, above the empty
                 state. Naming where it is would be worse than putting the
                 cursor in it. -->
            <button type="button" class="btn btn-primary" onclick={() => instructionEl?.focus()}>
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
          {@const children = delegated(task)}
          <article class="card task" style={`--depth:${row.depth}`}>
            <div class="task-main">
              <div class="task-title">
                <span class="branch" aria-hidden="true">{row.depth > 0 ? "↳" : ""}</span>
                <div><h4>{task.title}</h4><p>{task.objective || "No additional instructions."}</p></div>
              </div>
              <Badge variant={taskBadge(task.status)} label={stateLabel(task)} />
            </div>
            {#if children.total > 0}
              <!-- UX-TASK-06 — a parent settles only when its own run and every
                   task it delegated have: completed if all of them did, failed
                   if any did not. The bar is that rule, counted. -->
              <div class="delegated">
                <div
                  class="progress"
                  role="progressbar"
                  aria-label="Delegated work settled"
                  aria-valuenow={children.settled}
                  aria-valuemin="0"
                  aria-valuemax={children.total}
                >
                  <div style={`width:${Math.round((children.settled / children.total) * 100)}%`}></div>
                </div>
                <button
                  type="button"
                  class="btn btn-ghost btn-sm"
                  aria-expanded={expanded.includes(task.task_id)}
                  onclick={() => toggleDelegated(task.task_id)}
                >
                  {children.settled} of {children.total} delegated {children.total === 1 ? "task" : "tasks"} settled ·
                  {expanded.includes(task.task_id) ? "Hide" : "Show"}
                </button>
              </div>
            {/if}
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
                It completes when every one of them completes, and fails if any fails or is stopped.
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
            {:else if task.status === "paused" && task.summary?.trim()}
              <!-- DEC-12 step 6 — why it stopped, beside the Continue that
                   starts it again; "paused" alone sent the owner to History. -->
              <p class="blocked" role="status">
                <Icon name="warning" size="sm" /> {task.summary.trim()}
              </p>
            {:else if outcome(task)}
              <p class="outcome" role="status">{outcome(task)}</p>
            {/if}
            {#if task.delivery_state === "failed"}
              <!-- DEC-12 step 5 — whether the owner was told is a separate fact
                   from whether the work worked. A completed run whose notice did
                   not arrive is still completed, and says so here. -->
              <p class="blocked delivery-failed" role="status" data-testid="task-delivery-failed">
                <Icon name="warning" size="sm" />
                <span><strong>Delivery failed.</strong> {task.delivery_detail ?? "The notice that this ended did not arrive."}</span>
              </p>
            {/if}

            <!-- "Now:" is only true while the work is moving. A settled task's
                 last step is history, and its outcome line already says how it
                 ended. -->
            {#if task.current_step && ["running", "waiting"].includes(taskPhase(task))}<p class="step">Now: {task.current_step}</p>{/if}
            {#if task.progress_percent !== null}
              <div class="progress" role="progressbar" aria-valuenow={task.progress_percent} aria-valuemin="0" aria-valuemax="100"><div style={`width:${task.progress_percent}%`}></div></div>
            {/if}
            <footer>
              <!-- The same order a thread and a project use: where the
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
                <!-- C11 — each task runs its cycles in a conversation of its
                     own, so "what did the overnight run find?" is a thread the
                     owner opens and replies in, and the reply is context the
                     next cycle reads.

                     Only offered once there is something to read: a link to an
                     empty transcript is a dead end, and a routine that has not
                     run yet has one. -->
                {#if task.thread_session_id && (task.thread_turns ?? 0) > 0}
                  <a class="btn btn-ghost btn-sm thread-link" href={`#/new-chat?session=${task.thread_session_id}`}>
                    <Icon name="chat" size="sm" />
                    Thread · {task.thread_turns}
                  </a>
                {/if}
                <!-- BUG-299 — every run's attempts, the decision each waited on
                     and the continuation that followed, at one address. -->
                <a class="btn btn-ghost btn-sm thread-link" href={taskDetailHref(task.task_id)}>
                  <Icon name="activity" size="sm" />
                  History
                </a>
                <!-- UX-TASK-05 — the controls this task's phase offers, from the
                     one module every surface asks. Continue for a parked
                     approval is already on the line above, beside its reason. -->
                {#each taskActions(task).filter((action) => !(action === "continue" && task.status === "waiting_for_approval")) as action (action)}
                  <button
                    type="button"
                    class={action === "run_now" || action === "continue"
                      ? "btn btn-primary btn-sm"
                      : action === "run_again"
                        ? "btn btn-ghost btn-sm"
                        : "btn btn-danger btn-sm"}
                    onclick={() => act(task, action)}
                    disabled={busyTask === task.task_id}
                    >{busyTask === task.task_id ? busyLabel(action) : taskActionLabel(action)}</button
                  >
                {/each}
              </span>
            </footer>
          </article>
        {/each}
      </section>
    {/if}
    {#if history.length > 0}<section class="history"><h3>Finished work</h3>{#each history as task (task.task_id)}<div class="history-row"><div class="history-main"><a class="history-title" href={taskDetailHref(task.task_id)}>{task.title}</a><p class="outcome">{outcome(task)}</p>{#if task.delivery_state === "failed"}<!-- DEC-12 step 5 — the work's outcome, and separately whether the owner was told. --><p class="delivery-failed" role="status" data-testid="task-delivery-failed"><Icon name="warning" size="sm" /> <strong>Delivery failed.</strong> {task.delivery_detail ?? "The notice that this ended did not arrive."}</p>{/if}</div><Badge variant={taskBadge(task.status)} label={stateLabel(task)} /><span>{relativeTime(task.updated_at)}</span>{#if taskActions(task).includes("run_again")}<button type="button" class="btn btn-ghost btn-sm" onclick={() => again(task)} disabled={busyTask === task.task_id}>{busyTask === task.task_id ? "Filing…" : "Run again"}</button>{/if}</div>{/each}</section>{/if}
  {/if}
</section>

<style>
  .tasks{width:100%}.tasks header,.task-main,footer,.history-row{align-items:flex-start;display:flex;gap:var(--space-3);justify-content:space-between}.tasks header{margin-bottom:var(--space-4)}h3,h4{margin:0}.task p{color:var(--text-2);font-size:var(--text-sm);margin:.35rem 0 0}.summary{display:flex;gap:var(--space-4);margin:var(--space-4) 0}.summary span{color:var(--text-2);font-size:var(--text-sm)}.summary strong{color:var(--text-1);font-size:var(--text-base)}.work-list,.history{display:grid;gap:var(--space-2);margin-top:var(--space-4)}.task{margin-left:calc(var(--depth) * 1.15rem);max-width:calc(100% - var(--depth) * 1.15rem)}.task-title{display:flex;gap:.5rem}.branch{color:var(--accent);min-width:.8rem}.task h4{font-size:var(--text-base)}.task-attachments{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.7rem}.task-attachments span{align-items:center;background:var(--sunken);border:1px solid var(--border);border-radius:var(--r-sm);color:var(--text-2);display:flex;font-size:var(--text-xs);gap:.3rem;max-width:100%;overflow-wrap:anywhere;padding:.35rem .5rem}.step{color:var(--accent)!important}.continuing{align-items:center;background:var(--accent-soft);border:1px solid var(--accent-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;font-size:var(--text-sm);gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.blocked{align-items:center;background:var(--warn-soft);border:1px solid var(--warn-border);border-radius:var(--r-sm);color:var(--text-1)!important;display:flex;flex-wrap:wrap;font-size:var(--text-sm);gap:.4rem;margin-top:.6rem!important;padding:.4rem .6rem}.recovery{align-items:center;display:flex;flex-wrap:wrap;gap:.35rem;margin-left:auto}.recovery-note{color:var(--text-3);font-size:var(--text-xs)}.progress{background:var(--sunken);border-radius:var(--r-pill);height:6px;margin-top:.7rem;overflow:hidden}.progress div{background:var(--accent);height:100%}footer{align-items:center;color:var(--text-3);font-size:var(--text-xs);margin-top:.8rem}.task-actions{align-items:center;display:flex;flex-wrap:wrap;gap:.4rem}.thread-link{align-items:center;display:inline-flex;gap:.3rem;text-decoration:none}.history-row{align-items:center;border-bottom:1px solid var(--border);padding:.65rem 0}.history-row span:last-child{color:var(--text-3);font-size:var(--text-sm)}.history-main{display:grid;gap:.15rem;min-width:0}.history-title{color:var(--text-1);text-decoration:none}.history-title:hover{text-decoration:underline}.outcome{color:var(--text-2);font-size:var(--text-sm);margin:.4rem 0 0}.history-main .outcome{margin:0}.delivery-failed{align-items:center;color:var(--warn-text,var(--text-1));display:flex;flex-wrap:wrap;font-size:var(--text-sm);gap:.35rem;margin:0}.notice{color:var(--success);margin:var(--space-3) 0}
  /* COMPOSER-10 — the details, when asked for. A grid rather than a column so
     four short fields do not become four full-width rows. */
  .task-details{display:grid;gap:var(--space-3);margin:var(--space-2) 0}
  /* UX-TASK-03 — Schedule and Organisation are two groups, each a grid of its
     own short fields, so four of them do not become four full-width rows. */
  .detail-group{display:grid;gap:var(--space-3);grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));margin:0;padding:var(--space-3);border:1px solid var(--border);border-radius:var(--r-sm);min-width:0}
  .detail-group legend{padding:0 .35rem;color:var(--text-3);font-size:var(--text-xs);font-weight:650;letter-spacing:.06em;text-transform:uppercase}
  .task-details label{color:var(--text-2);display:grid;font-size:var(--text-sm);gap:.35rem}
  .parent-toggle,.method{align-self:end;justify-self:start}
  .preview-empty{grid-column:1/-1;margin:0;color:var(--warn,var(--text-2));font-size:var(--text-sm)}
  .zone{color:var(--text-3);font-size:var(--text-xs)}
  /* The preview spans the details grid: three timestamps read as a list, not as
     a fourth field squeezed beside Parent work. */
  .preview{grid-column:1/-1;display:grid;gap:.25rem;padding:var(--space-3);border-left:3px solid var(--accent);background:var(--sunken);border-radius:var(--r-sm)}
  .preview-heading{color:var(--text-3);font-size:var(--text-xs);text-transform:uppercase;letter-spacing:.04em}
  .preview ol{margin:0;padding-left:1.1rem;display:grid;gap:.1rem;color:var(--text-1);font-size:var(--text-sm)}
  .preview small{color:var(--text-2);font-size:var(--text-xs)}
  /* The one control planning work needs that asking a question does not. It
     reads as a composer control rather than as a form field, because that is
     what it is. */
  .schedule-toggle{display:inline-flex;align-items:center;gap:.35rem;white-space:nowrap;max-width:16rem;overflow:hidden;text-overflow:ellipsis}
  .project-choice{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap;margin:0 0 var(--space-2)}
  .project-choice label{color:var(--text-2);font-size:var(--text-sm)}
  .delegated{display:flex;align-items:center;gap:var(--space-2);margin-top:.6rem}
  .delegated .progress{flex:1 1 auto;margin-top:0}
  .project-choice select{min-width:12rem}@media(max-width:42rem){.tasks header{flex-direction:column}.task{margin-left:0;max-width:none}.history-row{flex-wrap:wrap}.history-main{flex:1 1 100%}.history-row span:last-of-type,.history-row button{white-space:nowrap}}
</style>
