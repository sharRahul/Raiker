<script lang="ts">
  /**
   * Workbench — the default screen, and now a board rather than a box.
   *
   * It used to open with a large composer that could not send anything. The
   * prompt was written here, handed to Chat, Build or Tasks, and *re-shown* there
   * in that surface's own composer, which meant the first thing the product asked
   * you to do was type into a control that was a copy of the real one. It also
   * pushed the only genuinely live information on the screen — what is running,
   * what is waiting, what fires next — into a narrow rail beside it.
   *
   * The box is gone. What is left is the answer to "what is Raiker doing right
   * now", in three groups that are three different facts, not three names for the
   * same one:
   *
   *  - **Running now** — a governed cycle in flight this second, with the safe
   *    boundary you can stop it at.
   *  - **Standing agents** — work with a repeating cadence, which re-arms itself
   *    after every cycle and keeps going until stopped.
   *  - **Scheduled runs** — a single future run that has not fired yet.
   *
   * Every row is a task the backend already owns, so the board never invents a
   * state: it reads `GET /api/tasks` and classifies by the recurrence and the
   * scheduled time the runtime itself honours. Starting work is a link to the
   * surface that owns the composer, so there is exactly one composer per kind of
   * work and no second send path.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type {
    ApprovalView,
    Diagnostics,
    ProjectsList,
    SessionSummary,
    TaskView,
  } from "../apiTypes";
  import Badge from "../components/Badge.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import StatTile from "../components/StatTile.svelte";
  import { relativeTime } from "../format";
  import { cadenceLabel } from "../agentCadence";
  import GuideLink from "../components/GuideLink.svelte";
  import { isActiveTask, taskBadge, taskStatusLabel } from "../statusMaps";

  let sessions = $state<SessionSummary[] | null>(null);
  let tasks = $state<TaskView[] | null>(null);
  let approvals = $state<ApprovalView[] | null>(null);
  let projects = $state<ProjectsList | null>(null);
  let diagnostics = $state<Diagnostics | null>(null);
  let unavailable = $state(false);
  let updatedAt = $state<Date | null>(null);
  let busyTask = $state<string | null>(null);
  let notice = $state<string | null>(null);

  /**
   * A repeating cadence re-arms after each cycle, so it is a standing agent. The
   * list mirrors `RECURRING_INTERVALS` server-side; `background` is deliberately
   * absent because it is one cycle that does not repeat.
   */
  const REPEATING = ["continuous", "hourly", "daily", "weekly"];
  const repeats = (task: TaskView) => REPEATING.includes(task.recurrence ?? "");

  const active = $derived((tasks ?? []).filter((task) => isActiveTask(task.status)));

  /**
   * A cycle is in flight, or parked mid-flight. `queued` is deliberately excluded
   * here and handled below: the scheduler stores an *armed* task as `queued` with
   * its next slot in `scheduled_at`, so counting every queued row as running is
   * exactly the overcount BUG-09 was filed about. A queued row with no scheduled
   * time is about to start and does belong here.
   */
  const IN_FLIGHT = ["running", "continuing", "waiting_for_approval", "waiting_for_children", "paused"];
  const armed = (task: TaskView) =>
    task.status === "queued" && (task.scheduled_at ?? null) !== null;

  const runningNow = $derived(
    active.filter((task) => IN_FLIGHT.includes(task.status) || !armed(task)),
  );
  // Every repeating task that is still alive stands, whether this second's cycle
  // is in flight or the next one is armed. A running agent therefore appears in
  // both groups, because "a cycle is running" and "an agent is standing" are two
  // different facts and the board answers both.
  const agents = $derived(active.filter(repeats));
  const scheduled = $derived(active.filter((task) => !repeats(task) && armed(task)));
  // Deliberately not "the active project": no route is scoped by one any more.
  // What the board can honestly say is how many projects exist.
  const projectCount = $derived(projects?.projects.length ?? 0);
  const named = $derived((sessions ?? []).filter((s) => (s.title ?? "").trim() !== ""));
  const hasActivity = $derived(
    named.length > 0 || (tasks ?? []).length > 0 || (projects?.projects ?? []).length > 0,
  );
  const runtimeIssues = $derived(
    diagnostics === null
      ? 0
      : diagnostics.missing_config.length > 0
        ? diagnostics.missing_config.length
        : diagnostics.production_ready_local_single_user_runtime
          ? 0
          : 1,
  );

  async function load() {
    unavailable = false;
    try {
      [sessions, tasks, approvals, projects] = await Promise.all([
        // Conversations only — the server-owned session a task run executes in is
        // not something to "resume" (BUG-10).
        api.sessions(undefined, false, "chat"),
        api.tasks(),
        api.approvals(),
        api.projects(),
      ]);
      try {
        diagnostics = await api.diagnostics();
      } catch {
        // Readiness is supplementary; an older or temporarily unavailable
        // diagnostics endpoint must not erase the board.
        diagnostics = null;
      }
      updatedAt = new Date();
    } catch {
      unavailable = true;
    }
  }

  /** Ask one run to stop at its next safe boundary. Never a hard kill. */
  async function stopTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    try {
      await api.interrupt({
        session_id: task.session_id,
        task_id: task.task_id,
        action_type: "cancel",
        reason: "stopped from the Workbench board",
      });
      notice = `Asked “${task.title}” to stop at its next safe boundary.`;
      await load();
    } catch (error) {
      notice =
        error instanceof ApiError
          ? `Could not request the stop (${error.reasonCode ?? error.status}).`
          : "Could not request the stop.";
    } finally {
      busyTask = null;
    }
  }

  /** What a row is waiting for, in the owner's language. */
  function detail(task: TaskView): string {
    if (task.status === "waiting_for_approval") return "Blocked on a decision you have not made yet.";
    if (task.status === "waiting_for_children") return "Its own run finished; delegated work has not.";
    if (task.current_step) return task.current_step;
    if (task.progress_percent !== null) return `${task.progress_percent}% through its objective.`;
    return task.objective.slice(0, 140);
  }

  // A board has to be live or it is a stale screenshot of one. The same 15-second
  // cadence the Tasks page uses, because it is the same data.
  onMount(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15_000);
    return () => window.clearInterval(timer);
  });
