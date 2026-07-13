<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ProjectDetail, ProjectsList } from "../apiTypes";
  import { relativeTime, shortId } from "../format";

  // The shell owns the active-project state for the topbar switcher; it passes
  // onchanged so a change here is reflected there without a full reload.
  let { onchanged }: { onchanged?: () => void } = $props();

  let list = $state<ProjectsList | null>(null);
  let loadError = $state<string | null>(null);

  let newName = $state("");
  let creating = $state(false);
  let createError = $state<string | null>(null);

  let selecting = $state(false);
  let selectError = $state<string | null>(null);

  let detail = $state<ProjectDetail | null>(null);
  let detailError = $state<string | null>(null);
  let deleteError = $state<string | null>(null);

  async function remove(projectId: string) {
    if (!window.confirm("This will permanently delete all project chats and files in this project folder. To save chats, move them to your chat list or another project before deleting.")) return;
    try { deleteError = null; await api.deleteProject(projectId); detail = null; await load(); onchanged?.(); }
    catch (e) { deleteError = e instanceof ApiError ? `Could not delete (${e.status}).` : "Could not delete"; }
  }

  async function load() {
    loadError = null;
    try {
      list = await api.projects();
    } catch (e) {
      list = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function create() {
    const name = newName.trim();
    if (name === "" || creating) return;
    creating = true;
    createError = null;
    try {
      await api.createProject(name);
      newName = "";
      await load();
      onchanged?.();
    } catch (e) {
      createError =
        e instanceof ApiError
          ? `Could not create (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not create";
    } finally {
      creating = false;
    }
  }

  async function select(projectId: string | null) {
    selecting = true;
    selectError = null;
    try {
      await api.selectProject(projectId);
      await load();
      onchanged?.();
    } catch (e) {
      selectError =
        e instanceof ApiError
          ? `Could not select (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not select";
    } finally {
      selecting = false;
    }
  }

  async function open(projectId: string) {
    detailError = null;
    try {
      detail = await api.project(projectId);
    } catch (e) {
      detail = null;
      detailError =
        e instanceof ApiError ? `Could not load project (${e.status}).` : "Could not load project.";
    }
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    A project is a named scope for an ongoing piece of work: its own folder inside the workspace,
    plus the sessions and checkpoints created while it is active. It is an organizing label, not an
    authority — selecting a project grants nothing, and its folder can never leave the workspace.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh projects">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

<form
  class="create-row"
  onsubmit={(e) => {
    e.preventDefault();
    void create();
  }}
>
  <input
    class="input"
    type="text"
    placeholder="New project name…"
    bind:value={newName}
    aria-label="New project name"
    maxlength={100}
  />
  <button type="submit" class="btn btn-primary btn-sm" disabled={creating || newName.trim() === ""}>
    {creating ? "Creating…" : "Create project"}
  </button>
  {#if createError}
    <span class="error" role="alert">{createError}</span>
  {/if}
</form>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if list === null}
  <p class="loading">Loading…</p>
{:else if list.projects.length === 0}
  <div class="card">
    <EmptyState
      icon="projects"
      title="No projects yet"
      body="Create one to scope your sessions and checkpoints to a piece of work."
    />
  </div>
{:else}
  <div class="layout">
    <div class="project-grid">
      {#each list.projects as p (p.project_id)}
        <article class="card project" class:active={p.selected}>
          <div class="project-head">
            <h2 class="project-name">{p.name}</h2>
            {#if p.selected}
              <Badge variant="active" label="active" />
            {/if}
          </div>
          <p class="sub">
            <code class="mono">{p.root_subpath}</code>
            · {p.session_count} session{p.session_count === 1 ? "" : "s"}
            · created {relativeTime(p.created_at)}
          </p>
          <div class="project-actions">
            {#if p.selected}
              <button
                type="button"
                class="btn btn-sm"
                onclick={() => void select(null)}
                disabled={selecting}
              >
                Deactivate
              </button>
            {:else}
              <button
                type="button"
                class="btn btn-sm"
                onclick={() => void select(p.project_id)}
                disabled={selecting}
              >
                Set active
              </button>
            {/if}
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void open(p.project_id)}>
              Details
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void remove(p.project_id)}>Delete</button>
          </div>
        </article>
      {/each}
    </div>
    {#if selectError}
      <p class="error" role="alert">{selectError}</p>
    {/if}
    {#if deleteError}<p class="error" role="alert">{deleteError}</p>{/if}

    {#if detailError}
      <p class="error" role="alert">{detailError}</p>
    {:else if detail !== null}
      <section class="card detail" aria-labelledby="project-detail-h">
        <div class="detail-head">
          <h2 id="project-detail-h">{detail.project.name}</h2>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => (detail = null)}>
            <Icon name="x" size={14} />
            Close
          </button>
        </div>
        <h3 class="kicker">Sessions</h3>
        {#if detail.sessions.length === 0}
          <p class="sub">No sessions yet — chats started while this project is active land here.</p>
        {:else}
          <ul class="plain-list">
            {#each detail.sessions as s (s.session_id)}
              <li>
                <span class="mono">{shortId(s.session_id)}</span>
                <span>{s.title ?? "—"}</span>
                <span class="sub" title={s.updated_at}>{relativeTime(s.updated_at)}</span>
              </li>
            {/each}
          </ul>
        {/if}
        <h3 class="kicker">Checkpoints</h3>
        {#if detail.checkpoints.length === 0}
          <p class="sub">No checkpoints for this project's sessions yet.</p>
        {:else}
          <ul class="plain-list">
            {#each detail.checkpoints as cp (cp.checkpoint_id)}
              <li>
                <span class="mono">{shortId(cp.checkpoint_id)}</span>
                <span>{cp.summary ?? cp.checkpoint_type}</span>
                <span class="sub" title={cp.created_at}>{relativeTime(cp.created_at)}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </section>
    {/if}
  </div>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .create-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }
  .create-row .input {
    max-width: 22rem;
  }
  .layout {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  .project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    gap: var(--space-4);
  }
  .project.active {
    border-color: var(--accent-border);
    box-shadow: 0 0 0 1px var(--accent-border), var(--shadow-1);
  }
  .project-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .project-name {
    font-size: 1rem;
    margin: 0;
    overflow-wrap: anywhere;
  }
  .project-actions {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.6rem;
  }
  .detail-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .plain-list {
    list-style: none;
    margin: 0 0 var(--space-3);
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.84rem;
  }
  .plain-list li {
    display: flex;
    gap: 0.6rem;
    align-items: baseline;
    border-bottom: 1px dashed var(--border);
    padding-bottom: 0.3rem;
  }
  .kicker {
    font-size: 0.72rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
    margin: var(--space-3) 0 0.4rem;
  }
  .sub {
    color: var(--text-3);
    font-size: 0.8rem;
    margin: 0.3rem 0 0;
    overflow-wrap: anywhere;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
