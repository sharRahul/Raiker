<script lang="ts">
  import WorkMeta from "../components/WorkMeta.svelte";
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import TabStrip from "../components/TabStrip.svelte";
  import PageState from "../components/PageState.svelte";
  import PathPicker from "../components/PathPicker.svelte";
  import ProjectTreeNode from "../components/ProjectTreeNode.svelte";
  import SidePanel from "../components/SidePanel.svelte";
  import RowOverflow from "../components/RowOverflow.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { setWorkProject, startInBuild } from "../workProject.svelte";
  import ProjectExplorer from "../components/ProjectExplorer.svelte";
  import { api, ApiError } from "../api";
  import type {
    ImageGeneration,
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
  // The empty state's primary action. The create field is already on
  // the page, above the empty state; the button that says "start here" should
  // put the cursor in it rather than describe where it is.
  let nameField = $state<HTMLInputElement>();
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
  /**
   * REM-PROJ-02 — the project's own sections, rather than one long column.
   *
   * The detail stacked context, files, sessions, images, tasks and checkpoints
   * on top of each other, all open, every time: an owner who came to read the
   * instructions scrolled past four lists to find them, and an owner who came
   * for the checkpoints scrolled past everything. These are five different
   * jobs, so they are five sections, and the one that answers "what is this
   * project" leads.
   *
   * Nothing is fetched per section: the project's detail, tasks and images are
   * read once on selection, exactly as before. Switching sections shows what is
   * already in hand.
   */
  const DETAIL_SECTIONS = [
    { id: "overview", label: "Overview" },
    { id: "files", label: "Files" },
    { id: "work", label: "Work" },
    { id: "assets", label: "Assets" },
    { id: "evidence", label: "Evidence" },
  ] as const;
  type DetailSection = (typeof DETAIL_SECTIONS)[number]["id"];
  let detailSection = $state<DetailSection>("overview");
  /**
   * The instructions as they were read, so an unsaved edit can say it is unsaved.
   *
   * Moving the context behind a section makes losing track of an unsaved edit
   * possible in a way a single column did not, so the page says so instead: the
   * edit is kept, the section that holds it is marked, and the mark goes when it
   * is saved.
   */
  let contextBaseline = $state("");
  const contextDirty = $derived(
    detail !== null && (detail.context.instructions ?? "") !== contextBaseline,
  );
  let detailError = $state<string | null>(null);
  /*
   * BUG-282 — the images made while this project was the working one.
   *
   * `POST /api/images` carries `project_id` now, so a generated picture belongs
   * somewhere; this is the half that makes the belonging visible. The filter is
   * on the row's own field rather than on anything derived, so a picture made
   * before the column existed stays out of every project rather than landing in
   * whichever one is open.
   */
  let projectImages = $state<ImageGeneration[]>([]);
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

  /*
   * "New chat in this project" opens Chat in that project.
   *
   * RR-PROJECT-01 — this used to navigate and nothing else, on the reasoning
   * that Chat's retrieval is owner-wide by design and starting a conversation
   * from a project must not quietly scope it. The first half of that is right
   * and is unchanged. The second half conflated two different things: *what a
   * turn may retrieve* and *where the resulting conversation is filed*. Only the
   * first is a boundary. The second is the ordinary meaning of pressing "New
   * chat" on a project card, and the Build button beside it had always done it.
   *
   * So the shared Work project is set — which is filing, is visible in the
   * composer's own picker before the owner presses Send, and re-files nothing
   * that already exists — and retrieval stays owner-wide exactly as before.
   */
  function newChatInProject(projectId: string) {
    setWorkProject(projectId);
    window.location.hash = "#/new-chat";
  }

  async function saveContext() {
    if (detail === null || savingContext) return;
    savingContext = true;
    contextError = null;
    try {
      await api.saveProjectContext(detail.project.project_id, detail.context);
      // Saved is the new baseline, so the section stops saying it is unsaved.
      contextBaseline = detail.context.instructions ?? "";
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
    try { deleteError = null; await api.deleteProject(projectId, true); closeDetail(); await load(); onchanged?.(); }
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

  /*
   * NEW-PROJ-01 — which selection a response belongs to.
   *
   * A project home is four independent reads — the detail, the files, the tasks
   * and the images — sharing one set of view variables, and every one of them
   * used to be assigned the moment it resolved. Open project A on a slow
   * workspace, open B while A's file read is still out, and B's header stood
   * over A's files: a header is an implicit promise that everything under it
   * belongs to that workspace, and this broke the promise silently, which is
   * the worst way to break it. An older *failed* detail read could also clear a
   * newer successful selection, so a project that loaded fine disappeared
   * behind an error about a different one.
   *
   * The counter is the whole fix. Each open takes the next number, every
   * response carries the number of the open that asked for it, and a response
   * is committed only if that number is still the current one. It holds for
   * failures as well as successes, and for a close during a load, because
   * closing takes a number too.
   *
   * This is not a substitute for cancelling the request — it is the thing that
   * makes cancellation unnecessary to get right. A cancel can always lose the
   * race with a response that is already on the wire.
   */
  let selectionSeq = 0;

  async function loadProjectContext(projectId: string, seq: number) {
    filesError = null;
    files = null;
    selectedFile = null;
    projectTasks = [];
    projectImages = [];
    try {
      const loaded = await api.projectFiles(projectId);
      if (seq !== selectionSeq) return;
      files = loaded;
    } catch (e) {
      if (seq !== selectionSeq) return;
      filesError =
        e instanceof ApiError ? `Files unavailable (${e.status}).` : "Files unavailable.";
    }
    try {
      const loaded = await api.tasks({ project_id: projectId });
      if (seq !== selectionSeq) return;
      projectTasks = loaded;
    } catch {
      // Task scoping is supplementary context; a failed read leaves the rest
      // of the project home intact rather than blanking it.
      if (seq !== selectionSeq) return;
      projectTasks = [];
    }
    try {
      // The gallery read is owner-scoped and returns metadata only, so this is
      // one request rather than a per-picture one; the bytes stay behind the
      // separate route each thumbnail names.
      const gallery = await api.images();
      if (seq !== selectionSeq) return;
      projectImages = gallery.generations
        .filter(
          (generation) =>
            generation.project_id === projectId &&
            generation.status === "ok" &&
            generation.has_image,
        )
        .sort((left, right) => right.created_at.localeCompare(left.created_at));
    } catch {
      // Same rule as tasks: supplementary context, and a workspace with no
      // image provider connected answers this with an error rather than a list.
      if (seq !== selectionSeq) return;
      projectImages = [];
    }
  }

  /**
   * Leave the project home, and take the selection's number with it.
   *
   * Closing during a load is a selection change like any other: the reads that
   * are still out belong to a project that is no longer on screen, and without
   * a new number they would re-open it when they land.
   */
  function closeDetail() {
    selectionSeq += 1;
    detail = null;
    detailSection = "overview";
    contextBaseline = "";
    detailError = null;
    files = null;
    filesError = null;
    selectedFile = null;
    projectTasks = [];
    projectImages = [];
  }

  async function open(projectId: string) {
    const seq = ++selectionSeq;
    detailError = null;
    exportError = null;
    // Clear the previous project's panels on selection rather than leaving them
    // under the new name while its own reads are out.
    detail = null;
    files = null;
    filesError = null;
    selectedFile = null;
    projectTasks = [];
    projectImages = [];
    try {
      const loaded = await api.project(projectId);
      if (seq !== selectionSeq) return;
      detail = loaded;
      // A new project opens on its overview, with nothing unsaved.
      detailSection = "overview";
      contextBaseline = loaded.context.instructions ?? "";
      await loadProjectContext(projectId, seq);
    } catch (e) {
      if (seq !== selectionSeq) return;
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
    bind:this={nameField}
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
      body="Keep the chats, tasks and files for one goal together."
    >
      {#snippet action()}
        <button type="button" class="btn btn-primary" onclick={() => nameField?.focus()}>
          Name your first project
        </button>
      {/snippet}
    </EmptyState>
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
            <!-- The path is what this project *is* on disk, and it
                 is the technical identifier, so it reads below the name in mono
                 rather than inside the sentence about the work.
                 The counts and the age use the shared work vocabulary, in
                 the order a thread and a task use. -->
            <code class="project-root mono">{p.root_kind === "attached" ? p.root_label : p.root_subpath}</code>
            <WorkMeta
              detail={`${p.session_count} session${p.session_count === 1 ? "" : "s"}`}
              activityAt={p.created_at}
              activityVerb="created"
            />
          </button>
          <!-- REM-PROJ-01 / UX-PROJ-02 — five actions at equal weight is not a
               card, it is a menu with the lid off. "Start in Build", "New chat",
               "Archive", "Move" and "Delete" each looked like the thing to press
               next, so the two an owner wants many times a day sat beside the
               three they want a handful of times ever — one of which erases a
               project and, for a managed one, its folder.
               Continuing work is primary, starting new work is secondary, and
               the lifecycle actions are one deliberate reach away. Nothing is
               removed: every action keeps its handler, its disabled state and
               its confirmation. -->
          <div class="project-actions">
            <button
              type="button"
              class="btn btn-primary btn-sm"
              onclick={() => newChatInProject(p.project_id)}
            >
              New chat
            </button>
            <button
              type="button"
              class="btn btn-sm"
              onclick={() => startInBuild(p.project_id)}
            >
              Start in Build
            </button>
            <RowOverflow
              label={p.name}
              items={[
                {
                  label: archiving === p.project_id ? "Archiving…" : "Archive",
                  disabled: archiving === p.project_id,
                  run: () => void archiveProject(p.project_id),
                },
                { label: "Move", run: () => void startMove(p.project_id) },
                {
                  label: "Delete",
                  run: () =>
                    void remove(p.project_id, p.root_kind, p.root_label),
                },
              ]}
            />
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
            <button type="button" class="btn btn-ghost btn-sm" onclick={closeDetail}>
              <Icon name="x" size="sm" />
              Close
            </button>
          </div>
        </div>
        {#if exportError}<p class="error" role="alert">{exportError}</p>{/if}

        <TabStrip
          tabs={DETAIL_SECTIONS.map((section) => ({ id: section.id, label: section.label }))}
          selected={detailSection}
          onselect={(id: string) => (detailSection = id as DetailSection)}
          label="Project sections"
        />
        {#if contextDirty && detailSection !== "overview"}
          <p class="sub unsaved" role="status">
            Project context has unsaved changes. They are kept — open
            <strong>Overview</strong> to save them.
          </p>
        {/if}

        {#if detailSection === "overview"}
        <h3 class="kicker">Project context</h3>
        <p class="sub">Instructions and shared files are included only in chats already assigned to this project. Project memory follows this folder's setting or its nearest ancestor.</p>
        <!-- REM-PROJ-02 — the two context fields as two fields. A `<textarea>`
             sizes itself from its `cols` default, so it sat at about a fifth of
             the card with the memory control beside it, reading as a caption on
             a dropdown rather than as the project's instructions. -->
        <div class="context-fields">
        <label class="context-field">
          <span>Instructions</span>
          <textarea class="input context-input" aria-label="Project instructions" bind:value={detail.context.instructions} maxlength="4000" placeholder="Project-specific instructions…"></textarea>
        </label>
        <label class="context-field">Project memory
          <select class="input" bind:value={detail.context.memory_mode} aria-label="Project memory setting">
            <option value="inherit">Inherit from parent</option>
            <option value="enabled">Include approved project memory</option>
            <option value="disabled">Do not include project memory</option>
          </select>
        </label>
        </div>
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
        <!-- The overview ends with what the project *is*: how many of each kind
             of thing is under it, so a section is opened deliberately rather
             than to find out whether it holds anything. -->
        <dl class="section-counts">
          <div><dt>Files</dt><dd>{files?.files.length ?? 0}{files?.truncated ? "+" : ""}</dd></div>
          <div><dt>Sessions</dt><dd>{detail.sessions.length}</dd></div>
          <div><dt>Tasks</dt><dd>{projectTasks.length}</dd></div>
          <div><dt>Images</dt><dd>{projectImages.length}</dd></div>
          <div><dt>Checkpoints</dt><dd>{detail.checkpoints.length}</dd></div>
        </dl>
        {:else if detailSection === "files"}
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
        {:else if detailSection === "work"}
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

        <!-- BUG-282 / the Work project — "generated images belong to the Project
             automatically when created there". They are material, so they sit
             with the project's own things rather than in a gallery of their
             own; REM-PROJ-02 gives them the Assets section beside Files. -->
        {:else if detailSection === "assets"}
        <h3 class="kicker">Images</h3>
        {#if projectImages.length === 0}
          <p class="sub">
            No images yet — pictures generated in Design while this project is active land here.
          </p>
        {:else}
          <!-- NEW-PROJ-02 — the strip showed eight pictures and offered no way
               to open one of them: the only continuation was a bare `#/design`,
               so finding the image you had just been looking at meant searching
               the whole account's Design history for it. Each one is now a link
               to itself, and the strip says how many there are rather than
               implying eight is all of them. -->
          <ul class="image-strip">
            {#each projectImages.slice(0, 8) as image (image.generation_id)}
              <li>
                <a
                  href={`#/design?project=${encodeURIComponent(detail.project.project_id)}&asset=${encodeURIComponent(image.generation_id)}`}
                  title={image.prompt}
                >
                  <img
                    src={api.imageBytesUrl(image.generation_id)}
                    alt={`Open in Design: ${image.prompt}`}
                    loading="lazy"
                  />
                </a>
                <span class="sub" title={image.created_at}>{relativeTime(image.created_at)}</span>
              </li>
            {/each}
          </ul>
          {#if projectImages.length > 8}
            <p class="sub">Showing 8 of {projectImages.length}.</p>
          {/if}
          <a
            class="cross-link"
            href={`#/design?project=${encodeURIComponent(detail.project.project_id)}`}
            >View all in Design</a
          >
        {/if}


        {:else if detailSection === "evidence"}
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
  @media (max-width: 720px) {
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
  .context-fields { display: grid; gap: var(--space-3); margin: var(--space-3) 0; }
  .context-field { display: grid; gap: 0.35rem; color: var(--text-2); font-size: var(--text-sm); }
  .context-field > span { font-weight: 650; }
  .context-input { width: 100%; min-height: 6rem; resize: vertical; }
  /* REM-PROJ-02 — the project's counts, so a section is opened deliberately
     rather than to find out whether it holds anything. */
  .section-counts {
    display: flex; flex-wrap: wrap; gap: var(--space-4);
    margin: var(--space-4) 0 0; padding-top: var(--space-3);
    border-top: 1px solid var(--border);
  }
  .section-counts div { display: grid; gap: 0.1rem; }
  .section-counts dt { color: var(--text-3); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; }
  .section-counts dd { margin: 0; color: var(--text-1); font-size: var(--text-lg); }
  .unsaved { margin-top: var(--space-3); }
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
  /* A strip rather than a grid: this is the project's material at a glance,
     and Design is where a picture is worked on. The hairline is the same one
     Design's asset carries (the dark composition) so a thumbnail reads as a picture on both
     grounds without a card around it. */
  .image-strip {
    list-style: none;
    margin: 0 0 var(--space-3);
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .image-strip li {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    width: 7rem;
  }
  .image-strip img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    border: 1px solid var(--canvas-edge);
    border-radius: var(--r-sm);
    background: var(--surface);
  }
  .image-strip .sub {
    margin: 0;
    font-size: var(--text-2xs);
  }
  /* `.kicker` is a shared rule; only the spacing above it is this view's. */
  .project-root {
    display: block;
    color: var(--text-3);
    font-size: var(--text-2xs);
    overflow-wrap: anywhere;
  }
  .kicker {
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