</script>

<section class="workbench" aria-labelledby="workbench-title">
  <div class="intro">
    <div>
      <h2 id="workbench-title" class="display">{hasActivity ? "Welcome back" : "Welcome to your Work Dashboard"}</h2>
      <p class="lead">
        {#if unavailable}
          Raiker could not read what is running. Nothing was started or changed.
        {:else if tasks === null}
          Reading what is running…
        {:else if runningNow.length === 0 && agents.length === 0 && scheduled.length === 0}
          Nothing is running, standing, or scheduled. Start a conversation, a build, or a task.
        {:else}
          {runningNow.length} running · {agents.length} standing agent{agents.length === 1 ? "" : "s"} ·
          {scheduled.length} scheduled · {approvals?.length ?? 0} waiting on you
        {/if}
      </p>
    </div>
    <div class="refresh-state">
      <GuideLink route="home" />
      <span aria-live="polite">{updatedAt ? `Updated ${relativeTime(updatedAt.toISOString())}` : "Updating…"}</span>
      <button class="btn btn-ghost btn-sm" aria-label="Refresh Workbench" type="button" onclick={load}>
        <Icon name="refresh" size={15} /> Refresh
      </button>
    </div>
  </div>

  <nav class="start-row" aria-label="Start work">
    <a class="start-card" href="#/new-chat">
      <Icon name="chat" size={18} /><span><strong>Start a conversation</strong><small>Ask, think, work with a file</small></span>
    </a>
    <a class="start-card" href="#/build">
      <Icon name="code" size={18} /><span><strong>Start a build</strong><small>Change a repository under governance</small></span>
    </a>
    <a class="start-card" href="#/tasks">
      <Icon name="tasks" size={18} /><span><strong>Plan a task or agent</strong><small>Run once, on a cadence, or in the background</small></span>
    </a>
    <a class="start-card" href="#/projects">
      <Icon name="projects" size={18} /><span><strong>Open a project</strong><small>{projectCount === 0 ? "None yet" : `${projectCount} project${projectCount === 1 ? "" : "s"}`}</small></span>
    </a>
  </nav>

  {#if notice}<p class="notice" role="status">{notice}</p>{/if}

  <div class="columns">
    <div class="main-column">
      {#if unavailable}
        <PageState
          state="error"
          title="Workbench status is unavailable"
          detail="Refresh to retry. No work was started or changed."
        />
      {:else if tasks === null}
        <PageState state="loading" title="Loading status…" lines={3} />
      {:else}
        <section class="board card" aria-labelledby="running-h">
          <div class="card-head">
            <h3 id="running-h">Running now</h3>
            <a href="#/observe?tab=work">Live board</a>
          </div>
          {#if runningNow.length === 0}
            <p class="empty">Nothing is running.</p>
          {:else}
            <ul class="rows">
              {#each runningNow as task (task.task_id)}
                <li>
                  <div class="row-main">
                    <strong>{task.title}</strong>
                    <span>{detail(task)}</span>
                  </div>
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    {#if task.recurrence}<span class="kind">{cadenceLabel(task.recurrence)}</span>{/if}
                    <span class="since">started {relativeTime(task.created_at)}</span>
                  </div>
                  <div class="row-actions">
                    {#if task.status === "waiting_for_approval"}
                      <a class="btn btn-sm" href="#/approvals">Decide</a>
                    {/if}
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      disabled={busyTask === task.task_id}
                      onclick={() => void stopTask(task)}
                    >
                      {busyTask === task.task_id ? "Stopping…" : "Stop"}
                    </button>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        <section class="board card" aria-labelledby="agents-h">
          <div class="card-head">
            <h3 id="agents-h">Standing agents</h3>
            <a href="#/tasks">Manage agents</a>
          </div>
          {#if agents.length === 0}
            <p class="empty">No agent is standing.</p>
          {:else}
            <ul class="rows">
              {#each agents as task (task.task_id)}
                <li>
                  <div class="row-main">
                    <strong>{task.title}</strong>
                    <span>{detail(task)}</span>
                  </div>
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    <span class="kind">{cadenceLabel(task.recurrence ?? "")}</span>
                    {#if task.scheduled_at}<span class="since">next cycle {relativeTime(task.scheduled_at)}</span>{/if}
                    <span class="since">last moved {relativeTime(task.updated_at)}</span>
                  </div>
                  <div class="row-actions">
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      disabled={busyTask === task.task_id}
                      onclick={() => void stopTask(task)}
                    >
                      {busyTask === task.task_id ? "Stopping…" : "Stop"}
                    </button>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        <section class="board card" aria-labelledby="scheduled-h">
          <div class="card-head">
            <h3 id="scheduled-h">Scheduled runs</h3>
            <a href="#/tasks">Manage schedules</a>
          </div>
          {#if scheduled.length === 0}
            <p class="empty">Nothing is scheduled.</p>
          {:else}
            <ul class="rows">
              {#each scheduled as task (task.task_id)}
                <li>
                  <div class="row-main">
                    <strong>{task.title}</strong>
                    <span>{detail(task)}</span>
                  </div>
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    <span class="kind">fires {relativeTime(task.scheduled_at ?? task.created_at)}</span>
                  </div>
                  <div class="row-actions">
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      disabled={busyTask === task.task_id}
                      onclick={() => void stopTask(task)}
                    >
                      {busyTask === task.task_id ? "Cancelling…" : "Cancel"}
                    </button>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        {#if named.length > 0}
          <section class="board card" aria-labelledby="resume-h">
            <div class="card-head">
              <h3 id="resume-h">Continue working</h3>
              <a href="#/sessions">All sessions</a>
            </div>
            <ul class="resumes">
              {#each named.slice(0, 5) as session (session.session_id)}
                <li>
                  <a href={`#/new-chat?session=${encodeURIComponent(session.session_id)}`}>{session.title}</a>
                  <span>
                    {session.turn_count} turn{session.turn_count === 1 ? "" : "s"} · updated
                    {relativeTime(session.updated_at)}
                  </span>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/if}
    </div>

    <aside class="side-column" aria-label="Needs your attention">
      <h3 class="attention-title">Needs your attention</h3>
      {#if unavailable}
        <PageState
          state="error"
          title="Status is unavailable"
          detail="Refresh to retry. No work was started or changed."
        />
      {:else if approvals === null || tasks === null}
        <PageState state="loading" title="Loading status…" lines={3} />
      {:else}
        <StatTile
          label="Approvals"
          value={approvals.length}
          detail={approvals.length === 0
            ? "No decision needs your review."
            : approvals.length === 1
              ? "One decision blocks a governed action until you decide."
              : "Each one blocks a governed action until you decide."}
          tone={approvals.length > 0 ? "accent" : "neutral"}
          icon="approvals"
          href="#/approvals"
          linkLabel="Review approvals"
        />
        <StatTile
          label="Runtime issues"
          value={runtimeIssues}
          detail={runtimeIssues === 0
            ? "No readiness issue needs attention."
            : "Review configuration and readiness evidence before critical work."}
          tone={runtimeIssues > 0 ? "warn" : "neutral"}
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Review issues"
        />
        <StatTile
          label="Active work"
          value={active.length}
          detail={active.length === 0
            ? "Nothing is queued, running, paused, or waiting for approval."
            : "You can stop any of these at a safe boundary."}
          icon="tasks"
          href="#/observe?tab=work"
          linkLabel="Open the live board"
        />
      {/if}
    </aside>
  </div>
</section>

<style>
  .workbench { display: grid; gap: var(--space-5); }
  .intro { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
  /* BUG-37 — the greeting is display type: Raiker speaking to the owner, not a
     control label. Size, face and tracking come from the shared `.display` rule
     so this page cannot drift from the spec. */
  .intro h2 { margin: 0.15rem 0; }
  .lead { color: var(--text-2); max-width: 62ch; margin: 0; }
  .refresh-state { display: flex; align-items: center; gap: var(--space-3); color: var(--text-3); font-size: var(--text-sm); flex-wrap: wrap; justify-content: flex-end; }
  /* Starting work is a link to the surface that owns the composer, so the board
     never becomes a second send path. */
  .start-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); }
  .start-card {
    display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center;
    gap: var(--space-3); padding: var(--space-3) var(--space-4); color: var(--text-1);
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
    box-shadow: var(--shadow-1); text-decoration: none;
    transition: transform var(--motion-fast) var(--ease), border-color var(--motion-fast) var(--ease);
  }
  .start-card:hover { transform: translateY(-1px); border-color: var(--accent-border); }
  .start-card > :first-child { color: var(--accent); }
  .start-card span { display: grid; gap: 0.1rem; min-width: 0; }
  .start-card small { color: var(--text-3); line-height: 1.35; overflow-wrap: anywhere; }
  @media (prefers-reduced-motion: reduce) {
    .start-card { transition: none; }
    .start-card:hover { transform: none; }
  }
  .columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 19rem); gap: var(--space-4); align-items: start; }
  .main-column { display: grid; gap: var(--space-4); min-width: 0; }
  .side-column { display: grid; gap: var(--space-3); }
  .attention-title { margin: 0 0 var(--space-2); font-size: 0.95rem; }
  .board { border-radius: var(--r-lg); }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .card-head h3 { margin: 0; }
  .card-head a { font-size: var(--text-sm); }
  .empty { margin: var(--space-3) 0 0; color: var(--text-3); font-size: var(--text-sm); }
  .notice { margin: 0; color: var(--ok); font-size: var(--text-sm); font-weight: 650; }
  .rows { list-style: none; margin: var(--space-3) 0 0; padding: 0; }
  /* One row: what it is, what state it is in, and the one control that changes
     it. The three parts hold their own columns wide and stack narrow. */
  .rows li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    border-top: 1px solid var(--border);
    padding: var(--row-y) 0;
  }
  .row-main { display: grid; gap: 0.15rem; min-width: 0; }
  .row-main strong { color: var(--text-1); }
  .row-main span { color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .row-meta { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; color: var(--text-3); font-size: var(--text-xs); }
  .kind, .since { white-space: nowrap; }
  .row-actions { display: flex; align-items: center; gap: var(--space-2); }
  .resumes { list-style: none; margin: var(--space-2) 0 0; padding: 0; }
  .resumes li { border-top: 1px solid var(--border); display: grid; gap: 0.15rem; padding: var(--row-y) 0; }
  .resumes li span { font-size: var(--text-xs); color: var(--text-3); }
  @media (max-width: 63.9rem) {
    .columns { grid-template-columns: 1fr; }
    .start-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 40rem) {
    .intro { flex-direction: column; }
    .start-row { grid-template-columns: 1fr; }
    .rows li { grid-template-columns: minmax(0, 1fr); }
    .row-actions { justify-content: flex-start; }
  }
</style>
