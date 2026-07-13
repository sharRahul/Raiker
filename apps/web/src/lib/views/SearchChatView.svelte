<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary } from "../apiTypes";
  import { relativeTime } from "../format";

  let sessions = $state<SessionSummary[] | null>([]);
  let loadError = $state<string | null>(null);
  let query = $state("");

  $effect(() => {
    const q = query.trim();
    if (!q) { sessions = []; return; }
    void (async () => {
      try { loadError = null; sessions = await api.searchChats(q); }
      catch (e) { sessions = null; loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable"; }
    })();
  });
</script>

<section class="search-chat">
  <header><h2>Search Chat</h2><input type="search" placeholder="Search your chat history…" bind:value={query} aria-label="Search chat history" /></header>
  {#if loadError}<p class="error" role="alert">{loadError}</p>
  {:else if query.trim() === ""}<EmptyState title="Search your chats" body="Enter words from a conversation title or message." />
  {:else if sessions === null}<p role="status">Loading history…</p>
  {:else if sessions.length === 0}<EmptyState title="No matching conversations" body="Try a different search term." />
  {:else}<ul>{#each sessions as s (s.session_id)}<li><a href={`#/new-chat?session=${encodeURIComponent(s.session_id)}`}><span class="title">{s.title ?? "Untitled chat"}</span><span class="meta">{s.turn_count} turns · {relativeTime(s.updated_at)}</span></a></li>{/each}</ul>{/if}
</section>

<style>.search-chat{max-width:48rem}header{display:flex;gap:var(--space-4);margin-bottom:var(--space-4)}input{flex:1;padding:var(--space-2) var(--space-3)}ul{list-style:none;padding:0}li a{display:flex;justify-content:space-between;padding:var(--space-2) var(--space-3);color:var(--text-1);text-decoration:none}.title{font-weight:600}.meta,.error{color:var(--text-2)}.error{color:var(--danger)}</style>
