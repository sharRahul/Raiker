<script lang="ts">
  /**
   * Workbench — the default screen: a board over the work, opened by a
   * composer that hands its message to Chat (QUI-H01). Home still never sends a
   * prompt itself: the one governed send path is Chat's.
   *
   * It answers "what is Raiker doing right now" in three groups that are three
   * different facts, not three names for the same one:
   *
   *  - **Running now** — a governed cycle in flight this second, with the safe
   *    boundary you can stop it at.
   *  - **Standing agents** — work with a repeating cadence, which re-arms itself
   *    after every cycle and keeps going until stopped.
   *  - **Scheduled runs** — a single future run that has not fired yet.
   *
   * Every row is a task the backend already owns, so the board never invents a
   * state: it reads `GET /api/tasks` and classifies by the recurrence and the
   * scheduled time the runtime itself honours.
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
  import type { AttentionFeedView, BackupView, GoalView } from "../generated/apiContract";
  import { backupReminder } from "../backupReminder";
  import { contract } from "../generated/apiContract";
  import { goalBadge, homeGoalGroups, stepProgress } from "../goalPresentation";
  import Badge from "../components/Badge.svelte";
  import Icon from "../components/Icon.svelte";
  import HomeComposer from "../components/HomeComposer.svelte";
  import { homeFact, homeGreeting, weekOutcomes } from "../homeSummary";
  import { markVersionSeen, versionToAnnounce } from "../whatsNew";
  import PageState from "../components/PageState.svelte";
  import StatTile from "../components/StatTile.svelte";
  import { readinessGaps } from "../readinessGaps";
  import { humanize, relativeFuture, relativeTime } from "../format";
  import { capabilityLabel } from "../capabilityModel";
  import { cadenceLabel } from "../agentCadence";
  import GuideLink from "../components/GuideLink.svelte";
  import { stopRun } from "../taskLifecycle";
  import { haltAction, taskActionLabel } from "../taskPhase";
  // REM-HOME-01 asked a deduplicated row to "link to the canonical Tasks
  // detail", and the dedupe landed without the link because there was no such
  // route. BUG-299 built it; this is the row honouring the promise.
  import { taskDetailHref } from "../taskHistory";
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

  // C18 — "continue working" includes the threads a routine is advancing on
  // its own, not only the conversations the owner typed. One read answers both.
  let sessions = $state<WorkThread[] | null>(null);
  let tasks = $state<TaskView[] | null>(null);
  let approvals = $state<ApprovalView[] | null>(null);
  // DEC-02 — the server's attention feed. Approvals and blocked work keep their
  // own tiles below; the feed adds what has no tile — a proposed memory, a
  // delivery to review, a tool held for review, a containment signal.
  let feed = $state<AttentionFeedView | null>(null);
  let feedFailed = $state(false);
  const TILED_KINDS = new Set(["approvals", "task"]);
  const feedItems = $derived((feed?.items ?? []).filter((item) => !TILED_KINDS.has(item.origin_kind)));
  const feedUnknown = $derived(feedFailed || (feed?.unknown ?? []).length > 0);
  let projects = $state<ProjectsList | null>(null);
  // NEW-HOME-01 — not read yet, read and failed, and nothing to report are
  // three states, never one `null`. A readiness claim nobody checked is worse
  // than no claim, because it is acted on.
  let health = $state<Freshness<Diagnostics>>(freshnessLoading());
  let unavailable = $state(false);
  let updatedAt = $state<Date | null>(null);
  // QUI-H05 — read with the board; `null` until read, so a failed read never
  // recommends a backup the owner may already have.
  let backups = $state<BackupView[] | null>(null);
  const backupNote = $derived(backupReminder(backups, updatedAt ?? new Date()));
  let busyTask = $state<string | null>(null);
  let notice = $state<string | null>(null);
  // BUG-299 — where to look when the runtime could not say what happened.
  let noticeHref = $state<string | null>(null);

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
   * REM-HOME-01 — a standing agent whose cycle is in flight is one row, not two:
   * one piece of work is never counted twice or given two Stop buttons.
   *
   * The cycle wins the row while it is in flight, and it carries the
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
  const named = $derived((sessions ?? []).filter((s) => s.title.trim() !== ""));
  // QUI-H01 — the one thread Home offers to continue: the most recently moved.
  const latestThread = $derived(
    [...named].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))[0] ?? null,
  );
  // QUI-H01 — at most two in-progress cards on Home; the live board has the rest.
  const IN_PROGRESS_ON_HOME = 2;
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
  const gaps = $derived.by(() => {
    const diagnostics = valueOf(health);
    if (diagnostics === null) return [];
    return readinessGaps(diagnostics.missing_config, diagnostics.production_ready_local_single_user_runtime);
  });
  const healthIsCurrent = $derived(isCurrent(health));
  // QUI-H01 — the owner's chosen name, as Chat greets them (RR-IDENTITY-01).
  let ownerName = $state("");
  const greeting = $derived(homeGreeting(ownerName, tasks !== null && !hasActivity, new Date().getHours()));
  const fact = $derived(homeFact((approvals ?? []).length));

  const healthLine = $derived(freshnessLabel(health, "Runtime health"));

  // NEW-HOME-01 — a run that is running is progress, not attention. The rail
  // counted every active task, so a healthy overnight routine made Home look
  // like it had something for the owner, every time they opened it. Only work
  // that will not move again until a person acts belongs here.
  const blocked = $derived(active.filter((task) => isBlockedTask(task.status)));

  // The rail is called "Needs your attention"; when nothing does, it
  // should say so once rather than in three tiles reading zero. Declared after
  // `runtimeIssues` because it reads it: a `$derived` re-runs lazily so the
  // earlier position worked, and named a binding in its own temporal dead zone.
  //
  // NEW-HOME-01 — and it now requires readiness to have actually been read.
  // "Nothing needs you right now" is a claim about three things, and it may
  // only be made when all three were looked at.
  const nothingNeedsAttention = $derived(
    backupNote === null &&
    (approvals ?? []).length === 0 &&
      healthIsCurrent &&
      runtimeIssues === 0 &&
      blocked.length === 0 &&
      // DEC-02 — and the feed was read whole, with nothing in it.
      feed !== null &&
      !feedUnknown &&
      feedItems.length === 0,
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
    backupNote === null &&
    (approvals ?? []).length === 0 && blocked.length === 0 && feedItems.length === 0 && !healthIsCurrent,
  );

  /**
   * NEW-HOME-01 — Home reloads every fifteen seconds, so two reads are
   * routinely in flight at once and the network is free to answer them in
   * either order. Nothing stopped an older response from landing on top of a
   * newer one, which is the same defect a project home had (FIXED-497) and the
   * same fix: each load takes a number, and only the newest one commits.
   */
  let loadSeq = 0;

  let goals = $state<GoalView[]>([]);
  const goalGroups = $derived(homeGoalGroups(goals));
  // QUI-H01 — finished outcomes named, not counted.
  const thisWeek = $derived(weekOutcomes(tasks ?? [], goals, updatedAt ?? new Date(), taskDetailHref));
  const GOAL_GROUPS = [
    { key: "needsYou", title: "Needs you" },
    { key: "moving", title: "In progress" },
    { key: "finished", title: "Finished recently" },
  ] as const;

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
        // PA-D06 — goals are supplementary to the board, like readiness: a
        // failed read leaves the last answer in place rather than erasing it.
        const loadedGoals = await contract.listGoals();
        if (seq !== loadSeq) return;
        goals = Array.isArray(loadedGoals?.goals) ? loadedGoals.goals : [];
      } catch {
        // kept as last read
      }
      try {
        const attention = await api.attention();
        if (seq !== loadSeq) return;
        feed = attention;
        feedFailed = false;
      } catch {
        if (seq !== loadSeq) return;
        feedFailed = true;
      }
      try {
        const listed = await api.backups();
        if (seq !== loadSeq) return;
        backups = Array.isArray(listed?.backups) ? listed.backups : null;
      } catch {
        // kept as last read
      }
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
    noticeHref = null;
    const outcome = await stopRun(task, "stopped from the Workbench board");
    notice = outcome.notice;
    noticeHref = outcome.detailHref ?? null;
    await load();
    busyTask = null;
  }

  /**
   * QUI-H01 — a thread's real next step, from what the runtime reports about
   * it: what it waits on, when a routine runs next, or when it last moved.
   * Never an invented "next".
   */
  function threadNextStep(thread: WorkThread): string {
    if (thread.waiting_on) return `Waiting on ${thread.waiting_on}`;
    if (thread.kind === "routine" && thread.next_run_at) return `Routine · next run ${relativeFuture(thread.next_run_at)}`;
    const place = thread.kind === "routine" ? "Routine · " : thread.project_name ? `${thread.project_name} · ` : "";
    return `${place}${thread.turn_count} turn${thread.turn_count === 1 ? "" : "s"} · updated ${relativeTime(thread.updated_at)}`;
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
  // QUI-H04 — the version to announce, once, after an update.
  let updatedTo = $state<string | null>(null);
  function dismissUpdate() {
    if (updatedTo !== null) markVersionSeen(updatedTo);
    updatedTo = null;
  }

  onMount(() => {
    void api.hostUpdate()
      .then((view) => (updatedTo = versionToAnnounce(view.installation.version)))
      .catch(() => {});
    void api.settings()
      .then((view) => (ownerName = view.status.display_name || view.status.username || ""))
      .catch(() => {});
    void load();
    const timer = window.setInterval(() => void load(), 15_000);
    return () => window.clearInterval(timer);
  });
</script>

<section class="workbench" aria-labelledby="workbench-title">
  <!-- REM-HOME-03 — the next action, before the commentary.
       Home opened with a greeting, a sentence restating counts the boards
       below state exactly, and a platform-state strip, so an owner met three
       rows of Raiker describing itself before the thing they came to do. One
       greeting stays; the counts sentence is gone, because the boards *are*
       the count; the exceptions that change what to do next — a failed read,
       a first run with nothing in it — stay, because those are the cases where
       the page has something to say the boards cannot. The freshness strip and
       the guide link moved below the start row: they are true, and they are
       not the reason anybody opened this page. -->
  <div class="intro">
    <!-- QUI-H01 — a greeting for the owner's time of day, and one fact under
         it only when that fact is true. "Welcome" stays for a first day. -->
    <h2 id="workbench-title" class="display">{greeting}</h2>
    {#if fact !== null}
      <p class="fact"><a href="#/approvals">{fact}</a></p>
    {/if}
    {#if unavailable}
      <p class="lead">Raiker could not read what is running. Nothing was started or changed.</p>
    {/if}
  </div>

  {#if updatedTo !== null}
    <!-- QUI-H04 — one dismissible line after an update; never a modal. -->
    <p class="whats-new" role="status">
      <span>Raiker was updated to {updatedTo}.</span>
      <a href="#/settings?tab=updates" onclick={dismissUpdate}>What's new</a>
      <button type="button" class="btn btn-ghost btn-sm" onclick={dismissUpdate}>Dismiss</button>
    </p>
  {/if}

  <!-- QUI-H01 / QUI-Q02 — the composer replaces the five start cards. They
       repeated the sidebar and the Chat · Build · Design switch; the composer
       starts work in one step and opens it in Chat. QUI-H02 — on a first day
       the four starters sit under it, and nothing else does. -->
  <HomeComposer showStarters={tasks !== null && !hasActivity} />

  <div class="refresh-state">
    <GuideLink route="home" />
    <button class="btn btn-ghost btn-sm" aria-label="Refresh Workbench" type="button" onclick={load}
      title={updatedAt ? `Updated ${relativeTime(updatedAt.toISOString())}` : "Updating…"}>
      <Icon name="refresh" size="sm" />
    </button>
  </div>

  {#if notice}<p class="notice" role="status">
      {notice}
      {#if noticeHref}<a href={noticeHref}>Open its history</a>{/if}
    </p>{/if}

  <div class="columns">
    {#if latestThread !== null}
      <!-- QUI-H01 — the last conversation or routine, and its real next step, as
           one card. The full list is Work → Threads. -->
      <section class="board card continue-card" aria-labelledby="resume-h">
        <div class="card-head">
          <h3 id="resume-h">Continue where you left off</h3>
          {#if named.length > 1}<a href="#/search-chat">All threads ({named.length})</a>{/if}
        </div>
        <div class="continue-row">
          <div class="row-main">
            <a class="row-title" href={`#/new-chat?session=${encodeURIComponent(latestThread.session_id)}`}>{latestThread.title}</a>
            <span>{threadNextStep(latestThread)}</span>
          </div>
          <a class="btn btn-soft btn-sm" href={`#/new-chat?session=${encodeURIComponent(latestThread.session_id)}`}
            aria-label={`Continue ${latestThread.title}`}>Continue</a>
        </div>
      </section>
    {/if}

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
        <!-- "Do not show healthy subsystem status by default." Under a
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
        <!-- "Could not read" is a claim about an answer; while the answer is
             on its way the honest sentence is that it is still being read.
             Neither is an all-clear. -->
        <p class="all-clear">
          No approvals are waiting and no work is blocked.
          {#if health.kind === "loading"}
            Raiker is still reading its own readiness, so this is not an all-clear yet.
          {:else}
            Raiker could not read its own readiness, so this is not an all-clear.
          {/if}
        </p>
        <StatTile
          label="Health check"
          value="—"
          detail={healthLine}
          tone="warn"
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Open diagnostics"
        />
      {:else}
        {#if approvals.length > 0}
          {@const first = approvals[0]}
          <!-- QUI-H01 — one decision row, then View all. Approvals are listed
               in queue order, so the first is the one to take first. -->
          <div class="decision-row" data-testid="home-decision">
            <div class="row-main">
              <strong>{first.tool_name === "ask_owner_question" ? "Answer a question" : `Review ${humanize(first.tool_name).toLowerCase()}`}</strong>
              <span>{capabilityLabel(first.capability)}{first.age_seconds !== null ? ` · waiting ${relativeTime(first.created_at)}` : ""}</span>
            </div>
            <a class="btn btn-soft btn-sm" href="#/approvals">Decide</a>
          </div>
          {#if approvals.length > 1}
            <a class="view-all" href="#/approvals">View all {approvals.length} decisions</a>
          {/if}
        {/if}
        {#if !healthIsCurrent}
        <!-- NEW-HOME-01 — an unread readiness check is its own row, and it
             carries when it was last true. It is not a count, because there is
             no number to give: nobody looked. -->
        <StatTile
          label="Health check"
          value="—"
          detail={healthLine}
          tone="warn"
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Open diagnostics"
        />
        {:else if gaps.length > 0}
        <!-- QUI-Q01 — each gap as a sentence with the action that fixes it.
             This was a "Runtime issues" tile: a large number and a line about
             readiness evidence that named neither the problem nor the fix. -->
        <ul class="feed" aria-label="Setup Raiker still needs">
          {#each gaps as gap (gap.id)}
            <li class="feed-item feed-blocking">
              <strong>{gap.title}</strong>
              <a href={gap.action.href}>{gap.action.label}</a>
            </li>
          {/each}
        </ul>
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
        {#if backupNote !== null}
          <!-- QUI-H05 — a backup is recommended only when there is none or the
               newest is a week old. -->
          <p class="feed-item backup-note">
            <span>{backupNote.text}</span>
            <a href={backupNote.href}>{backupNote.label}</a>
          </p>
        {/if}
        {#if feedItems.length > 0}
          <!-- DEC-02 — each item names what waits and the one place it is
               resolved; it goes when its own subsystem says it is done. -->
          <ul class="feed" aria-label="Also waiting on you">
            {#each feedItems as item (item.id)}
              <li class="feed-item feed-{item.severity}">
                <strong>{item.title}</strong>
                <span>{item.reason}</span>
                <a href={item.href}>{item.action_label}</a>
              </li>
            {/each}
          </ul>
        {/if}
        {#if feedUnknown}
          <p class="all-clear">
            {feedFailed
              ? "Raiker could not read everything that may be waiting on you, so this is not a full list."
              : `Raiker could not read ${(feed?.unknown ?? []).join(", ")}, so this is not a full list.`}
          </p>
        {/if}
      {/if}
    </aside>
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
        <!-- A board that is empty is not a board. Each of these
             three rendered as a full card whatever the state, so a fresh
             install opened on three bordered rectangles saying "Nothing is
             running", "No standing agents" and "Nothing is scheduled" — three
             containers to explain an absence the lead sentence above already
             states in one line. They appear when there is something in them.
             "Continue working" already worked this way; now they all do. -->
        {#if goalGroups.needsYou.length + goalGroups.moving.length + goalGroups.finished.length > 0}
        <section class="board card" aria-labelledby="goals-h" data-testid="home-goals">
          <div class="card-head">
            <h3 id="goals-h">Goals</h3>
            <a href="#/work?tab=goals">All goals</a>
          </div>
          {#each GOAL_GROUPS as group (group.key)}
            {#if goalGroups[group.key].length > 0}
              <h4 class="goal-group">{group.title}</h4>
              <ul class="rows">
                {#each goalGroups[group.key] as goal (goal.goal_id)}
                  {@const badge = goalBadge(goal.status)}
                  <li>
                    <div class="row-main">
                      <a class="row-title" href={`#/work?tab=goals&record=${encodeURIComponent(goal.goal_id)}`}>{goal.title}</a>
                      <span>{goal.reason_text || stepProgress(goal)}</span>
                    </div>
                    <div class="row-meta"><Badge variant={badge.variant} label={badge.label} /></div>
                  </li>
                {/each}
              </ul>
            {/if}
          {/each}
        </section>
        {/if}
        {#if runningNow.length > 0}
        <section class="board card" aria-labelledby="running-h">
          <div class="card-head">
            <h3 id="running-h">Running now</h3>
            <a href="#/observe?tab=work">{runningNow.length > IN_PROGRESS_ON_HOME ? `View all ${runningNow.length}` : "Live board"}</a>
          </div>
            <ul class="rows">
              {#each runningNow.slice(0, IN_PROGRESS_ON_HOME) as task (task.task_id)}
                <li>
                  <div class="row-main">
                    <a class="row-title" href={taskDetailHref(task.task_id)}>{task.title}</a>
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
                    {#if haltAction(task)}
                    {@const halt = haltAction(task) ?? "stop"}
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      disabled={busyTask === task.task_id}
                      onclick={() => void stopTask(task)}
                    >
                      {busyTask === task.task_id ? (halt === "cancel" ? "Cancelling…" : "Stopping…") : taskActionLabel(halt)}
                    </button>
                    {/if}
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
                    <a class="row-title" href={taskDetailHref(task.task_id)}>{task.title}</a>
                    <span>{detail(task)}</span>
                  </div>
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    <span class="kind">{cadenceLabel(task.recurrence ?? "")}</span>
                    {#if task.scheduled_at}<span class="since">next cycle {relativeFuture(task.scheduled_at)}</span>{/if}
                    <span class="since">last moved {relativeTime(task.updated_at)}</span>
                  </div>
                  <div class="row-actions">
                    {#if haltAction(task)}
                    {@const halt = haltAction(task) ?? "stop"}
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      disabled={busyTask === task.task_id}
                      onclick={() => void stopTask(task)}
                    >
                      {busyTask === task.task_id ? (halt === "cancel" ? "Cancelling…" : "Stopping…") : taskActionLabel(halt)}
                    </button>
                    {/if}
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
                    <a class="row-title" href={taskDetailHref(task.task_id)}>{task.title}</a>
                    <span>{detail(task)}</span>
                  </div>
                  <div class="row-meta">
                    <Badge variant={taskBadge(task.status)} label={taskStatusLabel(task.status)} />
                    <span class="kind">fires {relativeFuture(task.scheduled_at ?? task.created_at)}</span>
                  </div>
                  <div class="row-actions">
                    {#if haltAction(task)}
                    {@const halt = haltAction(task) ?? "stop"}
                    <button
                      class="btn btn-ghost btn-sm"
                      type="button"
                      disabled={busyTask === task.task_id}
                      onclick={() => void stopTask(task)}
                    >
                      {busyTask === task.task_id ? (halt === "cancel" ? "Cancelling…" : "Stopping…") : taskActionLabel(halt)}
                    </button>
                    {/if}
                  </div>
                </li>
              {/each}
            </ul>
        </section>
        {/if}

        {#if thisWeek.length > 0}
          <!-- QUI-H01 — the week's finished outcomes, by name. This is where
               the sense of progress lives: what got done, not how many. -->
          <section class="board card week" aria-labelledby="week-h">
            <div class="card-head">
              <h3 id="week-h">This week</h3>
            </div>
            <p class="week-line">
              {#each thisWeek.slice(0, 5) as outcome, index (outcome.id)}{#if index > 0}<span class="sep" aria-hidden="true"> · </span>{/if}<a href={outcome.href}>{outcome.title}</a>{/each}{#if thisWeek.length > 5}<span class="sep" aria-hidden="true"> · </span><span>and {thisWeek.length - 5} more</span>{/if}
            </p>
          </section>
        {/if}
      {/if}
    </div>

  </div>
</section>

<style>
  .goal-group { margin: var(--space-3) 0 0; font-size: var(--text-sm); color: var(--text-2); }
  .workbench { display: grid; gap: var(--space-5); max-width: 61.25rem; }
  .intro { display: grid; gap: var(--space-2); }
  /* BUG-37 — the greeting is display type: Raiker speaking to the owner, not a
     control label. Size, face and tracking come from the shared `.display` rule
     so this page cannot drift from the spec. */
  .intro h2 { margin: 0.15rem 0; }
  .lead { color: var(--text-2); max-width: 62ch; margin: 0; }
  .all-clear { color: var(--text-3); font-size: var(--text-sm); margin: 0; }
  /* Below the start row now: freshness and a guide link are true and are not
     what anybody opened Home for. */
  .refresh-state { display: flex; align-items: center; gap: var(--space-3); color: var(--text-3); font-size: var(--text-sm); flex-wrap: wrap; justify-content: flex-end; margin-top: var(--space-3); }
  /* QUI-H01 — one 980 px column, in the order an owner reads it: continue,
     what needs you, what is in progress, this week, what is coming. */
  .columns { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-4); align-items: start; }
  .continue-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-3); }
  .decision-row {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
    min-height: 4.5rem; padding: var(--space-3); border: 1px solid var(--warn-border);
    border-radius: var(--r-md); background: var(--surface);
  }
  .view-all { font-size: var(--text-sm); justify-self: start; }
  .main-column { display: grid; gap: var(--space-4); min-width: 0; }
  .side-column { display: grid; gap: var(--space-3); }
  .attention-title { margin: 0 0 var(--space-2); font-size: var(--text-md); }
  .board { border-radius: var(--r-lg); }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .card-head h3 { margin: 0; }
  .card-head a { font-size: var(--text-sm); }
  /* A persistent normal state is neutral. Success colour is spent on
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
  /* The row's own title is the link to its attempt history (BUG-299). It keeps
     the weight a title had so the board does not suddenly read as a list of
     links, and underlines on hover so it is discoverable as one. */
  .row-title { color: var(--text-1); font-weight: 600; text-decoration: none; }
  .row-title:hover { text-decoration: underline; }
  .row-main span { color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .row-meta { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; color: var(--text-3); font-size: var(--text-xs); }
  .kind, .since { white-space: nowrap; }
  .row-actions { display: flex; align-items: center; gap: var(--space-2); }
  @media (max-width: 40rem) {
    .intro { flex-direction: column; }
    .rows li { grid-template-columns: minmax(0, 1fr); }
    .row-actions { justify-content: flex-start; }
  }
  .feed { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
  .feed-item {
    display: grid; gap: 0.2rem; padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface);
    font-size: var(--text-sm); min-width: 0; overflow-wrap: anywhere;
  }
  .feed-item span { color: var(--text-2); }
  .feed-containment { border-color: var(--danger-border); }
  .feed-blocking { border-color: var(--warn-border); }
  .fact { margin: 0; font-size: var(--text-sm); }
  .whats-new {
    display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-3);
    margin: 0; padding: var(--space-2) var(--space-3); max-width: 46rem;
    border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface);
    font-size: var(--text-sm); color: var(--text-2);
  }
  .week-line { margin: 0; font-size: var(--text-sm); color: var(--text-2); line-height: 1.6; }
  .week-line .sep { color: var(--text-3); }
</style>
