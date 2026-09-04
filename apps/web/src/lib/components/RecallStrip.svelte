<script lang="ts">
  /**
   * C17 — what Raiker remembered, at the moment it used it.
   *
   * Ambient recall reaches a turn through the context bundle rather than
   * through a tool the transcript can cite, so until now the only place an
   * owner could see what Raiker remembers about them was the Memory route —
   * never the answer the memory shaped. A remembered sentence that is wrong is
   * most obviously wrong in the answer it produced, and that is where
   * correcting it belongs.
   *
   * The actions are the governed ones the Memory page already uses; nothing
   * here is a second path to the memory store. Collapsed by default: recall is
   * background, and a strip that shouts would make every turn about memory.
   */
  import Icon from "./Icon.svelte";
  import type { RecalledMemory } from "../apiTypes";

  let {
    memories,
    onforget,
    oncorrect,
  }: {
    memories: RecalledMemory[];
    onforget: (memory: RecalledMemory) => void | Promise<void>;
    oncorrect: (memory: RecalledMemory, text: string) => void | Promise<void>;
  } = $props();

  let open = $state(false);
  let editingId = $state<string | null>(null);
  let draft = $state("");

  function startEdit(memory: RecalledMemory) {
    editingId = memory.memory_id;
    draft = memory.text;
  }
</script>

{#if memories.length > 0}
  <section class="recall" aria-label="Memories used in this answer">
    <button type="button" class="recall-toggle" aria-expanded={open} onclick={() => (open = !open)}>
      <Icon name={open ? "chevron-down" : "chevron-right"} size="sm" />
      <Icon name="spark" size="sm" />
      <span>Remembered {memories.length}</span>
    </button>
    {#if open}
      <ul class="recall-list">
        {#each memories as memory (memory.memory_id)}
          <li>
            {#if editingId === memory.memory_id}
              <label class="sr-only" for={`recall-edit-${memory.memory_id}`}>Correct this memory</label>
              <textarea id={`recall-edit-${memory.memory_id}`} bind:value={draft} rows="2"></textarea>
              <div class="recall-actions">
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  onclick={async () => {
                    await oncorrect(memory, draft.trim());
                    editingId = null;
                  }}
                >Save</button>
                <button type="button" class="btn btn-ghost btn-sm" onclick={() => (editingId = null)}>
                  Cancel
                </button>
              </div>
            {:else}
              <p class="recall-text">{memory.text}</p>
              <div class="recall-actions">
                <span class="recall-scope mono">{memory.scope}</span>
                <button type="button" class="link-button" onclick={() => startEdit(memory)}>
                  Correct
                </button>
                <button type="button" class="link-button danger" onclick={() => void onforget(memory)}>
                  Forget
                </button>
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{/if}

<style>
  .recall {
    margin: 0.35rem 0 0;
    display: grid;
    gap: 0.35rem;
    justify-items: start;
  }
  .recall-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    border: 0;
    background: transparent;
    color: var(--text-3);
    font: inherit;
    font-size: var(--text-2xs);
    font-weight: 650;
    letter-spacing: 0.02em;
    cursor: pointer;
    padding: 0;
  }
  .recall-toggle:hover { color: var(--text-2); }
  .recall-toggle:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
  .recall-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
    width: 100%;
  }
  .recall-list li {
    padding: 0.4rem 0.55rem;
    border-left: 2px solid var(--border);
    background: var(--sunken);
    border-radius: var(--r-sm);
  }
  .recall-text {
    margin: 0 0 0.25rem;
    font-size: var(--text-xs);
    color: var(--text-2);
    line-height: 1.5;
  }
  .recall-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .recall-scope {
    font-size: var(--text-2xs);
    color: var(--text-3);
    margin-right: auto;
  }
  .link-button {
    border: 0;
    background: transparent;
    padding: 0;
    font: inherit;
    font-size: var(--text-2xs);
    color: var(--accent);
    cursor: pointer;
  }
  .link-button.danger { color: var(--danger); }
  .link-button:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
  textarea {
    width: 100%;
    font: inherit;
    font-size: var(--text-xs);
    padding: 0.35rem 0.45rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-1);
    resize: vertical;
  }
</style>
