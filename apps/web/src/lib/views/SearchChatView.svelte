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
   * Two modes, one page, and the mode follows the box:
   *
   *  - **Empty box — the board.** Every thread of work, newest first, from
   *    `GET /api/work-threads`: chats the owner started and routines advancing
   *    on their own, each naming its project and what it is blocked on.
   *  - **Typed query — the search.** Exactly what this page did before, over
   *    titles and message text, opening on the exchange that matched.
   *
   * The filters narrow the board, never the search: a search already names what
   * it is looking for, and a scope chip on top of it would be a second, silent
   * predicate on the same question.
   */
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary, WorkThread } from "../apiTypes";
  import { groupByDay, relativeTime } from "../format";
  import { cadenceLabel } from "../agentCadence";
  import { conversationLink } from "../turnAnchor";

  type Scope = "all" | "chat" | "routine";

  let threads = $state<WorkThread[] | null>(null);
  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);
  let query = $state("");
  let searching = $state(false);
  let scope = $state<Scope>("all");
  let projectFilter = $state<string>("");
  let requestId = 0;

  const searchMode = $derived(query.trim() !== "");
  const groupedSessions = $derived(groupByDay(sessions ?? []));

  /** Projects that actually hold a thread. A filter for an empty one is noise. */
  const projects = $derived(
    [
      ...new Map(
        (threads ?? [])
          .filter((t) => t.project_id && t.project_name)
          .map((t) => [t.project_id as string, t.project_name as string]),
      ),
    ].sort((a, b) => a[1].localeCompare(b[1])),
  );

  const visible = $derived(
    (threads ?? []).filter(
      (t) =>
        (scope === "all" || t.kind === scope) &&
        (projectFilter === "" || t.project_id === projectFilter),
    ),
  );

  const routineCount = $derived((threads ?? []).filter((t) => t.kind === "routine").length);

  $effect(() => {
    const q = query.trim();
    const id = ++requestId;
    searching = true;
    loadError = null;
    const timer = window.setTimeout(
      () =>
        void (async () => {
          try {
            if (q) {
              const result = await api.searchChats(q);
              if (id === requestId) {
                sessions = [...result].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
              }
            } else {
              const result = await api.workThreads();
              if (id === requestId) threads = result;
            }
          } catch (error) {
            if (id === requestId) {
              sessions = null;
              threads = null;
              loadError =
                error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
            }
          } finally {
            if (id === requestId) searching = false;
          }
        })(),
      q ? 180 : 0,
    );
    return () => window.clearTimeout(timer);
  });
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

  {#if !searchMode && threads !== null && threads.length > 0}
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
            {#each projects as [id, name] (id)}
              <option value={id}>{name}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>
  {/if}

  {#if loadError}
    <PageState
      state="error"
      title={searchMode ? "Couldn't search chats" : "Couldn't load your threads"}
      detail={loadError}
    />
  {:else if searching || (searchMode ? sessions === null : threads === null)}
    <PageState
      state="loading"
      title={searchMode ? "Searching your chats…" : "Loading your threads…"}
    />
  {:else if searchMode}
    {#if sessions === null || sessions.length === 0}
      <EmptyState title="No matching conversations" body="Try a different search term." />
    {:else}
      <p class="result-count">
        {sessions.length} matching conversation{sessions.length === 1 ? "" : "s"}
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
    {/if}
  {:else if threads === null || threads.length === 0}
    <EmptyState
      title="Nothing going yet"
      body="Every chat and routine you have running shows up here."
    >
      {#snippet action()}
        <a class="btn btn-primary" href="#/new-chat">Start a chat</a>
      {/snippet}
    </EmptyState>
  {:else if visible.length === 0}
    <EmptyState title="Nothing in this view" body="Widen the filters to see your other threads." />
  {:else}
    <p class="result-count">{visible.length} thread{visible.length === 1 ? "" : "s"}</p>
    <ul class="threads">
      {#each visible as thread (thread.session_id)}
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
    margin: 0 0 var(--space-4);
    color: var(--text-2);
    font-size: var(--text-sm);
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
