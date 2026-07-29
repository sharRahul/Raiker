<script lang="ts">
  /**
   * Workbench — the default screen and the start of the common journey.
   *
   * The main column opens with one natural-language composer carrying its own
   * scope: which session the prompt continues, which project bounds it, and
   * which model will serve it. The composer does not send anything itself. It
   * hands the text to the persistently mounted Chat view, which owns the single
   * governed send path, so a prompt started here is identical to one typed
   * there and no governance step is skipped.
   *
   * The secondary column holds only live information worth interrupting for:
   * what is waiting on a decision, what is running, and what can be resumed.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import type {
    ApprovalView,
    Diagnostics,
    ProjectsList,
    SessionSummary,
    TaskView,
  } from "../apiTypes";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import StatTile from "../components/StatTile.svelte";
  import { providerName, relativeTime } from "../format";
  import { isActiveTask } from "../statusMaps";
  import { allProfiles, refreshModels } from "../models.svelte";

  let sessions = $state<SessionSummary[] | null>(null);
  let tasks = $state<TaskView[] | null>(null);
  let approvals = $state<ApprovalView[] | null>(null);
  let projects = $state<ProjectsList | null>(null);
  let diagnostics = $state<Diagnostics | null>(null);
  let unavailable = $state(false);
  // One reactive view of the shared model store; refreshes live when the
  // Models page connects a provider or selects a model, without a remount.
  const profiles = $derived(allProfiles());

  let draft = $state("");
  let continueSession = $state("");
  let handedOff = $state(false);

  const activeTasks = $derived(
    (tasks ?? []).filter((task) => isActiveTask(task.status)),
  );
  const activeProject = $derived(
    projects?.projects.find((project) => project.project_id === projects?.active_project_id) ?? null,
  );
  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);
  const named = $derived((sessions ?? []).filter((s) => (s.title ?? "").trim() !== ""));
  const hasActivity = $derived(named.length > 0 || (tasks ?? []).length > 0 || (projects?.projects ?? []).length > 0);
  const runtimeIssues = $derived(
    diagnostics === null
      ? 0
      : diagnostics.missing_config.length + (diagnostics.production_ready_local_single_user_runtime ? 0 : 1),
  );
  const egressNote = $derived(
    selectedProfile === null
      ? "No model is selected yet, so the runtime will refuse the turn until you choose one."
      : selectedProfile.off_machine
        ? `${providerName(selectedProfile.provider)} runs off this machine — the turn leaves your device and needs its provider gate open.`
        : `${providerName(selectedProfile.provider)} runs locally — the turn stays on this machine.`,
  );

  async function load() {
    unavailable = false;
    try {
      [sessions, tasks, approvals, projects, diagnostics] = await Promise.all([
        // Conversations only — "Resume a conversation" must not offer the
        // server-owned session a task run executes in (BUG-10).
        api.sessions(undefined, false, "chat"),
        api.tasks(),
        api.approvals(),
        api.projects(),
        api.diagnostics(),
      ]);
    } catch {
      unavailable = true;
    }
    // The model summary is supplementary: a failure leaves the previous
    // snapshot in place rather than implying a model is ready when it is not.
    void refreshModels();
  }

  function startWork(event: SubmitEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (text === "") return;
    window.location.hash = continueSession
      ? `#/new-chat?session=${encodeURIComponent(continueSession)}`
      : "#/new-chat";
    // Let the Chat view mount and pick up the session before it receives the
    // text, so the prompt continues the chosen conversation rather than opening
    // a new one.
    window.setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent("raiker:compose", {
          detail: { text, sessionId: continueSession || null },
        }),
      );
    }, 0);
    draft = "";
    handedOff = true;
  }

  onMount(load);
</script>

<section class="workbench" aria-labelledby="workbench-title">
  <div class="intro">
    <div>
      <p class="eyebrow">Workbench</p>
      <h2 id="workbench-title">{hasActivity ? "Pick up where you left off" : "Welcome to your Work Dashboard"}</h2>
      <p class="lead">{hasActivity
        ? "Continue a conversation, start something new, or review what needs your attention."
        : "Start a conversation, organise your work, and track tasks and approvals from one place."}</p>
    </div>
    <button class="btn btn-ghost btn-sm" type="button" onclick={load}>
      <Icon name="refresh" size={15} /> Refresh
    </button>
  </div>

  <div class="columns">
    <div class="main-column">
      <nav class="action-grid" aria-label="Quick actions">
        <a class="action-card primary-action" href="#/new-chat"><Icon name="chat" size={20} /><span><strong>Start a new chat</strong><small>Ask, draft, or work with a file</small></span><Icon name="chevron-right" size={16} /></a>
        <a class="action-card" href="#/projects"><Icon name="projects" size={20} /><span><strong>Create a project</strong><small>Group conversations, files, and instructions</small></span><Icon name="chevron-right" size={16} /></a>
        <a class="action-card" href="#/tasks"><Icon name="tasks" size={20} /><span><strong>Create a task</strong><small>Capture work for Raiker or yourself</small></span><Icon name="chevron-right" size={16} /></a>
        <a class="action-card" href="#/tasks"><Icon name="clock" size={20} /><span><strong>Schedule a task</strong><small>Run once or on a recurring cadence</small></span><Icon name="chevron-right" size={16} /></a>
      </nav>

      <form class="composer card" onsubmit={startWork}>
        <label class="composer-label" for="workbench-prompt">What would you like to do?</label>
        <textarea
          id="workbench-prompt"
          class="textarea prompt"
          rows="4"
          bind:value={draft}
          placeholder="Describe the outcome you want. Raiker asks before anything gated happens."
        ></textarea>

        <div class="scope">
          <label>
            <span class="field-label">Continue</span>
            <select class="select" bind:value={continueSession} aria-label="Conversation to continue">
              <option value="">A new conversation</option>
              {#each named.slice(0, 10) as session (session.session_id)}
                <option value={session.session_id}>{session.title}</option>
              {/each}
            </select>
          </label>
          <div class="scope-fact">
            <span class="field-label">Project scope</span>
            <p>{activeProject?.name ?? "No project — the workspace root"}</p>
          </div>
          <div class="scope-fact">
            <span class="field-label">Model</span>
            <p>
              {selectedProfile
                ? `${selectedProfile.profile_id} · ${selectedProfile.model}`
                : "Not selected"}
            </p>
          </div>
        </div>

        <p class="governed">
          <Icon name="shield" size={14} />
          <span>{egressNote} Anything gated stops for your approval before it runs.</span>
        </p>

        <div class="composer-actions">
          <button class="btn btn-primary" type="submit" disabled={draft.trim() === ""}>
            <Icon name="send" size={15} /> Start work
          </button>
          <a class="btn btn-ghost" href="#/tasks">Plan it as a task instead</a>
        </div>
        {#if handedOff}
          <p class="handoff" role="status">
            Sent to Chat. The conversation and its governed turn continue there.
          </p>
        {/if}
      </form>

      {#if named.length > 0}
      <section class="resumes card" aria-labelledby="resume-h">
        <div class="card-head">
          <h3 id="resume-h">Resume a conversation</h3>
          <a href="#/sessions">All sessions</a>
        </div>
        {#if sessions === null}
          <PageState state="loading" title="Loading your conversations…" />
        {:else}
          <ul>
            {#each named.slice(0, 5) as session (session.session_id)}
              <li>
                <a href={`#/new-chat?session=${encodeURIComponent(session.session_id)}`}>
                  {session.title}
                </a>
                <span>
                  {session.turn_count} turn{session.turn_count === 1 ? "" : "s"} · updated
                  {relativeTime(session.updated_at)}
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </section>
      {/if}
    </div>

    <aside class="side-column" aria-label="Live status">
      {#if unavailable}
        <PageState
          state="error"
          title="Workbench status is unavailable"
          detail="Refresh to retry. No work was started or changed."
        />
      {:else if approvals === null || tasks === null}
        <PageState state="loading" title="Loading status…" />
      {:else}
        <StatTile
          label="Waiting for you"
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
          detail={runtimeIssues === 0 ? "No readiness issue needs attention." : "Review configuration and readiness evidence before critical work."}
          tone={runtimeIssues > 0 ? "warn" : "neutral"}
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="View and flag runtime issues"
        />
        <StatTile
          label="Active work"
          value={activeTasks.length}
          detail={activeTasks.length === 0
            ? "Nothing is queued, running, paused, or waiting for approval."
            : "You can stop any of these at a safe boundary."}
          icon="tasks"
          href="#/observe?tab=work"
          linkLabel="Open the live board"
        />
        <StatTile
          label="Runtime record"
          value="Observe"
          detail="Readiness, the audit log, and notification history in one place."
          icon="diagnostics"
          href="#/observe"
          linkLabel="Open observability"
        />
      {/if}
    </aside>
  </div>
</section>

<style>
  .workbench { display: grid; gap: var(--space-5); }
  .intro { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
  .intro h2 { margin: 0.15rem 0; font-size: clamp(1.4rem, 3vw, 2rem); }
  .lead { color: var(--text-2); max-width: 62ch; margin: 0; }
  .eyebrow {
    color: var(--accent);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin: 0;
  }
  .columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 19rem);
    gap: var(--space-4);
    align-items: start;
  }
  .main-column { display: grid; gap: var(--space-4); min-width: 0; }
  .side-column { display: grid; gap: var(--space-3); }
  .action-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
  .action-card {
    display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center;
    gap: var(--space-3); padding: var(--space-4); color: var(--text-1);
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg);
    box-shadow: var(--shadow-1); text-decoration: none; transition: transform 120ms ease, border-color 120ms ease;
  }
  .action-card:hover { transform: translateY(-1px); border-color: var(--accent-border); }
  .action-card > :first-child { color: var(--accent); }
  .action-card span { display: grid; gap: 0.15rem; }
  .action-card small { color: var(--text-3); line-height: 1.35; }
  .primary-action { background: linear-gradient(135deg, var(--accent-soft), var(--surface)); border-color: var(--accent-border); }
  .composer { display: grid; gap: var(--space-3); padding: var(--space-5); border-radius: var(--r-lg); }
  .composer-label { font-size: 1rem; font-weight: 700; }
  .prompt { min-height: 6rem; font-size: 0.95rem; }
  .scope {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: var(--space-3);
  }
  .scope label { display: grid; gap: 0.1rem; }
  .scope-fact p {
    margin: 0;
    font-size: 0.86rem;
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .governed {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    margin: 0;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
    color: var(--text-2);
    font-size: 0.8rem;
  }
  .composer-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
  .handoff { margin: 0; color: var(--ok); font-size: 0.82rem; font-weight: 600; }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .card-head h3 { margin: 0; }
  .card-head a { font-size: 0.82rem; }
  .resumes { border-radius: var(--r-lg); }
  .resumes ul { list-style: none; margin: var(--space-2) 0 0; padding: 0; }
  .resumes li { border-top: 1px solid var(--border); display: grid; gap: 0.15rem; padding: var(--space-3) 0; }
  .resumes li span { font-size: 0.78rem; color: var(--text-3); }
  @media (max-width: 63.9rem) {
    .columns { grid-template-columns: 1fr; }
  }
  @media (max-width: 40rem) {
    .intro { flex-direction: column; }
    .action-grid { grid-template-columns: 1fr; }
  }
</style>
