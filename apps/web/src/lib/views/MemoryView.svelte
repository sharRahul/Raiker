<script lang="ts">
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { MemoryControlView, MemorySettingsView } from "../apiTypes";
  import { relativeTime } from "../format";

  type MemoryImport = Array<Partial<MemoryControlView> & { text: string }>;

  let memories = $state<MemoryControlView[] | null>(null);
  let loadError = $state<string | null>(null);
  let settings = $state<MemorySettingsView | null>(null);
  let actionError = $state<string | null>(null);
  let togglingIncognito = $state(false);
  let editingId = $state<string | null>(null);
  let editDraft = $state("");
  let expiryDrafts = $state<Record<string, string>>({});
  let exportText = $state("");
  let importText = $state("");

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

  function inputValue(event: Event): string {
    return (event.currentTarget as HTMLInputElement | HTMLTextAreaElement).value;
  }

  function expiryInputValue(expiresAt: string | null): string {
    return expiresAt === null ? "" : expiresAt.slice(0, 16);
  }

  function normalizeExpiry(value: string): string | null {
    const trimmed = value.trim();
    if (trimmed === "") return null;
    const date = new Date(trimmed);
    return Number.isNaN(date.getTime()) ? trimmed : date.toISOString().replace(".000Z", "Z");
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

  function startEdit(m: MemoryControlView) {
    editingId = m.memory_id;
    editDraft = m.text;
  }

  async function saveEdit(m: MemoryControlView) {
    actionError = null;
    try {
      await api.editMemory(m.memory_id, editDraft);
      editingId = null;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? `Could not edit memory (${e.status}).` : "Could not edit memory.";
    }
  }

  async function toggleSearch(m: MemoryControlView) {
    actionError = null;
    try {
      await api.setMemorySearchEnabled(m.memory_id, !m.search_enabled);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not update search (${e.status}).` : "Could not update search.";
    }
  }

  async function saveExpiry(m: MemoryControlView) {
    actionError = null;
    try {
      await api.setMemoryExpiry(m.memory_id, normalizeExpiry(expiryDrafts[m.memory_id] ?? expiryInputValue(m.expires_at)));
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not update expiry (${e.status}).` : "Could not update expiry.";
    }
  }

  async function clearExpiry(m: MemoryControlView) {
    expiryDrafts[m.memory_id] = "";
    actionError = null;
    try {
      await api.setMemoryExpiry(m.memory_id, null);
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not clear expiry (${e.status}).` : "Could not clear expiry.";
    }
  }

  async function exportMemories() {
    actionError = null;
    try {
      const exported = await api.exportMemories();
      exportText = JSON.stringify(exported.memories, null, 2);
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not export memories (${e.status}).` : "Could not export memories.";
    }
  }

  async function importMemories() {
    actionError = null;
    try {
      const parsed = JSON.parse(importText) as unknown;
      const memoriesToImport = Array.isArray(parsed)
        ? parsed
        : typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { memories?: unknown }).memories)
          ? (parsed as { memories: unknown[] }).memories
          : [];
      await api.importMemories(memoriesToImport as MemoryImport);
      importText = "";
      await load();
    } catch (e) {
      actionError =
        e instanceof ApiError ? `Could not import memories (${e.status}).` : "Could not import memories.";
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
    <span class="incognito-label">Incognito - withhold approved memory from context</span>
    {#if settings.incognito}<Badge variant="idle" label="on" />{:else}<Badge variant="active" label="off" />{/if}
  </label>
{/if}

<div class="memory-tools">
  <div class="tool-panel">
    <button type="button" class="btn btn-ghost btn-sm" onclick={() => void exportMemories()} aria-label="Export memories">
      Export
    </button>
    <label class="field">
      <span>Memory export JSON</span>
      <textarea readonly rows="3" aria-label="Memory export JSON" bind:value={exportText}></textarea>
    </label>
  </div>
  <div class="tool-panel">
    <label class="field">
      <span>Memory import JSON</span>
      <textarea rows="3" aria-label="Memory import JSON" bind:value={importText}></textarea>
    </label>
    <button type="button" class="btn btn-primary btn-sm" onclick={() => void importMemories()} aria-label="Import memories">
      Import
    </button>
  </div>
</div>

{#if actionError}<p class="error" role="alert">{actionError}</p>{/if}

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if memories === null}
  <p class="loading">Loading...</p>
{:else if memories.length === 0}
  <div class="card">
    <EmptyState icon="activity" title="No approved memories yet" body="The agent stores durable lessons here as you work. Nothing is shared without your approval." />
  </div>
{:else}
  <ul class="memory-list">
    {#each ordered as m (m.memory_id)}
      <li class="card memory" class:pinned={m.pinned}>
        <div class="memory-head">
          {#if editingId === m.memory_id}
            <label class="field edit-field">
              <span>Memory text</span>
              <textarea rows="3" aria-label="Memory text" bind:value={editDraft}></textarea>
            </label>
          {:else}
            <span class="memory-text">{m.text}</span>
          {/if}
          <div class="memory-actions">
            {#if editingId === m.memory_id}
              <button type="button" class="icon-btn" onclick={() => void saveEdit(m)} aria-label="Save memory" title="Save memory">
                Save
              </button>
              <button type="button" class="icon-btn" onclick={() => (editingId = null)} aria-label="Cancel edit" title="Cancel edit">
                Cancel
              </button>
            {:else}
              <button type="button" class="icon-btn" onclick={() => startEdit(m)} aria-label="Edit memory" title="Edit memory">
                Edit
              </button>
              <button
                type="button"
                class="icon-btn"
                class:pinned={m.pinned}
                onclick={() => void togglePin(m)}
                aria-label={m.pinned ? "Unpin memory" : "Pin memory"}
                title={m.pinned ? "Unpin" : "Pin to top"}
              >Pin</button>
              <button
                type="button"
                class="icon-btn danger"
                onclick={() => void forget(m)}
                aria-label="Forget memory"
                title="Forget this memory permanently"
              >Forget</button>
            {/if}
          </div>
        </div>

        <div class="memory-controls">
          <label class="check-row">
            <input type="checkbox" checked={m.search_enabled} onchange={() => void toggleSearch(m)} />
            Include memory in search
          </label>
          <label class="expiry-field">
            <span>Expires</span>
            <input
              type="datetime-local"
              aria-label="Memory expiry"
              value={expiryDrafts[m.memory_id] ?? expiryInputValue(m.expires_at)}
              oninput={(event) => (expiryDrafts[m.memory_id] = inputValue(event))}
            />
          </label>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void saveExpiry(m)} aria-label="Save memory expiry">
            Save expiry
          </button>
          <button type="button" class="btn btn-ghost btn-sm" onclick={() => void clearExpiry(m)} aria-label="Clear memory expiry">
            Clear
          </button>
        </div>

        <div class="memory-meta">
          <span class="chip" title="Scope">{m.scope}</span>
          <span class="chip" title="Sensitivity">sensitivity: {m.sensitivity}</span>
          <span class="chip" title="Confidence">confidence: {m.confidence.toFixed(2)}</span>
          <span class="chip" title="Retention">{m.retention}</span>
          {#if m.expires_at !== null}<span class="chip" title="Expiry">expires: {m.expires_at}</span>{/if}
          {#if m.tags.length > 0}<span class="chip" title="Tags">{m.tags.join(", ")}</span>{/if}
          <span class="sub" title={m.created_at}>created {relativeTime(m.created_at)}</span>
        </div>
        <p class="sub provenance">source: {m.source} - provenance: {Object.keys(m.provenance).length ? Object.entries(m.provenance).map(([k]) => k).join(", ") : "none"}</p>
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
  .memory-tools {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0;
  }
  .tool-panel {
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    padding: 0.65rem;
    display: grid;
    gap: 0.5rem;
  }
  .field {
    display: grid;
    gap: 0.25rem;
    color: var(--text-2);
    font-size: 0.76rem;
    font-weight: 600;
  }
  textarea,
  input[type="datetime-local"] {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface-2);
    color: var(--text-1);
    font: inherit;
    padding: 0.45rem 0.55rem;
  }
  textarea {
    resize: vertical;
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
  .memory-text,
  .edit-field {
    flex: 1;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
  }
  .memory-actions,
  .memory-controls {
    display: flex;
    gap: 0.35rem;
    flex-wrap: wrap;
    align-items: center;
  }
  .memory-actions {
    flex-shrink: 0;
  }
  .memory-controls {
    margin-top: 0.6rem;
  }
  .check-row,
  .expiry-field {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--text-2);
    font-size: 0.78rem;
    font-weight: 600;
  }
  .expiry-field input {
    min-width: 12rem;
  }
  .icon-btn {
    border: 1px solid transparent;
    background: none;
    color: var(--text-3);
    cursor: pointer;
    font-size: 0.8rem;
    line-height: 1;
    padding: 0.25rem 0.4rem;
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
