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
    TaskView,
    WorkThread,
  } from "../apiTypes";
  import Badge from "../components/Badge.svelte";
  import Icon from "../components/Icon.svelte";
  import { START_WORK } from "../workSurface";
  import PageState from "../components/PageState.svelte";
  import StatTile from "../components/StatTile.svelte";
  import { relativeFuture, relativeTime } from "../format";
  import { cadenceLabel } from "../agentCadence";
  import GuideLink from "../components/GuideLink.svelte";
  import { stopRun } from "../taskLifecycle";
  import { isActiveTask, isBlockedTask, taskBadge, taskStatusLabel } from "../statusMaps";
  import {
    type Freshness,
    failed as freshnessFailed,
    freshnessLabel,
    isCurrent,
    loading as freshnessLoading,
    received,
    valueOf,
  } from "../freshness";

  // C18 — "continue working" used to mean only the conversations the owner
  // typed, so a routine advancing a thread on its own was invisible here and
  // reachable only through Tasks. One read now answers both.
  let sessions = $state<WorkThread[] | null>(null);
  let tasks = $state<TaskView[] | null>(null);
  let approvals = $state<ApprovalView[] | null>(null);
  let projects = $state<ProjectsList | null>(null);
  // NEW-HOME-01 — readiness used to be `Diagnostics | null`, and `null` meant
  // three different things: not read yet, read and failed, and nothing to
  // report. `runtimeIssues` resolved all three to **0**, so a diagnostics
  // endpoint that was down produced a board that said nothing needed the owner.
  // A readiness claim nobody checked is worse than no claim, because it is
  // acted on.
  let health = $state<Freshness<Diagnostics>>(freshnessLoading());
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
  /**
   * REM-HOME-01 — a standing agent whose cycle is in flight is one row, not two.
   *
   * This used to be every repeating task that was still alive, on the reasoning
   * that "a cycle is running" and "an agent is standing" are two different
   * facts and the board should answer both. They are two different facts, and
   * the board still answers both — but it was answering them with the *same
   * row, twice*, under two headings, with two Stop buttons that do the same
   * thing to the same run. An owner scanning Home counted one nightly routine
   * as two pieces of work, and there was nothing on either row to tell them it
   * was not.
   *
   * So the cycle wins the row while it is in flight, and it carries the
   * schedule with it: the running row states the cadence and the next slot, so
   * nothing that was in the standing row is lost. `Standing agents` lists the
   * repeating work that is *waiting* for its next cycle, which is what the
   * heading has always meant to an owner reading it.
   */
  const runningIds = $derived(new Set(runningNow.map((task) => task.task_id)));
  const agents = $derived(
    active.filter((task) => repeats(task) && !runningIds.has(task.task_id)),
  );
  const scheduled = $derived(active.filter((task) => !repeats(task) && armed(task)));
  // Deliberately not "the active project": no route is scoped by one any more.
  // What the board can honestly say is how many projects exist.
  const projectCount = $derived(projects?.projects.length ?? 0);
  const named = $derived((sessions ?? []).filter((s) => s.title.trim() !== ""));
  const hasActivity = $derived(
    named.length > 0 || (tasks ?? []).length > 0 || (projects?.projects ?? []).length > 0,
  );
  // `null` is now *only* "nobody has a current answer", and it is never a zero.
  const runtimeIssues = $derived.by(() => {
    const diagnostics = valueOf(health);
    if (diagnostics === null) return null;
    if (diagnostics.missing_config.length > 0) return diagnostics.missing_config.length;
    return diagnostics.production_ready_local_single_user_runtime ? 0 : 1;
  });
  const healthIsCurrent = $derived(isCurrent(health));
  const healthLine = $derived(freshnessLabel(health, "Runtime health"));

  // NEW-HOME-01 — a run that is running is progress, not attention. The rail
  // counted every active task, so a healthy overnight routine made Home look
  // like it had something for the owner, every time they opened it. Only work
  // that will not move again until a person acts belongs here.
  const blocked = $derived(active.filter((task) => isBlockedTask(task.status)));

  // VIS-13 — the rail is called "Needs your attention"; when nothing does, it
  // should say so once rather than in three tiles reading zero. Declared after
  // `runtimeIssues` because it reads it: a `$derived` re-runs lazily so the
  // earlier position worked, and named a binding in its own temporal dead zone.
  //
  // NEW-HOME-01 — and it now requires readiness to have actually been read.
  // "Nothing needs you right now" is a claim about three things, and it may
  // only be made when all three were looked at.
  const nothingNeedsAttention = $derived(
    (approvals ?? []).length === 0 &&
      healthIsCurrent &&
      runtimeIssues === 0 &&
      blocked.length === 0,
  );

  /**
   * The all-clear, scoped to what was actually read.
   *
   * When readiness could not be read there is still something true and useful
   * to say — the approvals queue and the work board were read, and they are
   * empty — so the page says that and names the gap, rather than choosing
   * between a false all-clear and a blank rail.
   */
  const partialAllClear = $derived(
    (approvals ?? []).length === 0 && blocked.length === 0 && !healthIsCurrent,
  );

  /**
   * NEW-HOME-01 — Home reloads every fifteen seconds, so two reads are
   * routinely in flight at once and the network is free to answer them in
   * either order. Nothing stopped an older response from landing on top of a
   * newer one, which is the same defect a project home had (FIXED-497) and the
   * same fix: each load takes a number, and only the newest one commits.
   */
  let loadSeq = 0;

  async function load() {
    const seq = ++loadSeq;
    try {
      const [loadedSessions, loadedTasks, loadedApprovals, loadedProjects] = await Promise.all([
        // Threads, not sessions: the owner's own conversations plus the
        // threads a routine is advancing (C11/C18). The Inbox — the
        // server-owned session task bookkeeping lands in — is still not
        // something to resume and is still not listed (BUG-10).
        api.workThreads(),
        api.tasks(),
        api.approvals(),
        api.projects(),
      ]);
      if (seq !== loadSeq) return;
      unavailable = false;
      sessions = loadedSessions;
      tasks = loadedTasks;
      approvals = loadedApprovals;
      projects = loadedProjects;
      try {
        const diagnostics = await api.diagnostics();
        if (seq !== loadSeq) return;
        health = received(diagnostics);
      } catch (error) {
        // Readiness is supplementary, and an unavailable diagnostics endpoint
        // must not erase the board — but it must not be quietly reported as a
        // pass either. Whatever was last read survives as stale; a workspace
        // that has never read it says so.
        if (seq !== loadSeq) return;
        health = freshnessFailed(
          health,
          error instanceof ApiError ? `HTTP ${error.status}` : "unreachable",
        );
      }
      updatedAt = new Date();
    } catch {
      if (seq !== loadSeq) return;
      unavailable = true;
    }
  }

  /**
   * Ask one run to stop at its next safe boundary. Never a hard kill.
   *
   * REM-TASK-02 — through the shared controller, so this board, the Tasks page
   * and Build's side panel report the same three outcomes for the same request.
   * The reason string stays local because it is the audit trail's record of
   * *where* the owner pressed it.
   */
  async function stopTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    const outcome = await stopRun(task, "stopped from the Workbench board");
    notice = outcome.notice;
    await load();
    busyTask = null;
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
        <Icon name="refresh" size="sm" /> Refresh
      </button>
    </div>
  </div>

  <!-- The shell calls Chat, Build and Design three peer Work modes; this row
       listed two of them beside Tasks and Projects and left Design out, so the
       first screen an owner sees disagreed with the product it opens onto. The
       three modes come first, as peers, from the same list the rest of the
       product reads (`workSurface.ts`); the two workflow entries follow, which
       is what they are. -->
  <nav class="start-row" aria-label="Start work">
    {#each START_WORK as entry (entry.mode)}
      <a class="start-card" href={entry.route}>
        <Icon name={entry.icon} size="md" />
        <span><strong>{entry.title}</strong><small>{entry.detail}</small></span>
      </a>
    {/each}
  </nav>
  <nav class="start-row secondary" aria-label="Organise work">
    <a class="start-card" href="#/tasks">
      <Icon name="tasks" size="md" /><span><strong>Plan a task or agent</strong><small>Run once, on a cadence, or in the background</small></span>
    </a>
    <a class="start-card" href="#/projects">
      <Icon name="projects" size="md" /><span><strong>Open a project</strong><small>{projectCount === 0 ? "None yet" : `${projectCount} project${projectCount === 1 ? "" : "s"}`}</small></span>
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
        <!-- VIS-13/VIS-05 — a board that is empty is not a board. Each of these
             three rendered as a full card whatever the state, so a fresh
             install opened on three bordered rectangles saying "Nothing is
             running", "No standing agents" and "Nothing is scheduled" — three
             containers to explain an absence the lead sentence above already
             states in one line. They appear when there is something in them.
             "Continue working" already worked this way; now they all do. -->
        {#if runningNow.length > 0}
        <section class="board card" aria-labelledby="running-h">
          <div class="card-head">
            <h3 id="running-h">Running now</h3>
            <a href="#/observe?tab=work">Live board</a>
          </div>
            <ul class="rows">
              {#each runningNow as task (task.task_id)}
                <li>
                  <div class="row-main">
                    <strong>{task.title}</strong>
                    <span>{detail(task)}</span>
                  </div>
                  <!-- REM-HOME-01 — the schedule travels with the attempt.
                       A repeating task is only in this section while a cycle is
                       actually running, so its cadence and next slot have to be
                       here or they would be the thing the dedupe lost. -->
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    {#if task.recurrence}<span class="kind">{cadenceLabel(task.recurrence)}</span>{/if}
                    <span class="since">this cycle started {relativeTime(task.created_at)}</span>
                    {#if repeats(task) && task.scheduled_at}
                      <span class="since">next cycle {relativeFuture(task.scheduled_at)}</span>
                    {/if}
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
        </section>
        {/if}

        {#if agents.length > 0}
        <section class="board card" aria-labelledby="agents-h">
          <div class="card-head">
            <h3 id="agents-h">Standing agents</h3>
            <a href="#/tasks">Manage agents</a>
          </div>
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
                    {#if task.scheduled_at}<span class="since">next cycle {relativeFuture(task.scheduled_at)}</span>{/if}
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
        </section>
        {/if}

        {#if scheduled.length > 0}
        <section class="board card" aria-labelledby="scheduled-h">
          <div class="card-head">
            <h3 id="scheduled-h">Scheduled runs</h3>
            <a href="#/tasks">Manage schedules</a>
          </div>
            <ul class="rows">
              {#each scheduled as task (task.task_id)}
                <li>
                  <div class="row-main">
                    <strong>{task.title}</strong>
                    <span>{detail(task)}</span>
                  </div>
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    <span class="kind">fires {relativeFuture(task.scheduled_at ?? task.created_at)}</span>
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
        </section>
        {/if}

        {#if named.length > 0}
          <section class="board card" aria-labelledby="resume-h">
            <div class="card-head">
              <h3 id="resume-h">Continue working</h3>
              <a href="#/search-chat">All threads</a>
            </div>
            <ul class="resumes">
              {#each named.slice(0, 5) as session (session.session_id)}
                <li>
                  <a href={`#/new-chat?session=${encodeURIComponent(session.session_id)}`}>{session.title}</a>
                  <span>
                    {#if session.kind === "routine"}Routine · {/if}{#if session.project_name}{session.project_name}
                      · {/if}{session.turn_count} turn{session.turn_count === 1 ? "" : "s"} · updated
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
      {:else if nothingNeedsAttention}
        <!-- VIS-13 — "Do not show healthy subsystem status by default." Under a
             heading that says *Needs your attention*, three tiles reading 0 are
             a report that there is nothing to report, and they were the largest
             thing on an idle Home. One line instead, and each tile comes back
             the moment its own count is not zero. -->
        <p class="all-clear">Nothing needs you right now.</p>
      {:else if partialAllClear}
        <!-- NEW-HOME-01 — the same rail when readiness could not be read. Two
             of the three things were looked at and both are clear; the third
             is named rather than counted as zero, which is what turned a
             failed read into "Nothing needs you right now." -->
        <p class="all-clear">
          No approvals are waiting and no work is blocked. Raiker could not read
          its own runtime readiness, so this is not an all-clear.
        </p>
        <StatTile
          label="Runtime health"
          value="—"
          detail={healthLine}
          tone="warn"
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Open diagnostics"
        />
      {:else}
        {#if approvals.length > 0}
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
        {/if}
        {#if !healthIsCurrent}
        <!-- NEW-HOME-01 — an unread readiness check is its own row, and it
             carries when it was last true. It is not a count, because there is
             no number to give: nobody looked. -->
        <StatTile
          label="Runtime health"
          value="—"
          detail={healthLine}
          tone="warn"
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Open diagnostics"
        />
        {:else if runtimeIssues !== null && runtimeIssues > 0}
        <StatTile
          label="Runtime issues"
          value={runtimeIssues}
          detail="Review configuration and readiness evidence before critical work."
          tone="warn"
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Review issues"
        />
        {/if}
        {#if blocked.length > 0}
        <!-- NEW-HOME-01 — blocked work, not all work. Every running task used
             to appear here, so a healthy overnight routine put Home permanently
             in a state that said something needed the owner; the board below
             already lists running work, with the same Stop control. What is
             left here is the work that will not move again until they act. -->
        <StatTile
          label="Blocked work"
          value={blocked.length}
          detail={blocked.length === 1
            ? "One run is paused or waiting for your decision."
            : "These runs are paused or waiting for your decision."}
          tone="warn"
          icon="tasks"
          href="#/observe?tab=work"
          linkLabel="Open the live board"
        />
        {/if}
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
  .all-clear { color: var(--text-3); font-size: var(--text-sm); margin: 0; }
  .refresh-state { display: flex; align-items: center; gap: var(--space-3); color: var(--text-3); font-size: var(--text-sm); flex-wrap: wrap; justify-content: flex-end; }
  /* Starting work is a link to the surface that owns the composer, so the board
     never becomes a second send path. */
  /* Three peer Work modes on the first row; the two workflow entries on a
     second, quieter one. Peers share a row; a secondary thing does not sit in
     the same rhythm as the thing it is secondary to. */
  .start-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
  .start-row.secondary { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: var(--space-3); }
  .start-row.secondary .start-card { padding: var(--space-2) var(--space-3); }
  .start-row.secondary strong { font-weight: 600; }
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
  .attention-title { margin: 0 0 var(--space-2); font-size: var(--text-md); }
  .board { border-radius: var(--r-lg); }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .card-head h3 { margin: 0; }
  .card-head a { font-size: var(--text-sm); }
  /* VIS2-16 — a persistent normal state is neutral. Success colour is spent on
     something that just happened or on a decision that was just confirmed; used
     as the standing representation of "connected", "enabled", "verified" or
     "ready" it is on screen constantly, which is the one condition under which
     a colour stops carrying information. Exceptions keep their tone. */
  .notice { margin: 0; color: var(--text-2); font-size: var(--text-sm); font-weight: 650; }
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
