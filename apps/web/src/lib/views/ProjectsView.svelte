<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import PathPicker from "../components/PathPicker.svelte";
  import ProjectTreeNode from "../components/ProjectTreeNode.svelte";
  import SidePanel from "../components/SidePanel.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { startInBuild } from "../buildProject";
  import ProjectExplorer from "../components/ProjectExplorer.svelte";
  import { api, ApiError } from "../api";
  import type {
    ProjectBrowseEntry,
    ProjectDetail,
    ProjectFilesView,
    ProjectsList,
    ProjectTreeNode as TreeNode,
    TaskView,
  } from "../apiTypes";
  import { humanize, isRedacted, relativeTime, shortId } from "../format";
  import { explainReasonCode } from "../reasonCodes";

  let { onchanged }: { onchanged?: () => void } = $props();

  let list = $state<ProjectsList | null>(null);
  let tree = $state<TreeNode[]>([]);
  let loadError = $state<string | null>(null);

  let newName = $state("");
  let creating = $state(false);
  let createError = $state<string | null>(null);

  // Attaching an existing folder sits beside creating one, because for anyone
  // whose work already lives in a folder it *is* the way they make a project.
  // Hiding it inside a created project's detail would make the common case the
  // one they have to go looking for.
  let attachOpen = $state(false);
  let attachName = $state("");
  let attachPath = $state("");
  let attachWritable = $state(true);
  let attaching = $state(false);
  let attachError = $state<string | null>(null);


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
  // BUG-251 — the folder can be browsed to. Typing an absolute path is still
  // allowed; it is no longer the only way.
  let browsing = $state(false);

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

  // "New chat in this project" opens Chat, and deliberately does not narrow it.
  // Chat's retrieval is owner-wide by design, so starting a conversation from a
  // project must not quietly scope it. The composer's own picker files the
  // resulting conversation, which is filing rather than a boundary.
  function newChatInProject() {
    window.location.hash = "#/new-chat";
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

  async function remove(projectId: string, rootKind: "managed" | "attached", rootLabel: string) {
    // The two roots deserve different sentences, because they have different
    // consequences. Telling an owner their attached folder will be deleted
    // would be false; telling a managed project's owner it survives would be
    // worse.
    const message =
      rootKind === "attached"
        ? `This will remove the project and its chats from Raiker. The folder ${rootLabel} will not be deleted.`
        : "This will permanently delete all project chats and files in this project folder. To save chats, move them to your chat list or another project before deleting.";
    if (!window.confirm(message)) return;
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
      // Say what happened, not what the wire said: a duplicate name is an
      // ordinary refusal and should read like one.
      createError =
        e instanceof ApiError
          ? explainReasonCode(e.reasonCode)?.plain ?? `Could not create (${e.status})`
          : "Could not create";
    } finally {
      creating = false;
    }
  }

  async function attachFolder() {
    const name = attachName.trim();
    const path = attachPath.trim();
    if (name === "" || path === "" || attaching) return;
    attaching = true;
    attachError = null;
    try {
      await api.createProject(name, path, attachWritable);
      attachName = "";
      attachPath = "";
      attachOpen = false;
      await load();
      onchanged?.();
    } catch (e) {
      attachError =
        e instanceof ApiError
          ? explainReasonCode(e.reasonCode)?.plain ?? `Could not attach (${e.status})`
          : "Could not attach";
    } finally {
      attaching = false;
    }
  }

  async function attachToExisting(projectId: string) {
    const path = window.prompt(
      "Full path to the folder. It is read where it lives — Raiker copies nothing.",
    );
    if (path === null || path.trim() === "") return;
    try {
      attachError = null;
      await api.attachProjectFolder(projectId, path.trim(), true);
      await load();
      await open(projectId);
    } catch (e) {
      attachError =
        e instanceof ApiError
          ? `Could not attach (${e.status}${e.reasonCode ? `: ${e.reasonCode}` : ""})`
          : "Could not attach";
    }
  }

  // ── Project context home ─────────────────────────────────────────────
  // Opening a project shows everything scoped to it in one place: its files,
  // the work running under it, its stored knowledge, and its checkpoint
  // timeline. Files are metadata only — Raiker never serves workspace content
  // to the browser — and selecting one opens an inspect pane whose provenance
  // links back to the turn that wrote it.
  // `files` is read for its provenance map alone. The listing it also carries
  // is no longer rendered: the explorer is the one file list, and two lists of
  // the same files described differently is exactly what this replaced. The
  // provenance is not duplicated anywhere, so it is still read here.
  let files = $state<ProjectFilesView | null>(null);
  let filesError = $state<string | null>(null);
  let selectedFile = $state<ProjectBrowseEntry | null>(null);
  let projectTasks = $state<TaskView[]>([]);

  const detailProjectId = $derived(detail?.project.project_id ?? "");
  const detailRootKind = $derived(detail?.project.root_kind ?? "managed");
  const detailRootLabel = $derived(detail?.project.root_label ?? "");

  const fileProvenance = $derived.by(() => {
    if (selectedFile === null || files === null) return [];
    // A governed write is recorded against a workspace-relative path, while the
    // explorer names a file relative to its own root. For a managed project the
    // two differ by the project's subpath; for an attached one they can also
    // agree outright, so both keys are tried rather than one guessed at.
    const relative = selectedFile.relative_path;
    const subpath = files.root_subpath;
    return (
      files.provenance[relative] ??
      files.provenance[subpath === "" ? relative : `${subpath}/${relative}`] ??
      []
    );
  });

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function loadProjectContext(projectId: string) {
    filesError = null;
    files = null;
    selectedFile = null;
    projectTasks = [];
    try {
      files = await api.projectFiles(projectId);
    } catch (e) {
      filesError =
        e instanceof ApiError ? `Files unavailable (${e.status}).` : "Files unavailable.";
    }
    try {
      projectTasks = await api.tasks({ project_id: projectId });
    } catch {
      // Task scoping is supplementary context; a failed read leaves the rest
      // of the project home intact rather than blanking it.
      projectTasks = [];
    }
  }

  async function open(projectId: string) {
    detailError = null;
    exportError = null;
    try {
      detail = await api.project(projectId);
      await loadProjectContext(projectId);
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
  <GuideLink route="projects" />
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh projects">
    <Icon name="refresh" size="sm" />
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
  <button
    type="button"
    class="btn btn-ghost btn-sm"
    onclick={() => (attachOpen = !attachOpen)}
    aria-expanded={attachOpen}
  >
    Attach existing folder…
  </button>
  {#if createError}
    <span class="error" role="alert">{createError}</span>
  {/if}
</form>

{#if attachOpen}
  <form
    class="card attach-form"
    onsubmit={(e) => {
      e.preventDefault();
      void attachFolder();
    }}
  >
    <h3 class="kicker">Attach an existing folder</h3>
    <p class="sub">
      The folder is read where it lives on this machine. Nothing is copied into Raiker, and
      deleting the project later will not delete the folder.
    </p>
    <input
      class="input"
      type="text"
      placeholder="Project name…"
      bind:value={attachName}
      aria-label="Attached project name"
      maxlength={100}
    />
    <div class="path-field">
      <input
        class="input"
        type="text"
        placeholder="Full path to the folder…"
        bind:value={attachPath}
        aria-label="Folder path"
      />
      <button type="button" class="btn btn-sm" onclick={() => (browsing = true)}>
        <Icon name="folder" size="sm" /> Browse
      </button>
    </div>
    <label class="check-row">
      <input type="checkbox" bind:checked={attachWritable} />
      Let Raiker write into this folder (still subject to your approvals)
    </label>
    <div class="attach-actions">
      <button
        type="submit"
        class="btn btn-primary btn-sm"
        disabled={attaching || attachName.trim() === "" || attachPath.trim() === ""}
      >
        {attaching ? "Attaching…" : "Attach folder"}
      </button>
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (attachOpen = false)}>
        Cancel
      </button>
    </div>
    {#if attachError}<p class="error" role="alert">{attachError}</p>{/if}
  </form>
{/if}

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
    <div class="card-grid project-grid">
      {#each list.projects as p (p.project_id)}
        <article
          class="card card-interactive project"
          class:active={p.selected}
          class:drag-over={dragOverId === p.project_id}
          ondragover={(e) => onDragOver(e, p.project_id)}
          ondragleave={() => onDragLeave(p.project_id)}
          ondrop={(e) => void onDrop(e, p.project_id)}
        >
          <!-- The card body opens the project. A "Details" button beside five
               other buttons made the card's own name inert, which is the one
               thing a person tries first. -->
          <button
            type="button"
            class="project-open"
            onclick={() => void open(p.project_id)}
            aria-label={`Open project ${p.name}`}
          >
            <span class="project-head">
              <span class="project-name">{p.name}</span>
              {#if p.selected}
                <Badge variant="active" label="active" />
              {/if}
              {#if p.root_kind === "attached"}
                <Badge variant="read-only" label="attached folder" />
              {/if}
            </span>
            <span class="sub">
              <code class="mono">{p.root_kind === "attached" ? p.root_label : p.root_subpath}</code>
              · {p.session_count} session{p.session_count === 1 ? "" : "s"}
              · created {relativeTime(p.created_at)}
            </span>
          </button>
          <div class="project-actions">
            <button
              type="button"
              class="btn btn-sm"
              onclick={() => startInBuild(p.project_id)}
            >
              Start in Build
            </button>
            <button type="button" class="btn btn-primary btn-sm" onclick={() => newChatInProject()}>
              New chat
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void archiveProject(p.project_id)} disabled={archiving === p.project_id}>
              Archive
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void startMove(p.project_id)}>
              Move
            </button>
            <button type="button" class="btn btn-ghost btn-sm" onclick={() => void remove(p.project_id, p.root_kind, p.root_label)}>Delete</button>
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
              <Icon name="x" size="sm" />
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
        {#if detailRootKind === "managed"}
          <div class="attach-inline">
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={() => void attachToExisting(detailProjectId)}
            >
              Attach a folder
            </button>
            <span class="sub">Use a folder you already have as this project's root instead.</span>
          </div>
        {/if}
        {#if attachError}<p class="error" role="alert">{attachError}</p>{/if}
        <ProjectExplorer
          projectId={detail.project.project_id}
          rootKind={detailRootKind}
          rootLabel={detailRootLabel}
          onselect={(entry) => (selectedFile = entry)}
        />
        {#if filesError}
          <!-- Provenance is read alongside the tree. Losing it degrades this one
               line rather than the file list, which no longer depends on it. -->
          <p class="sub" role="status">{filesError}</p>
        {/if}
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
        <h3 class="kicker">Work under this project</h3>
        {#if projectTasks.length === 0}
          <p class="sub">
            No tasks are scoped to this project. Tasks created while it is active land here.
          </p>
        {:else}
          <ul class="plain-list">
            {#each projectTasks.slice(0, 8) as task (task.task_id)}
              <li>
                <span>{task.title}</span>
                <span class="sub">{humanize(task.status)}</span>
                <span class="sub" title={task.updated_at}>{relativeTime(task.updated_at)}</span>
              </li>
            {/each}
          </ul>
          <a class="cross-link" href="#/tasks">Open Tasks</a>
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
          <a class="cross-link" href="#/checkpoints">Open the checkpoint timeline</a>
        {/if}
      </section>
    {/if}

    <SidePanel
      open={selectedFile !== null}
      title={selectedFile?.name ?? ""}
      subtitle={selectedFile?.relative_path ?? null}
      onclose={() => (selectedFile = null)}
    >
      {#if selectedFile}
        <dl class="property-list inspect">
          <dt>Kind</dt>
          <dd>{selectedFile.is_directory ? "Folder" : "File"}</dd>
          {#if !selectedFile.is_directory}
            <dt>Size</dt>
            <dd>{formatBytes(selectedFile.size_bytes)}</dd>
          {/if}
          {#if selectedFile.index_state !== null}
            <dt>Index</dt>
            <dd>{humanize(selectedFile.index_state)}</dd>
          {/if}
        </dl>

        <h3 class="panel-h">Provenance</h3>
        {#if fileProvenance.length === 0}
          <p class="sub">
            No governed write is recorded against this path. It was not changed through a Raiker
            action that captures a checkpoint.
          </p>
        {:else}
          <ul class="provenance">
            {#each fileProvenance as entry (entry.created_at + (entry.action_id ?? ""))}
              <li>
                <p class="prov-head">
                  {humanize(entry.capability)}
                  <time title={entry.created_at}>{relativeTime(entry.created_at)}</time>
                </p>
                <p class="prov-detail">
                  {entry.existed_before
                    ? `Overwrote ${entry.pre_image_size} bytes`
                    : "Created this file"} · captured as
                  <span class="mono">{entry.capture_status}</span>
                </p>
                <p class="prov-links">
                  {#if isRedacted(entry.session_id)}
                    <!-- A redacted id addresses nothing; a link here would be
                         dead, so the fact is stated instead. -->
                    <span title="The server redacted this identifier.">Session withheld</span>
                  {:else}
                    <a href={`#/sessions?session=${encodeURIComponent(entry.session_id)}`}>
                      Session {shortId(entry.session_id)}
                    </a>
                    {#if entry.turn_id}
                      ·
                      <a
                        href={`#/observe?tab=activity&session=${encodeURIComponent(entry.session_id)}`}
                      >Turn {shortId(entry.turn_id)} in the audit log</a>
                    {/if}
                  {/if}
                </p>
              </li>
            {/each}
          </ul>
        {/if}
        <p class="sub">
          Raiker shows what changed and who changed it, never the file's contents. Editing goes
          through a governed action with its own approval.
        </p>
      {/if}
    </SidePanel>

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

{#if browsing}
  <PathPicker
    title="Choose a folder to attach"
    start={attachPath}
    onchoose={(path) => { attachPath = path; browsing = false; }}
    onclose={() => (browsing = false)}
  />
{/if}

<style>
  .path-field { display: flex; gap: var(--space-2); align-items: center; }
  .path-field .input { flex: 1; min-width: 0; }
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
    --card-min: 18rem;
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
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .project-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .project-name {
    font-size: var(--text-base);
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
    font-size: var(--text-sm);
  }
  .plain-list li {
    display: flex;
    gap: 0.6rem;
    align-items: baseline;
    border-bottom: 1px dashed var(--border);
    padding-bottom: 0.3rem;
  }
  .kicker {
    font-size: var(--text-xs);
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
    margin: var(--space-3) 0 0.4rem;
  }
  .sub {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0.3rem 0 0;
    overflow-wrap: anywhere;
  }
  .cross-link {
    display: inline-block;
    font-size: var(--text-sm);
    font-weight: 600;
    margin-bottom: var(--space-2);
  }
  .panel-h {
    margin: var(--space-2) 0 0;
    font-size: var(--text-sm);
  }
  .provenance {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .provenance li {
    border-left: 2px solid var(--accent-border);
    padding-left: 0.55rem;
  }
  .prov-head {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 650;
  }
  .prov-head time {
    color: var(--text-3);
    font-weight: 500;
    white-space: nowrap;
  }
  .prov-detail,
  .prov-links {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
</style>
