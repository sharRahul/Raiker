<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
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
  <header><div><p class="eyebrow">Conversation library</p><h2>Find a chat</h2><p>Search titles and message text, then continue exactly where you left off.</p></div><input type="search" placeholder="Search your chat history…" bind:value={query} aria-label="Search chat history" /></header>
  {#if loadError}<p class="error" role="alert">{loadError}</p>
  {:else if query.trim() === ""}<EmptyState title="Search your chats" body="Enter words from a conversation title or message." />
  {:else if searching || sessions === null}<p role="status">Searching your chats…</p>
  {:else if sessions.length === 0}<EmptyState title="No matching conversations" body="Try a different search term." />
  {:else}<p class="result-count">{sessions.length} matching conversation{sessions.length === 1 ? "" : "s"}</p>{#each groupedSessions as group (group.label)}<section class="day-group" aria-label={group.label}><h3>{group.label}</h3><ul>{#each group.items as s (s.session_id)}<li><a href={`#/new-chat?session=${encodeURIComponent(s.session_id)}`}><span class="title">{s.title ?? "Untitled chat"}</span><span class="meta">{s.turn_count} turns · {relativeTime(s.updated_at)} · Open conversation →</span></a></li>{/each}</ul></section>{/each}{/if}
</section>

<style>.search-chat{max-width:52rem}.search-chat header{align-items:end;display:flex;gap:var(--space-4);justify-content:space-between;margin-bottom:var(--space-5)}h2{margin:0}.eyebrow{color:var(--accent);font-size:.7rem;font-weight:750;letter-spacing:.08em;margin:0 0 .25rem;text-transform:uppercase}header p{color:var(--text-3);font-size:.84rem;margin:.3rem 0 0}input{background:var(--surface);border:1px solid var(--neutral-border);border-radius:var(--r-md);flex:0 1 19rem;padding:var(--space-2) var(--space-3)}.day-group{margin-top:var(--space-4)}h3{color:var(--text-2);font-size:.78rem;letter-spacing:.04em;margin:0 0 var(--space-2);text-transform:uppercase}ul{display:grid;gap:.45rem;list-style:none;margin:0;padding:0}li a{border:1px solid var(--border);border-radius:var(--r-md);display:flex;justify-content:space-between;padding:var(--space-3);color:var(--text-1);text-decoration:none}.title{font-weight:650}.meta,.result-count{color:var(--text-2);font-size:.8rem}.error{color:var(--danger)}@media(max-width:42rem){.search-chat header{align-items:stretch;flex-direction:column}input{flex:auto}}</style>
