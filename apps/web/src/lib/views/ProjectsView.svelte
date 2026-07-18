<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import ProjectTreeNode from "../components/ProjectTreeNode.svelte";
  import { api, ApiError } from "../api";
  import type { ProjectDetail, ProjectsList, ProjectTreeNode as TreeNode } from "../apiTypes";
  import { relativeTime, shortId } from "../format";

  let { onchanged }: { onchanged?: () => void } = $props();

  let list = $state<ProjectsList | null>(null);
  let tree = $state<TreeNode[]>([]);
  let loadError = $state<string | null>(null);

  let newName = $state("");
  let creating = $state(false);
  let createError = $state<string | null>(null);

  let selecting = $state(false);
  let selectError = $state<string | null>(null);

  let detail = $state<ProjectDetail | null>(null);
  let detailError = $state<string | null>(null);
  let exporting = $state(false);
  let exportError = $state<string | null>(null);
  let deleteError = $state<string | null>(null);
  let savingContext = $state(false);
  let contextError = $state<string | null>(null);

  let moveTarget = $state<string | null>(null);
  let moveParentId = $state<string | null>(null);
  let moving = $state(false);
  let moveError = $state<string | null>(null);

  let archiving = $state<string | null>(null);
  let archiveError = $state<string | null>(null);

  // Drag-and-drop: a recent chat from the sidebar can be dropped onto a
  // project card to move that chat into the project. The session id travels in
  // the drag dataTransfer under the private mime "text/raiker-session-id".
  let dragOverId = $state<string | null>(null);
  let dropError = $state<string | null>(null);

  function onDragOver(event: DragEvent, projectId: string) {
    if (event.dataTransfer === null) return;
    // Accept chats being dragged in. Browsers won't let us read the payload
    // on dragover, so we allow any drag that advertises our mime types.
    if (event.dataTransfer.types.includes("text/raiker-session-id")) {
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      dragOverId = projectId;
    }
  }
  function onDragLeave(projectId: string) {
    if (dragOverId === projectId) dragOverId = null;
  }
  async function onDrop(event: DragEvent, projectId: string) {
    event.preventDefault();
    dragOverId = null;
    const sessionId = event.dataTransfer?.getData("text/raiker-session-id") ?? null;
    if (sessionId === null || sessionId === "") return;
    dropError = null;
    try {
      await api.setSessionProject(sessionId, projectId);
      window.dispatchEvent(new CustomEvent("raiker:chats-changed"));
      await load();
      onchanged?.();
    } catch (e) {
      dropError = e instanceof ApiError ? `Could not move chat into ${projectId}.` : "Could not move chat.";
    }
  }

  // "New chat in this project": activate the project (new sessions are stamped
  // with the active project), notify the shell so the topbar switcher follows,
  // then open the composer. The project is an organizing scope — selecting it
  // grants nothing; it only bounds the context the new chat receives.
  async function newChatInProject(projectId: string) {
    try {
      await api.selectProject(projectId);
      onchanged?.();
      window.location.hash = "#/new-chat";
    } catch (e) {
      selectError = e instanceof ApiError ? `Could not start a new chat (${e.status}).` : "Could not start a new chat.";
    }
  }

  async function saveContext() {
    if (detail === null || savingContext) return;
    savingContext = true;
    contextError = null;
    try {
      await api.saveProjectContext(detail.project.project_id, detail.context);
    } catch (e) {
      contextError = e instanceof ApiError ? `Could not save context (${e.status}).` : "Could not save context.";
    } finally {
      savingContext = false;
    }
  }

  async function remove(projectId: string) {
    if (!window.confirm("This will permanently delete all project chats and files in this project folder. To save chats, move them to your chat list or another project before deleting.")) return;
    try { deleteError = null; await api.deleteProject(projectId, true); detail = null; await load(); onchanged?.(); }
    catch (e) { deleteError = e instanceof ApiError ? `Could not delete (${e.status}).` : "Could not delete"; }
  }

  async function load() {
    loadError = null;
    try {
      const [projects, projectTree] = await Promise.all([api.projects(), api.projectTree()]);
      list = projects;
      tree = projectTree;
    } catch (e) {
      list = null;
      tree = [];
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
    exportError = null;
    try {
      detail = await api.project(projectId);
    } catch (e) {
      detail = null;
      detailError =
        e instanceof ApiError ? `Could not load project (${e.status}).` : "Could not load project.";
    }
  }

  async function exportProject() {
    if (detail === null || exporting) return;
    exporting = true;
    exportError = null;
    try {
      await api.exportProject(detail.project.project_id);
    } catch (e) {
      exportError = e instanceof ApiError ? `Could not export (${e.status}).` : "Could not export.";
    } finally {
      exporting = false;
    }
  }

  async function archiveProject(projectId: string) {
    archiving = projectId;
    archiveError = null;
    try {
      await api.archiveProject(projectId);
      await load();
    } catch (e) {
      archiveError = e instanceof ApiError ? `Could not archive (${e.status}).` : "Could not archive.";
    } finally {
      archiving = null;
    }
  }

  async function startMove(projectId: string) {
    moveTarget = projectId;
    moveParentId = null;
    moveError = null;
  }

  async function confirmMove() {
    if (moveTarget === null || moving) return;
    moving = true;
    moveError = null;
    try {
      await api.moveProject(moveTarget, moveParentId);
      moveTarget = null;
      await load();
    } catch (e) {
      moveError = e instanceof ApiError ? `Could not move (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""}).` : "Could not move.";
    } finally {
      moving = false;
    }
  }

  function flatProjects(): { project_id: string; name: string }[] {
    if (!list) return [];
    return list.projects.map((p) => ({ project_id: p.project_id, name: p.name }));
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    A project is a named scope for an ongoing piece of work: its own folder inside the workspace,
    plus the sessions and checkpoints created while it is active. It is an organizing label, not an
    authority — selecting a project grants nothing, and its folder can never leave the workspace.
    Drag a recent chat onto a project to move it in, or use “New chat” to start a conversation in
    that project.
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
  <PageState state="error" title="Couldn't load projects" detail={loadError} />
{:else if list === null}
  <PageState state="loading" title="Loading projects…" />
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
        <article
          class="card project"
          class:active={p.selected}
          class:drag-over={dragOverId === p.project_id}
          ondragover={(e) => onDragOver(e, p.project_id)}
          ondragleave={() => onDragLeave(p.project_id)}
          ondrop={(e) => void onDrop(e, p.project_id)}
        >
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
            <button type="button" class="btn btn-primary btn-sm" onclick={() => void newChatInProject(p.project_id)}>
              New chat
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void open(p.project_id)}>
              Details
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void archiveProject(p.project_id)} disabled={archiving === p.project_id}>
              Archive
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void startMove(p.project_id)}>
              Move
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void remove(p.project_id)}>Delete</button>
          </div>
          {#if dragOverId === p.project_id}
            <p class="drop-hint" role="status">Drop to move chat into “{p.name}”.</p>
          {/if}
        </article>
      {/each}
    </div>

    {#if dropError}
      <p class="error" role="alert">{dropError}</p>
    {/if}

    {#if archiveError}
      <p class="error" role="alert">{archiveError}</p>
    {/if}

    {#if moveTarget !== null}
      <div class="card move-dialog">
        <h3 class="kicker">Move project</h3>
        <label class="move-row">
          <span>New parent:</span>
          <select bind:value={moveParentId} class="input">
            <option value={null}>Root (no parent)</option>
            {#each flatProjects() as fp}
              {#if fp.project_id !== moveTarget}
                <option value={fp.project_id}>{fp.name}</option>
              {/if}
            {/each}
          </select>
        </label>
        <div class="move-actions">
          <button type="button" class="btn btn-sm" onclick={() => void confirmMove()} disabled={moving}>
            {moving ? "Moving…" : "Confirm move"}
          </button>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => (moveTarget = null)}>
            Cancel
          </button>
        </div>
        {#if moveError}<p class="error" role="alert">{moveError}</p>{/if}
      </div>
    {/if}

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
          <div class="detail-actions">
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void exportProject()} disabled={exporting}>
              {exporting ? "Exporting…" : "Export project"}
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => (detail = null)}>
              <Icon name="x" size={14} />
              Close
            </button>
          </div>
        </div>
        {#if exportError}<p class="error" role="alert">{exportError}</p>{/if}
        <h3 class="kicker">Project context</h3>
        <p class="sub">Instructions and shared files are included only in chats already assigned to this project. Project memory follows this folder's setting or its nearest ancestor.</p>
        <textarea class="input context-input" aria-label="Project instructions" bind:value={detail.context.instructions} maxlength="4000" placeholder="Project-specific instructions…"></textarea>
        <label class="check-row">Project memory
          <select class="input" bind:value={detail.context.memory_mode} aria-label="Project memory setting">
            <option value="inherit">Inherit from parent</option>
            <option value="enabled">Include approved project memory</option>
            <option value="disabled">Do not include project memory</option>
          </select>
        </label>
        <p class="sub">Shared attachment IDs: {detail.context.attachment_ids.length ? detail.context.attachment_ids.join(", ") : "none"}</p>
        <button type="button" class="btn btn-sm" onclick={() => void saveContext()} disabled={savingContext}>{savingContext ? "Saving…" : "Save context"}</button>
        {#if contextError}<p class="error" role="alert">{contextError}</p>{/if}
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

    {#if tree.length > 0}
      <section class="card tree-section" aria-labelledby="tree-h">
        <h3 id="tree-h" class="kicker">Folder tree</h3>
        <ul class="tree-root">
          {#each tree as node (node.project_id)}
            <ProjectTreeNode {node} />
          {/each}
        </ul>
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
  @media (max-width: 720px) {
    .head-row {
      flex-direction: column;
    }
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
  .project.drag-over {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent), var(--shadow-2);
    background: var(--accent-soft);
  }
  .drop-hint {
    margin: 0.5rem 0 0;
    color: var(--accent);
    font-size: 0.8rem;
    font-weight: 600;
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
    flex-wrap: wrap;
  }
  .detail-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .detail-actions {
    display: flex;
    gap: 0.4rem;
  }
  .move-dialog {
    padding: var(--space-3);
  }
  .move-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  .move-row select {
    max-width: 16rem;
  }
  .move-actions {
    display: flex;
    gap: 0.4rem;
  }
  .tree-section {
    padding: var(--space-3);
  }
  .tree-root {
    margin: 0;
    padding: 0;
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
</style>
