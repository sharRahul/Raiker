<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { TaskView } from "../apiTypes";
  import { taskBadge } from "../statusMaps";
  import { relativeTime, shortId } from "../format";

  const ACTIVE_STATES = ["queued", "running", "paused"];

  let tasks = $state<TaskView[] | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  let busyTask = $state<string | null>(null);

  async function load() {
    loadError = null;
    try {
      tasks = await api.tasks();
    } catch (e) {
      tasks = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
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
        reason: "user stopped this task (web UI)",
      });
      notice = { kind: "ok", text: `Requested a safe-boundary stop for “${task.title}”.` };
      await load();
    } catch {
      notice = { kind: "error", text: "Could not request the stop." };
    } finally {
      busyTask = null;
    }
  }

  const active = $derived((tasks ?? []).filter((t) => ACTIVE_STATES.includes(t.status)));
  const finished = $derived((tasks ?? []).filter((t) => !ACTIVE_STATES.includes(t.status)));

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    What the agent is working on. Stopping a task requests cancellation at the next
    <strong>safe boundary</strong> — governed and audited, never a force-kill.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh tasks">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if tasks === null}
  <p class="loading">Loading…</p>
{:else if tasks.length === 0}
  <div class="card">
    <EmptyState icon="tasks" title="No tasks yet" body="Tasks appear when the agent starts tracked work." />
  </div>
{:else}
  {#if active.length > 0}
    <h2>Active</h2>
    <div class="task-grid">
      {#each active as task (task.task_id)}
        <article class="card task">
          <div class="task-head">
            <h3 class="task-title">{task.title || shortId(task.task_id)}</h3>
            <Badge variant={taskBadge(task.status)} label={task.status} />
          </div>
          {#if task.objective}
            <p class="task-objective">{task.objective}</p>
          {/if}
          {#if task.current_step}
            <p class="task-step">Now: {task.current_step}</p>
          {/if}
          {#if task.progress_percent !== null}
            <div
              class="progress"
              role="progressbar"
              aria-valuenow={task.progress_percent}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-label="Task progress"
            >
              <div class="progress-fill" style={`width:${task.progress_percent}%`}></div>
            </div>
          {/if}
          <div class="task-foot">
            <span class="task-time" title={task.updated_at}>Updated {relativeTime(task.updated_at)}</span>
            <button
              type="button"
              class="btn btn-danger btn-sm"
              onclick={() => stopTask(task)}
              disabled={busyTask === task.task_id}
            >
              {busyTask === task.task_id ? "Stopping…" : "Stop"}
            </button>
          </div>
        </article>
      {/each}
    </div>
  {/if}

  {#if finished.length > 0}
    <h2 class="finished-h">History</h2>
    <div class="card list-card">
      <table class="table">
        <thead>
          <tr>
            <th>Task</th>
            <th>Status</th>
            <th>Summary</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {#each finished as task (task.task_id)}
            <tr>
              <td>{task.title || shortId(task.task_id)}</td>
              <td><Badge variant={taskBadge(task.status)} label={task.status} /></td>
              <td class="summary-cell">{task.summary ?? "—"}</td>
              <td title={task.updated_at}>{relativeTime(task.updated_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .task-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-5);
  }
  .task-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
  }
  .task-title {
    margin: 0;
  }
  .task-objective {
    color: var(--text-2);
    font-size: 0.86rem;
    margin: 0.35rem 0 0;
  }
  .task-step {
    font-size: 0.82rem;
    color: var(--accent);
    margin: 0.4rem 0 0;
  }
  .progress {
    height: 6px;
    border-radius: var(--r-pill);
    background: var(--sunken);
    margin-top: 0.6rem;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    border-radius: var(--r-pill);
    background: var(--accent);
    transition: width 300ms var(--ease);
  }
  .task-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.75rem;
  }
  .task-time {
    font-size: 0.76rem;
    color: var(--text-3);
  }
  .finished-h {
    margin-top: var(--space-4);
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .summary-cell {
    max-width: 26rem;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
