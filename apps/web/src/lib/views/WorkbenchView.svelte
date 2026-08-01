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
  import ComposerAttach from "../components/ComposerAttach.svelte";
  import ComposerAttachPanel from "../components/ComposerAttachPanel.svelte";
  import ComposerChips from "../components/ComposerChips.svelte";
  import { createAttachmentStore } from "../composerAttachments.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ModelPicker from "../components/ModelPicker.svelte";
  import StatTile from "../components/StatTile.svelte";
  import { relativeTime } from "../format";
  import { isActiveTask } from "../statusMaps";
  import { chatProfiles, refreshModels } from "../models.svelte";

  let sessions = $state<SessionSummary[] | null>(null);
  let tasks = $state<TaskView[] | null>(null);
  let approvals = $state<ApprovalView[] | null>(null);
  let projects = $state<ProjectsList | null>(null);
  let diagnostics = $state<Diagnostics | null>(null);
  let unavailable = $state(false);
  // One reactive view of the shared model store; refreshes live when the
  // Models page connects a provider or selects a model, without a remount.
  const profiles = $derived(chatProfiles());

  // The Workbench composer carries files too, and hands their references to
  // whichever surface actually runs the work. It used to say "to work with a
  // file, start in Chat and attach it there", which was true and was also an
  // admission that this composer was a lesser one.
  const attachStore = createAttachmentStore();
  let attachControl = $state<ComposerAttach | undefined>();
  let attachOpen = $state(false);
  // Schedule mode needs a time. Without one the handoff landed in Tasks with an
  // empty, required start field and the owner had to notice and fill it in.
  let scheduleAt = $state("");

  let draft = $state("");
  let continueSession = $state("");
  let handedOff = $state(false);
  let workMode = $state<"chat" | "build" | "task" | "schedule">("build");
  let chatProfile = $state("");
  let chatModel = $state("");
  let buildProfile = $state("");
  let buildModel = $state("");
  let taskProfile = $state("");
  let taskModel = $state("");
  let updatedAt = $state<Date | null>(null);

  const activeTasks = $derived(
    (tasks ?? []).filter((task) => isActiveTask(task.status)),
  );
  const activeProject = $derived(
    projects?.projects.find((project) => project.project_id === projects?.active_project_id) ?? null,
  );
  const selectedProfile = $derived(profiles.find((profile) => profile.selected) ?? null);
  const chosenProfile = $derived(
    workMode === "chat" ? chatProfile : workMode === "build" ? buildProfile : workMode === "task" ? taskProfile : "",
  );
  const chosenModel = $derived(
    workMode === "chat" ? chatModel : workMode === "build" ? buildModel : workMode === "task" ? taskModel : "",
  );
  const effectiveModel = $derived(
    profiles.find((profile) => profile.profile_id === chosenProfile && profile.model === chosenModel) ?? selectedProfile,
  );
  const named = $derived((sessions ?? []).filter((s) => (s.title ?? "").trim() !== ""));
  const hasActivity = $derived(named.length > 0 || (tasks ?? []).length > 0 || (projects?.projects ?? []).length > 0);
  const runtimeIssues = $derived(
    diagnostics === null
      ? 0
      : diagnostics.missing_config.length > 0
        ? diagnostics.missing_config.length
        : diagnostics.production_ready_local_single_user_runtime ? 0 : 1,
  );
  const primaryLabel = $derived(workMode === "chat" ? "Start conversation" : workMode === "task" ? "Create task" : workMode === "schedule" ? "Review schedule" : "Start build");

  async function load() {
    unavailable = false;
    try {
      [sessions, tasks, approvals, projects] = await Promise.all([
        // Conversations only — "Resume a conversation" must not offer the
        // server-owned session a task run executes in (BUG-10).
        api.sessions(undefined, false, "chat"),
        api.tasks(),
        api.approvals(),
        api.projects(),
      ]);
      try {
        diagnostics = await api.diagnostics();
      } catch {
        // Readiness is supplementary; an older or temporarily unavailable
        // diagnostics endpoint must not erase conversations and tasks.
        diagnostics = null;
      }
      updatedAt = new Date();
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
    if (text === "" || effectiveModel === null) return;
    if (workMode === "task" || workMode === "schedule") {
      window.location.hash = "#/tasks";
      window.setTimeout(() => window.dispatchEvent(new CustomEvent("raiker:task-compose", {
        detail: {
          text,
          cadence: workMode === "schedule" ? "once" : "now",
          scheduledAt: workMode === "schedule" ? scheduleAt : "",
          profileId: workMode === "task" ? effectiveModel.profile_id : null,
          model: workMode === "task" ? effectiveModel.model : null,
        },
      })), 0);
      draft = "";
      handedOff = true;
      return;
    }
    const attachments = attachStore.take();
    if (workMode === "build") {
      window.location.hash = "#/build";
      window.setTimeout(() => window.dispatchEvent(new CustomEvent("raiker:build-compose", {
        detail: { text, profileId: effectiveModel.profile_id, model: effectiveModel.model, attachments },
      })), 0);
      draft = "";
      attachStore.clear();
      handedOff = true;
      return;
    }
    window.location.hash = continueSession
      ? `#/new-chat?session=${encodeURIComponent(continueSession)}`
      : "#/new-chat";
    // Let the Chat view mount and pick up the session before it receives the
    // text, so the prompt continues the chosen conversation rather than opening
    // a new one.
    window.setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent("raiker:compose", {
          detail: { text, sessionId: continueSession || null, profileId: effectiveModel.profile_id, model: effectiveModel.model, attachments },
        }),
      );
    }, 0);
    draft = "";
    attachStore.clear();
    handedOff = true;
  }

  onMount(load);
