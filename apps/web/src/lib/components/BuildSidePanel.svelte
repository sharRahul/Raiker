<script lang="ts">
  /**
   * The Build workspace's right rail: what is running in the background, and
   * how to start something that keeps running.
   *
   * It is deliberately a *rail*, not a modal — background work is context for
   * the conversation beside it, so it stays legible while you keep typing, and
   * the toggle in the header collapses it when the transcript needs the room.
   * Below the split-view breakpoint a side-by-side column stops being readable,
   * so it becomes a full-width section under the composer instead.
   *
   * Nothing here is a new authority. Tasks come from the same governed
   * `/api/tasks` surface as the Tasks page, stopping one is the same
   * safe-boundary interrupt, and a scheduled agent is a task with a cadence:
   * each cycle is one discrete governed turn that passes through policy, gates,
   * and approvals exactly like a prompt typed by hand.
   */
  import Badge from "./Badge.svelte";
  import EmptyState from "./EmptyState.svelte";
  import Icon from "./Icon.svelte";
  import PageState from "./PageState.svelte";
  import { api, ApiError } from "../api";
  import type { ProjectsList, TaskView } from "../apiTypes";
  import { relativeTime } from "../format";
  import { AGENT_CADENCES, cadenceLabel } from "../agentCadence";
  import { isActiveTask, taskBadge } from "../statusMaps";

  let {
    projectId = null,
    projects = null,
    onclose,
  }: {
    projectId?: string | null;
    projects?: ProjectsList | null;
    onclose: () => void;
  } = $props();

  type PanelTab = "running" | "agents";
  let tab = $state<PanelTab>("running");

  let tasks = $state<TaskView[] | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busyTask = $state<string | null>(null);

  // Scheduled agent form.
  let title = $state("");
  let instructions = $state("");
  let cadence = $state("continuous");
  let firstRunAt = $state("");
  let agentProjectId = $state("");
  let creating = $state(false);

  const running = $derived(
    (tasks ?? []).filter((task) => isActiveTask(task.status)),
  );
  const standing = $derived(running.filter((task) => task.recurrence));
  const finished = $derived(
    (tasks ?? []).filter((task) => !isActiveTask(task.status)).slice(0, 6),
  );

  async function load() {
    try {
      loadError = null;
      tasks = await api.tasks(projectId ? { project_id: projectId } : {});
    } catch (error) {
      tasks = null;
      loadError =
        error instanceof ApiError ? `Background work unavailable (${error.status}).` : "Background work unavailable.";
    }
  }

  async function stopTask(task: TaskView) {
    busyTask = task.task_id;
    notice = null;
    try {
      await api.interrupt({
        session_id: task.session_id,
        task_id: task.task_id,
        action_type: "cancel",
        reason: "stopped from the Build workspace",
      });
      notice = `Asked “${task.title}” to stop at its next safe boundary.`;
      await load();
    } catch {
      notice = "Could not request the stop.";
    } finally {
      busyTask = null;
    }
  }

  async function createAgent() {
    if (!title.trim() || !instructions.trim()) return;
    creating = true;
    notice = null;
    try {
      await api.createTask({
        title: title.trim(),
        description: instructions.trim(),
        recurrence: cadence,
        ...(firstRunAt && cadence !== "background"
          ? { scheduled_at: new Date(firstRunAt).toISOString() }
          : {}),
        ...(agentProjectId ? { project_id: agentProjectId } : projectId ? { project_id: projectId } : {}),
      });
      title = "";
      instructions = "";
      notice = firstRunAt && cadence !== "background"
        ? `Agent scheduled. Its first cycle starts ${new Date(firstRunAt).toLocaleString()}.`
        : "Agent scheduled. Its first cycle starts on the next scheduler tick.";
      firstRunAt = "";
      tab = "running";
      await load();
    } catch (error) {
      notice =
        error instanceof ApiError
          ? `Could not schedule the agent (${error.reasonCode ?? error.status}).`
          : "Could not schedule the agent.";
    } finally {
      creating = false;
    }
  }

  /** Prefill from an example so the shape of a good instruction is obvious. */
  function useExample(exampleTitle: string, exampleInstructions: string) {
    title = exampleTitle;
    instructions = exampleInstructions;
  }

  function scheduleLine(task: TaskView): string {
    if (task.recurrence) return cadenceLabel(task.recurrence);
    if (task.scheduled_at) return `Scheduled for ${new Date(task.scheduled_at).toLocaleString()}`;
    return "Runs on the next tick";
  }

  $effect(() => {
    void projectId;
    void load();
  });
</script>

