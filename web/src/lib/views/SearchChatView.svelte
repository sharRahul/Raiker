<script lang="ts">
  import WorkMeta from "../components/WorkMeta.svelte";
  /**
   * GAP-CHAT C18 — the cross-chat surface.
   *
   * This page could search titles and message text, which answers *"where did I
   * say that"*. It could not answer *"what am I working on"*: there was no view
   * across projects, and no way to reach — let alone resume — the threads a
   * routine is advancing on its own. Those threads did not exist as threads
   * until C11 gave each task a conversation; now they do, and this is where an
   * owner finds them without going through Tasks first.
   *
   * **NEW-THREAD-01 — the index moved to the server.** The board was one
   * unpaginated read of a hundred rows, and both the filters and the results
   * were derived from whatever arrived. Three things followed, and each read as
   * a fact about the workspace rather than about the read: a project whose
   * newest thread fell outside that page was not offered as a filter at all;
   * the window looked like the whole inventory; and typing called an unscoped
   * search that hid the filters, so narrowing something down silently widened
   * it.
   *
   * Now: `GET /api/work-threads/page` filters, facets over everything that
   * matched, and pages. The filters stay on screen while typing and stay
   * applied — a project chosen before the first keystroke is still chosen after
   * it.
   *
   * **Two searches, and they answer different questions.** Typing narrows this
   * board by title, inside the filters. *"Where did I say that"* is a different
   * question — it reads message text, across every conversation the account
   * has — so it is an explicit action rather than something that happens to the
   * owner mid-keystroke.
   *
   * **BUG-303 — the library lives here now.** Rename, move to a project, pin,
   * archive and tag were on Sessions, which is the page whose job is *audit*.
   * Organising the conversations you work in is not an audit activity, and the
   * page work is actually resumed from could not express any of it. The four
   * controls and the tag editor moved here, where the threads are; Sessions
   * keeps only **Delete**, because deleting removes the evidence record and
   * belongs beside the evidence.
   *
   * Archive could not move until the index could show an archived thread —
   * a control whose effect the owner cannot undo from the surface they used it
   * on is worse than one that has not moved. It can: `archived` is a scope on
   * the index, both counts come back in either scope, and the chip that
   * switches between them is the way back.
   *
   * A routine thread is a task's own conversation, not something in the
   * owner's library, so it is offered none of these.
   */
  import { onMount } from "svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import {
    archiveConfirmation,
    command,
    commandFailure,
    type CommandId,
  } from "../conversationCommands";
  import type { ProjectView, SessionSummary, WorkThread, WorkThreadPage } from "../apiTypes";
  import { groupByDay, relativeTime } from "../format";
  import { cadenceLabel } from "../agentCadence";
  import { conversationLink, evidenceLink, workModeRoute } from "../turnAnchor";

  type Scope = "all" | "chat" | "routine";

  /** REM-THREAD-03 — what a row calls the surface it will open on. */
  const WORK_MODE_NAMES = { "new-chat": "Chat", build: "Build", design: "Design" } as const;

  let page = $state<WorkThreadPage | null>(null);
  let threads = $state<WorkThread[]>([]);
  /** Results of the explicit message-text search, when one has been run. */
  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);
  let query = $state("");
  let searching = $state(false);
  let loadingMore = $state(false);
  let scope = $state<Scope>("all");
  let projectFilter = $state<string>("");
  let requestId = 0;

  // ── BUG-303: the conversation library ──────────────────────────────────
  /** Which archive scope is on screen. A scope, not a filter: the sets are disjoint. */
  let archivedScope = $state(false);
  /** The thread whose library controls are open, or null. One at a time. */
  let openMenu = $state<string | null>(null);
  /** The thread being renamed inline, and the draft title. */
  let renaming = $state<string | null>(null);
  let titleDraft = $state("");
  /** Per-thread tag drafts, so typing in one row does not appear in another. */
  let tagDraft = $state<Record<string, string>>({});
  /** Projects a thread can be moved into. Degrades to none rather than failing. */
  let projects_ = $state<ProjectView[]>([]);
  let actionError = $state<string | null>(null);
  let busy = $state<string | null>(null);

  const groupedSessions = $derived(groupByDay(sessions ?? []));

  /**
   * The projects the index says have work, not the ones this page happens to be
   * holding. That difference is the finding: a facet derived from the loaded
   * rows can only ever offer what is already on screen.
   */
  const projects = $derived(page?.projects ?? []);
  const routineCount = $derived(
    page?.kinds.find((facet) => facet.value === "routine")?.count ?? 0,
  );
  const loaded = $derived(threads.length);
  const total = $derived(page?.total ?? 0);

  async function read(cursor: string | null): Promise<void> {
    const id = ++requestId;
    if (cursor === null) searching = true;
    else loadingMore = true;
    loadError = null;
    try {
      const result = await api.workThreadPage({
        projectId: projectFilter || null,
        kind: scope === "all" ? null : scope,
        query: query.trim(),
        cursor,
        archived: archivedScope,
      });
      if (id !== requestId) return;
      page = result;
      // A cursor page appends; a new question replaces. Appending to a
      // different question is how a list comes to hold two answers at once.
      threads = cursor === null ? result.threads : [...threads, ...result.threads];
    } catch (error) {
      if (id !== requestId) return;
      page = null;
      threads = [];
      loadError = error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
    } finally {
      if (id === requestId) {
        searching = false;
        loadingMore = false;
      }
    }
  }

  // Every filter and the query are one question; changing any of them asks it
  // again from the first page. Debounced only for typing, because a chip is a
  // decision and a keystroke is not.
  $effect(() => {
    const typed = query.trim();
    void projectFilter;
    void scope;
    void archivedScope;
    const timer = window.setTimeout(() => void read(null), typed ? 180 : 0);
    return () => window.clearTimeout(timer);
  });

  // The move-to-project control needs somewhere to move things to. A failure
  // here must not take the board down with it, so it degrades to "no projects".
  onMount(() => {
    void (async () => {
      try {
        projects_ = (await api.projects()).projects.filter((project) => !project.is_archived);
      } catch {
        projects_ = [];
      }
    })();
  });

  /**
   * Run one library mutation and re-read the page it changed.
   *
   * Re-reading rather than patching the row in place: a pin changes the order,
   * an archive moves the thread to the other scope, and a move changes the
   * project facet counts. Every one of those is the index's answer, not
   * something the browser can derive — which is the whole reason the index
   * moved to the server.
   */
  async function organise(
    sessionId: string,
    id: CommandId,
    run: () => Promise<unknown>,
  ): Promise<void> {
    // BUG-306 — the command says what it is, whether it is confirmed, and how
    // it reads when it fails. This page renders and calls; it no longer also
    // decides.
    actionError = null;
    busy = sessionId;
    try {
      await run();
      // The menu's job is done, and the list behind it is about to change:
      // leaving it open over a row that may have moved or left the scope is a
      // control pointing at something that is no longer there.
      openMenu = null;
      await read(null);
    } catch (error) {
      actionError = commandFailure(id, error instanceof ApiError ? error.status : undefined);
    } finally {
      busy = null;
    }
  }

  /**
   * BUG-306 — archiving takes a thread off the board it is resumed from, which
   * is the one library command whose effect an owner can lose track of. The
   * command set says it confirms; the question it asks says what is kept.
   */
  async function archiveOrRestore(thread: WorkThread): Promise<void> {
    const id: CommandId = thread.archived ? "restore" : "archive";
    if (command(id).confirms && !window.confirm(archiveConfirmation(thread.title))) return;
    await organise(thread.session_id, id, () =>
      thread.archived
        ? api.unarchiveSession(thread.session_id)
        : api.archiveSession(thread.session_id),
    );
  }

  function startRename(thread: WorkThread): void {
    renaming = thread.session_id;
    titleDraft = thread.title;
    openMenu = null;
  }

  async function commitRename(thread: WorkThread): Promise<void> {
    const next = titleDraft.trim();
    renaming = null;
    if (!next || next === thread.title) return;
    await organise(thread.session_id, "rename", () =>
      api.renameSession(thread.session_id, next),
    );
  }

  async function addTag(thread: WorkThread): Promise<void> {
    const draft = (tagDraft[thread.session_id] ?? "").trim();
    if (!draft || thread.tags.includes(draft)) return;
    tagDraft[thread.session_id] = "";
    await organise(thread.session_id, "tag", () =>
      api.setSessionTags(thread.session_id, [...thread.tags, draft]),
    );
  }

  async function removeTag(thread: WorkThread, tag: string): Promise<void> {
    await organise(thread.session_id, "untag", () =>
      api.setSessionTags(
        thread.session_id,
        thread.tags.filter((item) => item !== tag),
      ),
    );
  }

  /**
   * The other question. Deliberately an action rather than a mode the owner
   * falls into: it reads message text across every conversation the account
   * has, which is not a narrowing of the board and must not silently replace it.
   */
  async function searchMessageText(): Promise<void> {
    const typed = query.trim();
    if (!typed) return;
    searching = true;
    loadError = null;
    try {
      const result = await api.searchChats(typed);
      sessions = [...result].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    } catch (error) {
      sessions = null;
      loadError = error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
    } finally {
      searching = false;
    }
  }