</script>

<svelte:window onclick={(event) => attachControl?.handleOutsideClick(event)} />

<section class="workbench" aria-labelledby="workbench-title">
  <div class="intro">
    <div>
      <h2 id="workbench-title">{hasActivity ? "Welcome back" : "Welcome to your Work Dashboard"}</h2>
      <p class="lead">{hasActivity
        ? `You have ${activeTasks.length} active item${activeTasks.length === 1 ? "" : "s"} and ${approvals?.length ?? 0} approval${approvals?.length === 1 ? "" : "s"}.`
        : "Start a conversation, create a project, or plan your first task."}</p>
    </div>
    <div class="refresh-state"><span aria-live="polite">{updatedAt ? "Updated just now" : "Updating…"}</span><button class="btn btn-ghost btn-sm" aria-label="Refresh Workbench" type="button" onclick={load}><Icon name="refresh" size={15} /> Refresh</button></div>
  </div>

  <div class="columns">
    <div class="main-column">
      <form class="composer card" onsubmit={startWork}>
        <label class="composer-label" for="workbench-prompt">What would you like Raiker to do?</label>
        <p class="composer-help">Describe an outcome or ask a question. Attach a workspace file, an image, or a document and it rides along to wherever the work runs.</p>
        <div class="mode-tabs" role="tablist" aria-label="Work mode">
          {#each [["chat", "Chat"], ["build", "Build"], ["task", "Create task"], ["schedule", "Schedule"]] as option}
            <button type="button" role="tab" aria-selected={workMode === option[0]} class:active={workMode === option[0]} onclick={() => (workMode = option[0] as typeof workMode)}>{option[1]}</button>
          {/each}
        </div>
        <ComposerChips store={attachStore} />
        <textarea id="workbench-prompt" class="textarea prompt" rows="4" bind:value={draft} placeholder="Ask a question or describe an outcome…"></textarea>
        <div class="scope">
          <!-- Continuing an existing conversation only means anything for Chat:
               Build starts its own workspace conversation, and a task runs in a
               server-owned session. Offering the control in those modes would
               promise a continuation that silently does not happen. -->
          {#if workMode === "chat"}
            <label><span class="field-label">Start as</span><select class="select" bind:value={continueSession} aria-label="Conversation to continue"><option value="">New conversation</option>{#each named.slice(0, 10) as session (session.session_id)}<option value={session.session_id}>{session.title}</option>{/each}</select></label>
          {:else if workMode === "schedule"}
            <label><span class="field-label">Start time</span><input class="input" type="datetime-local" bind:value={scheduleAt} aria-label="Scheduled start time" /></label>
          {:else}
            <div class="scope-fact"><span class="field-label">Start as</span><p>{workMode === "build" ? "A new build conversation" : workMode === "task" ? "A task run" : "A scheduled run"}</p></div>
          {/if}
          <div class="scope-fact"><span class="field-label">Project</span><p>{activeProject?.name ?? "No project"}</p></div>
          <div><span class="field-label">Model</span>{#if workMode === "chat"}<ModelPicker {profiles} {selectedProfile} bind:profileId={chatProfile} bind:model={chatModel} />{:else if workMode === "build"}<ModelPicker {profiles} {selectedProfile} bind:profileId={buildProfile} bind:model={buildModel} />{:else if workMode === "task"}<ModelPicker {profiles} {selectedProfile} bind:profileId={taskProfile} bind:model={taskModel} />{:else}<p class="global-model">Global at run time — {selectedProfile?.model ?? "not selected"}</p>{/if}</div>
        </div>
        {#if effectiveModel === null}<p class="model-error" role="alert"><strong>A model is required before work can start.</strong> <a href="#/models">Choose a model</a> or ask an administrator.</p>{/if}
        <details class="governed"><summary><Icon name="shield" size={14} /> Governed execution</summary><p>Raiker requests your approval before restricted external actions. Project boundaries and connected-tool policies still apply.</p></details>
        {#if attachOpen}
          <ComposerAttachPanel store={attachStore} idPrefix="workbench" />
        {/if}
        <div class="composer-actions">
          <ComposerAttach bind:this={attachControl} bind:open={attachOpen} />
          <button class="btn btn-primary" type="submit" disabled={draft.trim() === "" || effectiveModel === null}><Icon name="send" size={15} /> {primaryLabel}</button>
        </div>
        {#if handedOff}<p class="handoff" role="status">{workMode === "build" ? "Sent to Build. Review and start the governed build there." : workMode === "task" ? "Sent to Tasks. Review and create the task there." : workMode === "schedule" ? "Sent to Tasks. Review the schedule and create it there." : "Sent to Chat. The conversation and its governed turn continue there."}</p>{/if}
      </form>

      <div><h3 class="block-title">Quick actions</h3><nav class="action-grid" aria-label="Quick actions">
        <a class="action-card" href="#/projects"><Icon name="projects" size={20} /><span><strong>Create a project</strong><small>Group conversations, files, and instructions</small></span><Icon name="chevron-right" size={16} /></a>
        <a class="action-card" href="#/new-chat"><Icon name="file" size={20} /><span><strong>Upload or review a file</strong><small>Work with a document in a conversation</small></span><Icon name="chevron-right" size={16} /></a>
        <a class="action-card" href="#/tasks"><Icon name="tasks" size={20} /><span><strong>Create a task</strong><small>Capture work for Raiker or yourself</small></span><Icon name="chevron-right" size={16} /></a>
        <a class="action-card" href="#/tasks"><Icon name="clock" size={20} /><span><strong>Schedule work</strong><small>Run work once or on a recurring cadence</small></span><Icon name="chevron-right" size={16} /></a>
      </nav></div>

      {#if named.length > 0}
      <section class="resumes card" aria-labelledby="resume-h">
        <div class="card-head">
          <h3 id="resume-h">Continue working</h3>
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

    <aside class="side-column" aria-label="Needs your attention"><h3 class="attention-title">Needs your attention</h3>
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
          detail={runtimeIssues === 0 ? "No readiness issue needs attention." : "Review configuration and readiness evidence before critical work."}
          tone={runtimeIssues > 0 ? "warn" : "neutral"}
          icon="diagnostics"
          href="#/observe?tab=diagnostics"
          linkLabel="Review issues"
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
      {/if}
    </aside>
  </div>
</section>

<style>
  .workbench { display: grid; gap: var(--space-5); }
  .intro { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
  .intro h2 { margin: 0.15rem 0; font-size: clamp(1.4rem, 3vw, 2rem); }
  .lead { color: var(--text-2); max-width: 62ch; margin: 0; }
  .refresh-state { display: flex; align-items: center; gap: var(--space-2); color: var(--text-3); font-size: .78rem; }
  .columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 19rem);
    gap: var(--space-4);
    align-items: start;
  }
  .main-column { display: grid; gap: var(--space-4); min-width: 0; }
  .side-column { display: grid; gap: var(--space-3); }
  .attention-title, .block-title { margin: 0 0 var(--space-2); font-size: .95rem; }
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
  .composer { display: grid; gap: var(--space-3); padding: clamp(1.25rem, 3vw, 2rem); border-radius: var(--r-lg); border-color: var(--accent-border); box-shadow: var(--shadow-2); }
  .composer-label { font-size: 1rem; font-weight: 700; }
  .composer-help { color: var(--text-2); margin: -.5rem 0 0; font-size: .85rem; }
  .mode-tabs { display: flex; gap: .25rem; overflow-x: auto; border-bottom: 1px solid var(--border); }
  .mode-tabs button { min-height: 44px; padding: 0 .75rem; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--text-2); font: inherit; font-weight: 600; white-space: nowrap; cursor: pointer; }
  .mode-tabs button.active { color: var(--accent); border-bottom-color: var(--accent); }
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
    margin: 0;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--sunken);
    color: var(--text-2);
    font-size: 0.8rem;
  }
  .governed summary { display: flex; align-items: center; gap: .45rem; cursor: pointer; font-weight: 650; color: var(--text-1); }
  .governed p { margin: .5rem 0 0 1.25rem; }
  .model-error { margin: 0; padding: .65rem .8rem; border-radius: var(--r-md); background: var(--danger-soft); color: var(--danger); font-size: .82rem; }
  .composer-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
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
