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
   */
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary, WorkThread, WorkThreadPage } from "../apiTypes";
  import { groupByDay, relativeTime } from "../format";
  import { cadenceLabel } from "../agentCadence";
  import { conversationLink } from "../turnAnchor";

  type Scope = "all" | "chat" | "routine";

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
    const timer = window.setTimeout(() => void read(null), typed ? 180 : 0);
    return () => window.clearTimeout(timer);
  });

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
    </div>
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
                <a href={conversationLink("new-chat", session.session_id, session.match_turn_id)}>
                  <span class="title">{session.title?.trim() || "Untitled chat"}</span>
                  <span class="meta"
                    >{session.turn_count} turn{session.turn_count === 1 ? "" : "s"} · {relativeTime(
                      session.updated_at,
                    )} · {session.match_turn_id ? "Open the match" : "Open"} →</span
                  >
                  {#if session.match_snippet}<span class="matched">“{session.match_snippet}”</span
                    >{/if}
                </a>
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
          <a href={`#/new-chat?session=${encodeURIComponent(thread.session_id)}`}>
            <span class="title">
              {#if thread.kind === "routine"}<Icon name="tasks" size="sm" />{/if}
              {thread.title}
            </span>
            <!-- VIS-14 — project, state, last activity, in the one order every
                 surface that draws a piece of work now uses. -->
            <WorkMeta
              project={thread.project_name}
              state={thread.waiting_on ?? (thread.cadence ? cadenceLabel(thread.cadence) : null)}
              stateVariant={thread.waiting_on ? "approval-required" : "metadata-only"}
              detail={`${thread.turn_count} turn${thread.turn_count === 1 ? "" : "s"}`}
              activityAt={thread.updated_at}
            />
          </a>
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
  /* VIS-06 — a day heading in a list of threads is a section label. Size and
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
  .matched {
    grid-column: 1/-1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  @media (max-width: 42rem) {
    li a {
      grid-template-columns: 1fr;
    }
    .matched {
      grid-column: auto;
    }
  }
</style>
