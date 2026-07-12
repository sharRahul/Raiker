<script lang="ts">
  import EmptyState from "../components/EmptyState.svelte";
  import { api, ApiError } from "../api";
  import type { SessionSummary } from "../apiTypes";
  import { relativeTime, shortId } from "../format";

  // Dedicated history search over past chat sessions. Reads the real governed
  // sessions list and filters/categorises client-side — no fabricated data.
  let sessions = $state<SessionSummary[] | null>(null);
  let loadError = $state<string | null>(null);
  let query = $state("");

  async function load() {
    loadError = null;
    try {
      sessions = await api.sessions();
    } catch (e) {
      sessions = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  const filtered = $derived(
    (sessions ?? []).filter((s) => {
      const q = query.trim().toLowerCase();
      if (!q) return true;
      return (
        (s.title ?? "").toLowerCase().includes(q) ||
        s.session_id.toLowerCase().includes(q) ||
        s.status.toLowerCase().includes(q)
      );
    }),
  );

  // Categorise by status so history reads as a grouped repository.
  const groups = $derived.by(() => {
    const byStatus = new Map<string, SessionSummary[]>();
    for (const s of filtered) {
      const list = byStatus.get(s.status) ?? [];
      list.push(s);
      byStatus.set(s.status, list);
    }
    return [...byStatus.entries()];
  });

  load();
</script>

<section class="search-chat">
  <header>
    <h2>Search Chat</h2>
    <input
      type="search"
      placeholder="Search your chat history…"
      bind:value={query}
      aria-label="Search chat history"
    />
  </header>

  {#if loadError}
    <p class="error" role="alert">{loadError}</p>
  {:else if sessions === null}
    <p class="loading" role="status">Loading history…</p>
  {:else if filtered.length === 0}
    <EmptyState title="No matching conversations" body="Try a different search term." />
  {:else}
    {#each groups as [status, items] (status)}
      <div class="group">
        <h3>{status}</h3>
        <ul>
          {#each items as s (s.session_id)}
            <li>
              <a href={`#/sessions`}>
                <span class="title">{s.title ?? shortId(s.session_id)}</span>
                <span class="meta">{s.turn_count} turns · {relativeTime(s.updated_at)}</span>
              </a>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  {/if}
</section>

<style>
  .search-chat {
    max-width: 48rem;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }
  input[type="search"] {
    flex: 1;
    max-width: 22rem;
    padding: var(--space-2) var(--space-3);
  }
  .group {
    margin-bottom: var(--space-5);
  }
  .group h3 {
    text-transform: capitalize;
    color: var(--text-2);
    margin-bottom: var(--space-2);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  li a {
    display: flex;
    justify-content: space-between;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-2);
    text-decoration: none;
    color: var(--text-1);
  }
  li a:hover {
    background: var(--bg-2);
  }
  .meta {
    color: var(--text-2);
  }
  .error {
    color: var(--danger);
  }
</style>
