<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary } from "../apiTypes";
  import { groupByDay, relativeTime } from "../format";

  let sessions = $state<SessionSummary[] | null>([]);
  let loadError = $state<string | null>(null);
  let query = $state("");
  let searching = $state(false);
  let requestId = 0;
  const groupedSessions = $derived(groupByDay(sessions ?? []));

  $effect(() => {
    const q = query.trim();
    const id = ++requestId;
    if (!q) { sessions = []; searching = false; return; }
    searching = true;
    const timer = window.setTimeout(() => void (async () => {
      try { loadError = null; const result = await api.searchChats(q); if (id === requestId) sessions = result; }
      catch (e) { if (id === requestId) { sessions = null; loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable"; } }
      finally { if (id === requestId) searching = false; }
    })(), 180);
    return () => window.clearTimeout(timer);
  });
</script>

<section class="search-chat">
  <header><p class="page-lead">Search titles and message text across every conversation you have had, then continue exactly where you left off.</p><input type="search" placeholder="Search your chat history…" bind:value={query} aria-label="Search chat history" /></header>
  {#if loadError}<PageState state="error" title="Couldn't search chats" detail={loadError} />
  {:else if query.trim() === ""}<EmptyState title="Search your chats" body="Enter words from a conversation title or message." />
  {:else if searching || sessions === null}<PageState state="loading" title="Searching your chats…" />
  {:else if sessions.length === 0}<EmptyState title="No matching conversations" body="Try a different search term." />
  {:else}<p class="result-count">{sessions.length} matching conversation{sessions.length === 1 ? "" : "s"}</p>{#each groupedSessions as group (group.label)}<section class="day-group" aria-label={group.label}><h3>{group.label}</h3><ul>{#each group.items as s (s.session_id)}<li><a href={`#/new-chat?session=${encodeURIComponent(s.session_id)}`}><span class="title">{s.title ?? "Untitled chat"}</span><span class="meta">{s.turn_count} turns · {relativeTime(s.updated_at)} · Open conversation →</span>{#if s.match_snippet}<span class="matched">“{s.match_snippet}”</span>{/if}</a></li>{/each}</ul></section>{/each}{/if}
</section>

<style>.search-chat{max-width:52rem}.search-chat header{align-items:end;display:flex;gap:var(--space-4);justify-content:space-between;margin-bottom:var(--space-5)}.search-chat header .page-lead{margin:0;max-width:32rem}input{background:var(--surface);border:1px solid var(--neutral-border);border-radius:var(--r-md);flex:0 1 19rem;padding:var(--space-2) var(--space-3)}.day-group{margin-top:var(--space-4)}h3{color:var(--text-2);font-size:.78rem;letter-spacing:.04em;margin:0 0 var(--space-2);text-transform:uppercase}ul{display:grid;gap:.45rem;list-style:none;margin:0;padding:0}li a{border:1px solid var(--border);border-radius:var(--r-md);display:grid;grid-template-columns:1fr auto;gap:.2rem var(--space-3);padding:var(--space-3);color:var(--text-1);text-decoration:none}.title{font-weight:650}.meta,.result-count{color:var(--text-2);font-size:.8rem}.matched{grid-column:1/-1;color:var(--text-2);font-size:.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}@media(max-width:42rem){.search-chat header{align-items:stretch;flex-direction:column}input{flex:auto}}</style>