<aside class="rail" aria-label="Background work">
  <header>
    <div class="tabs" role="tablist" aria-label="Background work views">
      <button
        type="button"
        role="tab"
        id="build-tab-running"
        aria-selected={tab === "running"}
        aria-controls="build-panel-running"
        onclick={() => (tab = "running")}
      >
        Running
        {#if running.length > 0}<span class="count">{running.length}</span>{/if}
      </button>
      <button
        type="button"
        role="tab"
        id="build-tab-agents"
        aria-selected={tab === "agents"}
        aria-controls="build-panel-agents"
        onclick={() => (tab = "agents")}
      >
        Agents
      </button>
    </div>
    <div class="header-actions">
      <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh background work">
        <Icon name="refresh" size="sm" />
      </button>
      <button type="button" class="btn btn-ghost btn-sm" onclick={onclose} aria-label="Hide background work">
        <Icon name="x" size="sm" />
      </button>
    </div>
  </header>

  {#if notice}<p class="notice" role="status">{notice}</p>{/if}

  {#if tab === "running"}
    <div id="build-panel-running" role="tabpanel" aria-labelledby="build-tab-running" class="panel">
      {#if loadError}
        <section class="load-error" role="status">
          <strong>Couldn't read background work</strong>
          <span>{loadError}</span>
        </section>
      {:else if tasks === null}
        <PageState state="loading" title="Loading background work…" />
      {:else if running.length === 0}
        <EmptyState
          icon="clock"
          title="Nothing running"
          body="Schedule an agent and its cycles will appear here beside the conversation."
        />
      {:else}
        {#if standing.length > 0}
          <p class="rail-lead">
            {standing.length === 1 ? "1 standing agent" : `${standing.length} standing agents`} — each cycle is one
            governed turn, and stopping happens at a safe boundary.
          </p>
        {/if}
        <ul class="task-list">
          {#each running as task (task.task_id)}
            <li class="task">
              <div class="task-head">
                <span class="task-title">{task.title}</span>
                <Badge variant={taskBadge(task.status)} label={task.status} />
              </div>
              {#if task.current_step}<p class="step">{task.current_step}</p>{/if}
              {#if task.progress_percent !== null && task.progress_percent !== undefined}
                <div
                  class="progress"
                  role="progressbar"
                  aria-label={`${task.title} progress`}
                  aria-valuenow={task.progress_percent}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  <div style={`width:${task.progress_percent}%`}></div>
                </div>
              {/if}
              <footer>
                <span>{scheduleLine(task)} · {relativeTime(task.updated_at)}</span>
                {#if task.status === "waiting_for_approval"}
                  <a class="btn btn-primary btn-sm" href={`#/approvals?session=${encodeURIComponent(task.session_id)}`}>
                    Review approval
                  </a>
                {/if}
                <button
                  type="button"
                  class="btn btn-ghost btn-sm"
                  onclick={() => stopTask(task)}
                  disabled={busyTask === task.task_id}
                >
                  {busyTask === task.task_id ? "Stopping…" : "Stop"}
                </button>
              </footer>
            </li>
          {/each}
        </ul>
      {/if}

      {#if finished.length > 0}
        <section class="recent" aria-labelledby="build-recent">
          <h3 id="build-recent">Recently finished</h3>
          <ul>
            {#each finished as task (task.task_id)}
              <li>
                <span class="task-title">{task.title}</span>
                <Badge variant={taskBadge(task.status)} label={task.status} />
              </li>
            {/each}
          </ul>
        </section>
      {/if}
    </div>
  {:else}
    <div id="build-panel-agents" role="tabpanel" aria-labelledby="build-tab-agents" class="panel">
      <p class="rail-lead">
        A scheduled agent keeps working while you are away — building something out, or watching something and
        reporting back. Every cycle is one governed turn: it can be stopped, and anything above the safe floor still
        waits for you.
      </p>

      <form
        class="agent-form"
        onsubmit={(event) => {
          event.preventDefault();
          void createAgent();
        }}
      >
        <label>
          Name
          <input class="input" bind:value={title} maxlength="240" placeholder="What is this agent for?" required />
        </label>
        <label>
          Instructions
          <textarea
            class="textarea"
            bind:value={instructions}
            rows="4"
            placeholder="Describe the outcome, the constraints, and when to stop."
            required
          ></textarea>
        </label>
        <label>
          Cadence
          <select class="select" bind:value={cadence} aria-label="Cadence">
            {#each AGENT_CADENCES as option (option.id)}
              <option value={option.id}>{option.label}</option>
            {/each}
          </select>
        </label>
        <p class="cadence-detail">{AGENT_CADENCES.find((option) => option.id === cadence)?.detail}</p>
        <!-- Backlog #10 — a recurring agent anchors every later cycle to its
             first run, so without this the anchor was whenever the owner
             happened to press the button. Optional: left empty it still starts
             now, which is what a "keep going" agent usually wants. -->
        {#if cadence !== "background"}
          <label>
            First run
            <input class="input" type="datetime-local" bind:value={firstRunAt} aria-label="First run" />
          </label>
        {/if}
        {#if projects && projects.projects.length > 0}
          <label>
            Project
            <select class="select" bind:value={agentProjectId} aria-label="Project for this agent">
              <option value="">{projectId ? "Active project" : "No project"}</option>
              {#each projects.projects as project (project.project_id)}
                <option value={project.project_id}>{project.name}</option>
              {/each}
            </select>
          </label>
        {/if}
        <button class="btn btn-primary" disabled={creating || !title.trim() || !instructions.trim()}>
          {creating ? "Scheduling…" : "Schedule agent"}
        </button>
      </form>

      <section class="examples" aria-labelledby="build-examples">
        <h3 id="build-examples">Start from an example</h3>
        <button
          type="button"
          class="example"
          onclick={() =>
            useExample(
              "Surprise me",
              "Build one small, self-contained app in this workspace. Pick the idea yourself, keep it to a handful of files, and finish each cycle with a working version and a short note on what changed.",
            )}
        >
          <strong>Surprise me by building a small app</strong>
          <span>Picks its own idea and ships a working version each cycle.</span>
        </button>
        <button
          type="button"
          class="example"
          onclick={() =>
            useExample(
              "Keep the site improving",
              "Review the site in this repository once per cycle. Make one focused improvement — accessibility, performance, or copy — and explain what you changed and why.",
            )}
        >
          <strong>Keep improving the site</strong>
          <span>One focused improvement per cycle, with the reasoning.</span>
        </button>
        <button
          type="button"
          class="example"
          onclick={() =>
            useExample(
              "Watch the test suite",
              "Run the test suite in this repository. If anything fails, summarise the failure and propose the smallest fix. If everything passes, say so briefly and stop.",
            )}
        >
          <strong>Watch the test suite</strong>
          <span>Reports failures and proposes the smallest fix.</span>
        </button>
      </section>
    </div>
  {/if}
</aside>

<style>
  .rail {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-1);
    padding: var(--space-4);
    min-height: 0;
    overflow: auto;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .tabs {
    display: flex;
    gap: 0.2rem;
    background: var(--sunken);
    border-radius: var(--r-pill);
    padding: 0.15rem;
  }
  .tabs button {
    border: none;
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 650;
    padding: 0.25rem 0.7rem;
    border-radius: var(--r-pill);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .tabs button[aria-selected="true"] {
    background: var(--surface);
    color: var(--text-1);
    box-shadow: var(--shadow-1);
  }
  .tabs button:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .count {
    font-size: 0.68rem;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: var(--r-pill);
    padding: 0 0.32rem;
  }
  .header-actions {
    display: flex;
    gap: 0.15rem;
  }
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: 0;
  }
  .rail-lead {
    margin: 0;
    color: var(--text-2);
    font-size: 0.78rem;
    line-height: 1.5;
  }
  .notice {
    margin: 0;
    font-size: 0.78rem;
    color: var(--accent);
  }
  .load-error {
    display: grid;
    gap: var(--space-1);
    padding: var(--space-4);
    border: 1px solid var(--danger-border);
    border-radius: var(--r-md);
    background: var(--danger-soft);
    color: var(--text-2);
    font-size: 0.78rem;
  }
  .load-error strong { color: var(--danger); }
  .task-list,
  .recent ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .task {
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 0.6rem 0.7rem;
    background: var(--raised);
  }
  .task-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .task-title {
    font-size: 0.84rem;
    font-weight: 650;
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .step {
    margin: 0.3rem 0 0;
    font-size: 0.76rem;
    color: var(--accent);
  }
  .progress {
    margin-top: 0.5rem;
    height: 5px;
    border-radius: var(--r-pill);
    background: var(--sunken);
    overflow: hidden;
  }
  .progress div {
    height: 100%;
    background: var(--accent);
  }
  .task footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-top: 0.5rem;
    color: var(--text-3);
    font-size: 0.72rem;
  }
  .recent h3,
  .examples h3 {
    margin: 0 0 0.4rem;
    font-size: 0.76rem;
    font-weight: 650;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .recent li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    font-size: 0.78rem;
  }
  .agent-form {
    display: grid;
    gap: var(--space-3);
  }
  .agent-form label {
    display: grid;
    gap: 0.3rem;
    font-size: 0.78rem;
    color: var(--text-2);
  }
  .cadence-detail {
    margin: -0.4rem 0 0;
    font-size: 0.74rem;
    color: var(--text-3);
    line-height: 1.5;
  }
  .examples {
    display: grid;
    gap: var(--space-2);
  }
  .example {
    display: grid;
    gap: 0.15rem;
    text-align: left;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    padding: 0.55rem 0.7rem;
    cursor: pointer;
    font: inherit;
  }
  .example:hover {
    border-color: var(--accent-border);
  }
  .example:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .example strong {
    font-size: 0.82rem;
    color: var(--text-1);
  }
  .example span {
    font-size: 0.75rem;
    color: var(--text-3);
  }
</style>