</script>

<section class="search-chat">
  <!-- The topbar already carries this destination's name and what it is for.
       Repeating both here was two lines of the same sentence above an empty
       page; the search box is what the owner came for. -->
  <header>
    <GuideLink route="search-chat" />
  </header>
  <label class="search-field">
    <span class="sr-only">Search chat history</span>
    <input
      type="search"
      placeholder="Search titles and messages…"
      bind:value={query}
      aria-label="Search chat history"
    />
  </label>

  <!-- NEW-THREAD-01 — the filters stay while typing. Hiding them was an
       implicit scope switch: the owner narrowed by project, started typing, and
       the project quietly stopped applying. -->
  {#if page !== null}
    <div class="filters">
      <div class="scopes" role="group" aria-label="Show">
        {#each [["all", "All"], ["chat", "Chats"], ["routine", "Routines"]] as [id, label] (id)}
          <button
            type="button"
            class="chip"
            class:on={scope === id}
            aria-pressed={scope === id}
            onclick={() => (scope = id as Scope)}
            disabled={id === "routine" && routineCount === 0}>{label}</button
          >
        {/each}
      </div>
      {#if projects.length > 0}
        <label class="project-filter">
          <span class="sr-only">Filter by project</span>
          <select bind:value={projectFilter} aria-label="Filter by project">
            <option value="">All projects</option>
            <!-- Every project the index has work in, not only the ones on this
                 page. A project whose newest thread is a hundred rows down was
                 previously not offered at all. -->
            {#each projects as facet (facet.value)}
              <option value={facet.value}>{facet.label} ({facet.count})</option>
            {/each}
          </select>
        </label>
      {/if}
      {#if query.trim()}
        <button type="button" class="chip search-text" onclick={() => void searchMessageText()}>
          Search message text
        </button>
      {/if}
      <!-- BUG-303 — the way back. Archive only became movable off Sessions once
           an archived thread could be seen and restored from the same page that
           archived it. -->
      {#if archivedScope || (page?.archived_count ?? 0) > 0}
        <button
          type="button"
          class="chip archive-scope"
          class:on={archivedScope}
          aria-pressed={archivedScope}
          onclick={() => (archivedScope = !archivedScope)}
        >
          {archivedScope
            ? `Back to active (${page?.active_count ?? 0})`
            : `Archived (${page?.archived_count ?? 0})`}
        </button>
      {/if}
    </div>
  {/if}

  {#if actionError}
    <p class="action-error" role="alert">{actionError}</p>
  {/if}

  {#if loadError}
    <PageState state="error" title="Couldn't load your threads" detail={loadError} />
  {:else if searching && page === null}
    <PageState state="loading" title="Loading your threads…" />
  {:else if sessions !== null}
    <!-- The other question's answer, shown as its own thing with a way back.
         It reads message text across every conversation the account has, so
         presenting it as a narrowing of the board would misstate its scope. -->
    <div class="message-results">
      <p class="result-count">
        {sessions.length} conversation{sessions.length === 1 ? "" : "s"} mention “{query.trim()}”
        <button type="button" class="chip" onclick={() => (sessions = null)}>
          Back to your threads
        </button>
      </p>
      {#each groupedSessions as group (group.label)}
        <section class="day-group" aria-label={group.label}>
          <h3>{group.label}</h3>
          <ul>
            {#each group.items as session (session.session_id)}
              <!-- MEM-08 — a result that knows which exchange matched opens on
                   it. The coordinate was already returned as `match_turn_id`; it
                   had nowhere to go, so verifying a recalled claim meant opening
                   the conversation at the top and scrolling. -->
              <li>
                <a
                  href={conversationLink(
                    workModeRoute(session.origin),
                    session.session_id,
                    session.match_turn_id,
                  )}
                >
                  <span class="title">{session.title?.trim() || "Untitled chat"}</span>
                  <span class="meta"
                    >{session.turn_count} turn{session.turn_count === 1 ? "" : "s"} · {relativeTime(
                      session.updated_at,
                    )} · {session.match_turn_id ? "Open the match" : "Open"} →</span
                  >
                  {#if session.match_snippet}<span class="matched">“{session.match_snippet}”</span
                    >{/if}
                </a>
                <span class="row-links">
                  <a
                    class="row-link"
                    href={evidenceLink(session.session_id, session.match_turn_id)}>Evidence</a
                  >
                </span>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
      {#if sessions.length === 0}
        <EmptyState title="No matching conversations" body="Try a different search term." />
      {/if}
    </div>
  {:else if total === 0 && !query.trim() && projectFilter === "" && scope === "all"}
    <EmptyState
      title="Nothing going yet"
      body="Every chat and routine you have running shows up here."
    >
      {#snippet action()}
        <a class="btn btn-primary" href="#/new-chat">Start a chat</a>
      {/snippet}
    </EmptyState>
  {:else if total === 0}
    <EmptyState title="Nothing in this view" body="Widen the filters to see your other threads." />
  {:else}
    <!-- NEW-THREAD-01 — the count is what matched, and the page says what it is
         showing of it. A window that reads as an inventory is a count nobody
         stated. -->
    <p class="result-count">
      {#if loaded < total}Showing {loaded} of {total} threads{:else}{total} thread{total === 1
          ? ""
          : "s"}{/if}{#if page?.scan_truncated}
        · most recent threads only{/if}
    </p>
    <ul class="threads">
      {#each threads as thread (thread.session_id)}
        <li class:blocked={thread.waiting_on}>
          <!-- REM-THREAD-03 — a thread is resumed where it was done. Every row
               used to point at Chat, so a Build conversation opened on a screen
               that cannot show its repository, its pending diffs or the
               approvals over them. -->
          <a href={conversationLink(workModeRoute(thread.origin), thread.session_id)}>
            <span class="title">
              {#if thread.kind === "routine"}<Icon name="tasks" size="sm" />{/if}
              <!-- BUG-303 — a pin that is only an ordering is not readable as a
                   pin: the owner cannot tell a pinned thread from the newest
                   one. It says so on the row, with the mark Sessions has always
                   used for the same state. -->
              {#if thread.pinned}<span class="pin-mark" title="Pinned" aria-label="Pinned"
                  >★</span
                >{/if}
              {thread.title}
            </span>
            <!-- Project, state, last activity, in the one order every
                 surface that draws a piece of work now uses. -->
            <WorkMeta
              project={thread.project_name}
              state={thread.waiting_on ?? (thread.cadence ? cadenceLabel(thread.cadence) : null)}
              stateVariant={thread.waiting_on ? "approval-required" : "metadata-only"}
              detail={`${WORK_MODE_NAMES[workModeRoute(thread.origin)]} · ${thread.turn_count} turn${thread.turn_count === 1 ? "" : "s"}`}
              activityAt={thread.updated_at}
            />
          </a>
          <!-- BUG-303 — the tags are part of the row because they are how the
               owner finds it again, not a setting hidden behind a menu. -->
          {#if thread.tags.length > 0}
            <ul class="tags" aria-label="Tags">
              {#each thread.tags as tag (tag)}
                <li>
                  <span class="tag">{tag}</span>
                  <button
                    type="button"
                    class="tag-remove"
                    aria-label={`Remove tag ${tag} from ${thread.title}`}
                    disabled={busy === thread.session_id}
                    onclick={() => void removeTag(thread, tag)}>×</button
                  >
                </li>
              {/each}
            </ul>
          {/if}
          <!-- REM-THREAD-03 — the other job, kept out of the row's own reading
               order. Threads resumes work; the inspector verifies how it ran,
               and it is a link rather than the destination of the row. -->
          <span class="row-links">
            {#if thread.task_id}
              <a class="row-link" href={`#/tasks?task=${encodeURIComponent(thread.task_id)}`}
                >Task detail</a
              >
            {/if}
            <a class="row-link" href={evidenceLink(thread.session_id)}>Evidence</a>
            <!-- BUG-303 — a routine thread belongs to its task, not to the
                 owner's library, so it is offered none of this. -->
            {#if thread.kind === "chat"}
              <button
                type="button"
                class="row-link organise"
                aria-expanded={openMenu === thread.session_id}
                aria-label={`Organise ${thread.title}`}
                disabled={busy === thread.session_id}
                onclick={() =>
                  (openMenu = openMenu === thread.session_id ? null : thread.session_id)}
                >Organise</button
              >
            {/if}
          </span>
          {#if thread.kind === "chat" && openMenu === thread.session_id}
            <div class="library" role="group" aria-label={`Organise ${thread.title}`}>
              <button
                type="button"
                class="chip"
                disabled={busy === thread.session_id}
                onclick={() =>
                  void organise(thread.session_id, thread.pinned ? "unpin" : "pin", () =>
                    api.setSessionPinned(thread.session_id, !thread.pinned),
                  )}>{thread.pinned ? "Unpin" : "Pin"}</button
              >
              <button type="button" class="chip" onclick={() => startRename(thread)}>Rename</button>
              <button
                type="button"
                class="chip"
                disabled={busy === thread.session_id}
                onclick={() =>
                  void archiveOrRestore(thread)}>{thread.archived ? "Restore" : "Archive"}</button
              >
              {#if projects_.length > 0}
                <label class="move">
                  <span class="sr-only">Move {thread.title} to a project</span>
                  <select
                    value={thread.project_id ?? ""}
                    disabled={busy === thread.session_id}
                    aria-label={`Move ${thread.title} to a project`}
                    onchange={(event) =>
                      void organise(thread.session_id, "move", () =>
                        api.setSessionProject(
                          thread.session_id,
                          (event.currentTarget as HTMLSelectElement).value || null,
                        ),
                      )}
                  >
                    <option value="">No project</option>
                    {#each projects_ as project (project.project_id)}
                      <option value={project.project_id}>{project.name}</option>
                    {/each}
                  </select>
                </label>
              {/if}
              <label class="add-tag">
                <span class="sr-only">Add a tag to {thread.title}</span>
                <input
                  type="text"
                  placeholder="Add a tag…"
                  aria-label={`Add a tag to ${thread.title}`}
                  bind:value={tagDraft[thread.session_id]}
                  disabled={busy === thread.session_id}
                  onkeydown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void addTag(thread);
                    }
                  }}
                />
              </label>
            </div>
          {/if}
          {#if renaming === thread.session_id}
            <form
              class="rename"
              onsubmit={(event) => {
                event.preventDefault();
                void commitRename(thread);
              }}
            >
              <label>
                <span class="sr-only">New title for {thread.title}</span>
                <input
                  type="text"
                  bind:value={titleDraft}
                  aria-label={`New title for ${thread.title}`}
                />
              </label>
              <button type="submit" class="chip">Save</button>
              <button type="button" class="chip" onclick={() => (renaming = null)}>Cancel</button>
            </form>
          {/if}
        </li>
      {/each}
    </ul>
    {#if page?.next_cursor}
      <button
        type="button"
        class="btn load-more"
        disabled={loadingMore}
        onclick={() => void read(page?.next_cursor ?? null)}
      >
        {loadingMore ? "Loading…" : "Load more"}
      </button>
    {/if}
  {/if}
</section>

<style>
  .search-chat {
    width: 100%;
  }
  header {
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    gap: var(--space-4);
    margin-bottom: var(--space-3);
  }
  .search-field {
    display: block;
    max-width: 38rem;
    margin-bottom: var(--space-3);
  }
  input {
    width: 100%;
    background: var(--surface);
  }
  .filters {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .scopes {
    display: flex;
    gap: 0.3rem;
  }
  .chip {
    padding: 0.25rem 0.7rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    font-size: var(--text-sm);
    cursor: pointer;
  }
  .chip.on {
    background: var(--accent-soft);
    border-color: var(--accent-border);
    color: var(--text-1);
  }
  .chip:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .project-filter select {
    background: var(--surface);
  }
  .result-count {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin: 0 0 var(--space-4);
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  /* The message-text search is a different question with a different scope, so
     its answer is its own block with a way back rather than a mode the board
     silently becomes. */
  .message-results {
    display: contents;
  }
  .load-more {
    margin-top: var(--space-4);
  }
  .day-group {
    margin-top: var(--space-5);
  }
  /* A day heading in a list of threads is a section label. Size and
     colour separate it from the rows; caps and wide tracking were a third and
     fourth device for the same job. */
  h3 {
    margin: 0 0 var(--space-2);
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    border-top: 1px solid var(--border);
  }
  li {
    border-bottom: 1px solid var(--border);
  }
  li a {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.2rem var(--space-4);
    padding: var(--space-3) var(--space-2);
    border-radius: var(--r-sm);
    color: var(--text-1);
    text-decoration: none;
  }
  li a:hover {
    background: var(--sunken);
    text-decoration: none;
  }
  .title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 650;
    min-width: 0;
  }
  .meta,
  .matched {
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  /* REM-THREAD-03 — the secondary destinations sit under the row rather than
     inside its link, at one quiet weight: resuming the work is the row, and
     verifying how it ran is a link beside it. */
  .row-links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    /* Tucked under the row's title rather than given a line of its own: the
       row is the work, and a secondary destination that doubles every row's
       height turns a board into a list of pairs. */
    margin-top: -0.55rem;
    padding: 0 var(--space-2) var(--space-2);
  }
  .row-link {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .row-link:hover,
  .row-link:focus-visible {
    color: var(--accent);
  }
  .matched {
    grid-column: 1/-1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ── BUG-303: the conversation library ──────────────────────────────── */
  .action-error {
    color: var(--danger);
    font-size: var(--text-sm);
    margin: 0 0 var(--space-3);
  }
  .organise {
    background: none;
    border: 0;
    padding: 0;
    cursor: pointer;
    font: inherit;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .organise:hover,
  .organise:focus-visible {
    color: var(--accent);
  }
  .tags,
  .library,
  .rename {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding: 0 var(--space-2) var(--space-2);
    margin: 0;
    list-style: none;
  }
  .tags li {
    display: inline-flex;
    align-items: center;
    gap: 0.15rem;
  }
  /* The same chip Sessions draws, because it is the same tag: one label should
     not look like two different things depending on which page reads it. */
  .tag {
    display: inline-flex;
    align-items: center;
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    color: var(--text-1);
    border-radius: 999px;
    font-size: var(--text-xs);
    line-height: 1.4;
    padding: 0.05rem 0.45rem;
  }
  .tag-remove {
    background: none;
    border: 0;
    color: var(--text-3);
    cursor: pointer;
    font-size: var(--text-xs);
    line-height: 1;
    padding: 0 0.15rem;
  }
  .tag-remove:hover,
  .tag-remove:focus-visible {
    color: var(--danger);
  }
  .library {
    border-top: 1px solid var(--border);
    padding-top: var(--space-2);
  }
  .library select,
  .library input,
  .rename input {
    background: var(--surface);
    font-size: var(--text-sm);
  }
  .pin-mark {
    color: var(--accent);
    margin-right: 0.2rem;
  }

  @media (max-width: 42rem) {
    li a {
      grid-template-columns: 1fr;
    }
    .matched {
      grid-column: auto;
    }
    /* The controls stack rather than overflow: a menu that scrolls sideways on
       a phone is a menu whose last item does not exist. */
    .library {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
