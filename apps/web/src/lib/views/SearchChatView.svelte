<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary } from "../apiTypes";
  import { groupByDay, relativeTime } from "../format";

  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);
  let query = $state("");
  let searching = $state(false);
  let requestId = 0;
  const groupedSessions = $derived(groupByDay(sessions ?? []));

  $effect(() => {
    const q = query.trim();
    const id = ++requestId;
    searching = true;
    loadError = null;
    const timer = window.setTimeout(() => void (async () => {
      try {
        const result = q ? await api.searchChats(q) : await api.sessions(undefined, false, "chat");
        if (id === requestId) {
          sessions = [...result].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
        }
      } catch (error) {
        if (id === requestId) {
          sessions = null;
          loadError = error instanceof ApiError ? `Unavailable (${error.status})` : "Unavailable";
        }
      } finally {
        if (id === requestId) searching = false;
      }
    })(), q ? 180 : 0);
    return () => window.clearTimeout(timer);
  });
</script>

<section class="search-chat">
  <header>
    <div><p class="kicker">Conversation history</p><p class="intro">Browse recent conversations or search their titles and messages.</p></div>
    <GuideLink route="search-chat" />
  </header>
  <label class="search-field">
    <span class="sr-only">Search chat history</span>
    <input type="search" placeholder="Search titles and messages…" bind:value={query} aria-label="Search chat history" />
  </label>

  {#if loadError}<PageState state="error" title={query.trim() ? "Couldn't search chats" : "Couldn't load chats"} detail={loadError} />
  {:else if searching || sessions === null}<PageState state="loading" title={query.trim() ? "Searching your chats…" : "Loading your chats…"} />
  {:else if sessions.length === 0}<EmptyState title={query.trim() ? "No matching conversations" : "No conversations yet"} body={query.trim() ? "Try a different search term." : "Start a conversation and it will appear here."} />
  {:else}
    <p class="result-count">{sessions.length} {query.trim() ? "matching " : ""}conversation{sessions.length === 1 ? "" : "s"}</p>
    {#each groupedSessions as group (group.label)}
      <section class="day-group" aria-label={group.label}>
        <h3>{group.label}</h3>
        <ul>
          {#each group.items as session (session.session_id)}
            <li><a href={`#/new-chat?session=${encodeURIComponent(session.session_id)}`}>
              <span class="title">{session.title?.trim() || "Untitled chat"}</span>
              <span class="meta">{session.turn_count} turn{session.turn_count === 1 ? "" : "s"} · {relativeTime(session.updated_at)} · Open conversation →</span>
              {#if session.match_snippet}<span class="matched">“{session.match_snippet}”</span>{/if}
            </a></li>
          {/each}
        </ul>
      </section>
    {/each}
  {/if}
</section>

<style>
  .search-chat { width:100%; }
  header { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-4); margin-bottom:var(--space-4); }
  .intro { max-width:var(--prose-measure); margin:0; color:var(--text-2); }
  .search-field { display:block; max-width:38rem; margin-bottom:var(--space-5); }
  input { width:100%; background:var(--surface); }
  .result-count { margin:0 0 var(--space-4); color:var(--text-2); font-size:var(--text-sm); }
  .day-group { margin-top:var(--space-5); }
  h3 { margin:0 0 var(--space-2); color:var(--text-3); font-size:var(--text-xs); letter-spacing:var(--tracking-wide); text-transform:uppercase; }
  ul { list-style:none; margin:0; padding:0; border-top:1px solid var(--border); }
  li { border-bottom:1px solid var(--border); }
  li a { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:.2rem var(--space-4); padding:var(--space-3) var(--space-2); border-radius:var(--r-sm); color:var(--text-1); text-decoration:none; }
  li a:hover { background:var(--sunken); text-decoration:none; }
  .title { font-weight:650; }
  .meta,.matched { color:var(--text-2); font-size:var(--text-sm); }
  .matched { grid-column:1/-1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  @media(max-width:42rem) { header { flex-direction:column; } li a { grid-template-columns:1fr; } .matched { grid-column:auto; } }
</style>
