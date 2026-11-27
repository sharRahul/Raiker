<script lang="ts">
  import type { MemoryControlView } from "../apiTypes";
  import { isRecallable } from "../memoryLifecycle";

  let { memories, onSave, onForget }: {
    memories: MemoryControlView[];
    onSave: (memory: MemoryControlView, text: string) => Promise<void>;
    onForget: (memory: MemoryControlView) => unknown;
  } = $props();
  const topics: Record<string, string> = {
    preference: "Preferences", personal: "About you", fact: "Facts",
    project: "Projects", procedure: "Ways of working", lesson: "Lessons",
    relationship: "People and relationships", summary: "Summaries",
  };
  const groups = $derived.by(() => {
    const grouped = new Map<string, MemoryControlView[]>();
    for (const memory of memories) {
      if (!["approved", "policy_allowed"].includes(memory.approval_state) || !isRecallable(memory)) continue;
      const topic = topics[memory.memory_type] ?? "Other memories";
      grouped.set(topic, [...(grouped.get(topic) ?? []), memory]);
    }
    return [...grouped].sort(([a], [b]) => a.localeCompare(b));
  });
  // An internal id is not a label: `project:proj_3f…` reads as one project.
  function scopeLabel(scope: string): string {
    if (scope === "account" || scope === "global" || scope === "user") return "Across your conversations";
    if (scope.startsWith("project:")) return "In one project only";
    if (scope === "project") return "In your projects";
    return scope;
  }
  let editing = $state<string | null>(null);
  let draft = $state("");
  let saving = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);

  async function save(memory: MemoryControlView) {
    if (saving || !draft.trim()) return;
    saving = true; error = null; notice = null;
    try {
      await onSave(memory, draft.trim());
      editing = null;
      notice = "Memory updated.";
    } catch {
      error = "Could not save your memory edit. Your draft is kept here; try Save changes again.";
    } finally { saving = false; }
  }
</script>

<section class="memory-summary" aria-label="What Raiker knows about you">
  {#if error}<p class="notice notice-danger" role="alert">{error}</p>{/if}
  {#if notice}<p class="saved" role="status">{notice}</p>{/if}
  {#each groups as [topic, records] (topic)}
    <section class="topic" aria-label={topic}>
      <h3>{topic}</h3>
      <ul>
        {#each records as memory (memory.memory_id)}
          <li>
            <div class="fact">
              {#if editing === memory.memory_id}
                <textarea rows="3" aria-label="Memory text" bind:value={draft} disabled={saving}></textarea>
              {:else}<p>{memory.text}</p>{/if}
              <small>{scopeLabel(memory.scope)}</small>
            </div>
            <div class="actions">
              {#if editing === memory.memory_id}
                <button type="button" class="btn btn-primary btn-sm" disabled={saving || !draft.trim()} onclick={() => void save(memory)}>{saving ? "Saving…" : "Save changes"}</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={saving} onclick={() => { editing = null; error = null; }}>Cancel</button>
              {:else}
                <button type="button" class="btn btn-ghost btn-sm" disabled={saving} aria-label={`Edit ${memory.text}`} onclick={() => { editing = memory.memory_id; draft = memory.text; error = null; notice = null; }}>Edit</button>
                <button type="button" class="btn btn-ghost btn-sm" disabled={saving} aria-label={`Forget ${memory.text}`} onclick={() => onForget(memory)}>Forget</button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    </section>
  {/each}
</section>

<style>
  .memory-summary { margin-block: var(--space-5); }
  .topic + .topic { margin-top: var(--space-6); }
  h3 { margin: 0 0 var(--space-2); font-size: var(--text-lg); }
  ul { list-style: none; margin: 0; padding: 0; }
  li { display: flex; align-items: start; gap: var(--space-4); padding-block: var(--space-4); border-bottom: 1px solid var(--border); }
  .fact { flex: 1; min-width: 0; }
  p { margin: 0; overflow-wrap: anywhere; line-height: 1.6; }
  small { display: block; margin-top: var(--space-1); color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  textarea { width: 100%; box-sizing: border-box; }
  .actions { display: flex; flex: none; gap: var(--space-1); flex-wrap: wrap; }
  .saved { color: var(--text-2); font-size: var(--text-sm); }
  @media (max-width: 45rem) {
    li { flex-direction: column; gap: var(--space-2); }
    .fact { width: 100%; }
  }
</style>
