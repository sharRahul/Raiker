<script lang="ts">
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { MemoryControlView, MemorySettingsView } from "../apiTypes";
  import { relativeTime } from "../format";

  let memories = $state<MemoryControlView[] | null>(null);
  let loadError = $state<string | null>(null);
  let settings = $state<MemorySettingsView | null>(null);
  let actionError = $state<string | null>(null);
  let togglingIncognito = $state(false);

  async function load() {
    loadError = null;
    try {
      const [mems, set] = await Promise.all([api.memories(), api.memorySettings()]);
      memories = mems;
      settings = set;
    } catch (e) {
      memories = null;
      settings = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function toggleIncognito() {
    if (settings === null || togglingIncognito) return;
    actionError = null;
    togglingIncognito = true;
    try {
      const next = !settings.incognito;
      await api.setMemoryIncognito(next);
      settings = { incognito: next };
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not toggle incognito (${e.status}).` : "Could not toggle incognito.";
    } finally {
      togglingIncognito = false;
    }
  }

  async function togglePin(m: MemoryControlView) {
    actionError = null;
    try {
      await api.setMemoryPinned(m.memory_id, !m.pinned);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not update pin (${e.status}).` : "Could not update pin.";
    }
  }

  async function forget(m: MemoryControlView) {
    if (!window.confirm("Forget this memory permanently? It will be removed from the governed store and withheld from future context.")) return;
    actionError = null;
    try {
      await api.forgetMemory(m.memory_id);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not forget (${e.status}).` : "Could not forget.";
    }
  }

  // Pinned first, then most-recently-created.
  const ordered = $derived(
    memories === null
      ? null
      : [...memories].sort((a, b) => {
          if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
          return b.created_at.localeCompare(a.created_at);
        }),
  );

  $effect(() => {
    void load();
  });
</script>

<div class="head-row">
  <p class="page-lead">
    Approved memories the agent can recall. Each carries provenance, scope, and sensitivity.
    Pin the ones that matter; forget anything you do not want the agent to reuse.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh memories">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if settings !== null}
  <label class="incognito-row" title="When on, approved project memory is withheld from the turn context even if a project opted in. The memory is not deleted.">
    <input type="checkbox" checked={settings.incognito} disabled={togglingIncognito} onchange={() => void toggleIncognito()} />
    <span class="incognito-label">Incognito — withhold approved memory from context</span>
    {#if settings.incognito}<Badge variant="idle" label="on" />{:else}<Badge variant="active" label="off" />{/if}
  </label>
{/if}
{#if actionError}<p class="error" role="alert">{actionError}</p>{/if}

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if memories === null}
  <p class="loading">Loading…</p>
{:else if memories.length === 0}
  <div class="card">
    <EmptyState icon="activity" title="No approved memories yet" body="The agent stores durable lessons here as you work. Nothing is shared without your approval." />
  </div>
{:else}
  <ul class="memory-list">
    {#each ordered as m (m.memory_id)}
      <li class="card memory" class:pinned={m.pinned}>
        <div class="memory-head">
          <span class="memory-text">{m.text}</span>
          <div class="memory-actions">
            <button
              type="button"
              class="icon-btn"
              class:pinned={m.pinned}
              onclick={() => void togglePin(m)}
              aria-label={m.pinned ? "Unpin memory" : "Pin memory"}
              title={m.pinned ? "Unpin" : "Pin to top"}
            >★</button>
            <button
              type="button"
              class="icon-btn danger"
              onclick={() => void forget(m)}
              aria-label="Forget memory"
              title="Forget this memory permanently"
            >🗑</button>
          </div>
        </div>
        <div class="memory-meta">
          <span class="chip" title="Scope">{m.scope}</span>
          <span class="chip" title="Sensitivity">sensitivity: {m.sensitivity}</span>
          <span class="chip" title="Confidence">confidence: {m.confidence.toFixed(2)}</span>
          <span class="chip" title="Retention">{m.retention}</span>
          {#if m.tags.length > 0}<span class="chip" title="Tags">{m.tags.join(", ")}</span>{/if}
          <span class="sub" title={m.created_at}>created {relativeTime(m.created_at)}</span>
        </div>
        <p class="sub provenance">source: {m.source} · provenance: {Object.keys(m.provenance).length ? Object.entries(m.provenance).map(([k]) => k).join(", ") : "none"}</p>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .incognito-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: var(--space-3) 0;
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    cursor: pointer;
  }
  .incognito-label {
    font-weight: 600;
    font-size: 0.88rem;
  }
  .memory-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .memory {
    padding: 0.75rem 0.9rem;
  }
  .memory.pinned {
    border-color: var(--accent-border);
    box-shadow: 0 0 0 1px var(--accent-border), var(--shadow-1);
  }
  .memory-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
  }
  .memory-text {
    flex: 1;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
  }
  .memory-actions {
    display: flex;
    gap: 0.15rem;
    flex-shrink: 0;
  }
  .icon-btn {
    border: 1px solid transparent;
    background: none;
    color: var(--text-3);
    cursor: pointer;
    font-size: 0.95rem;
    line-height: 1;
    padding: 0.15rem 0.3rem;
    border-radius: var(--r-sm);
  }
  .icon-btn:hover:not(:disabled) {
    background: var(--neutral-soft);
    color: var(--text-1);
  }
  .icon-btn.pinned {
    color: var(--accent);
  }
  .icon-btn.danger:hover:not(:disabled) {
    color: var(--danger);
    background: var(--danger-soft);
  }
  .memory-meta {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
    align-items: center;
    margin-top: 0.5rem;
  }
  .chip {
    font-size: 0.72rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    background: var(--neutral-soft);
    color: var(--text-2);
    padding: 0.08rem 0.5rem;
  }
  .sub {
    color: var(--text-3);
    font-size: 0.76rem;
    margin: 0;
  }
  .provenance {
    margin-top: 0.35rem;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
