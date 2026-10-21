<script lang="ts">
  /**
   * QUI-C07 — what this conversation is working with, beside the transcript.
   *
   * Closed by default and opened from Chat's Context toggle. A tab is drawn
   * only when it has content (`contextTabs`). QUI-C12 — Chat decides where it
   * sits: over the transcript below 1,920 px, beside it from 1,920 px up.
   */
  import Icon from "./Icon.svelte";
  import type { AgentPlan, TurnSourceView } from "../apiTypes";
  import type { ToolCallRow } from "../chatPresentation";
  import type { ComposerAttachment } from "../composerAttachments.svelte";
  import { CONTEXT_TAB_LABELS, contextTabs, type ContextTab } from "../contextPanel";

  let {
    files,
    plan,
    sources,
    activity,
    onclose,
    onopensource,
  }: {
    files: ComposerAttachment[];
    plan: AgentPlan | null;
    sources: TurnSourceView[];
    activity: ToolCallRow[];
    onclose: () => void;
    onopensource?: (source: TurnSourceView) => void;
  } = $props();

  const tabs = $derived(contextTabs({ files, plan, sources, activity }));
  let chosen = $state<ContextTab | null>(null);
  const current = $derived(chosen !== null && tabs.includes(chosen) ? chosen : (tabs[0] ?? null));

  const STEP_WORDS: Record<string, string> = {
    completed: "Done",
    in_progress: "Now",
    pending: "Next",
    blocked: "Blocked",
  };
  const STATE_WORDS: Record<string, string> = {
    running: "Running",
    waiting: "Waiting for you",
    success: "Done",
    failed: "Failed",
    denied: "Declined",
    refused: "Not allowed",
  };

  function onTabKeydown(event: KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    chosen = next;
    document.getElementById(`context-tab-${next}`)?.focus();
  }
</script>

<aside class="context-panel" aria-label="Conversation context">
  <div class="context-head">
    <h3>Context</h3>
    <button type="button" class="btn btn-ghost btn-sm" aria-label="Close context" title="Close context" onclick={onclose}>
      <Icon name="x" size="sm" />
    </button>
  </div>
  {#if current === null}
    <p class="empty">Nothing in use yet. Files, a plan, sources and steps appear here as the conversation uses them.</p>
  {:else}
    {#if tabs.length > 1}
      <div class="tabs" role="tablist" aria-label="Context">
        {#each tabs as tab, index (tab)}
          <button
            type="button"
            role="tab"
            id={`context-tab-${tab}`}
            aria-selected={current === tab}
            aria-controls="context-tabpanel"
            tabindex={current === tab ? 0 : -1}
            onclick={() => (chosen = tab)}
            onkeydown={(event) => onTabKeydown(event, index)}
          >{CONTEXT_TAB_LABELS[tab]}</button>
        {/each}
      </div>
    {:else}
      <p class="single-tab">{CONTEXT_TAB_LABELS[current]}</p>
    {/if}
    <div id="context-tabpanel" role={tabs.length > 1 ? "tabpanel" : undefined} aria-labelledby={tabs.length > 1 ? `context-tab-${current}` : undefined}>
      {#if current === "context"}
        <ul class="items">
          {#each files as file (file.attachmentId ?? file.path ?? file.label)}
            <li><strong>{file.label}</strong><span>{file.detail}</span></li>
          {/each}
        </ul>
      {:else if current === "plan" && plan !== null}
        <ol class="items">
          {#each plan.steps as step, index (index)}
            <li class:now={step.status === "in_progress"}>
              <strong>{step.title}</strong><span>{STEP_WORDS[step.status] ?? step.status}</span>
            </li>
          {/each}
        </ol>
      {:else if current === "sources"}
        <ul class="items">
          {#each sources as source (source.source_id)}
            <li>
              {#if source.openable && onopensource}
                <button type="button" class="link-btn" onclick={() => onopensource?.(source)}>{source.title || source.locator}</button>
              {:else}
                <strong>{source.title || source.locator}</strong>
              {/if}
              {#if source.title && source.locator}<span>{source.locator}</span>{/if}
            </li>
          {/each}
        </ul>
      {:else if current === "activity"}
        <ul class="items">
          {#each activity as row (row.actionId)}
            <li><strong>{row.label}</strong><span>{row.action ? `${row.action} · ` : ""}{STATE_WORDS[row.state] ?? row.state}</span></li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</aside>

<style>
  .context-panel {
    display: grid;
    align-content: start;
    gap: var(--space-3);
    width: 20rem;
    max-width: 100%;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    overflow-y: auto;
  }
  .context-head { display: flex; align-items: center; justify-content: space-between; }
  .context-head h3 { margin: 0; font-size: var(--text-md); }
  .tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--border); }
  .tabs button {
    padding: var(--space-1) var(--space-2); border: 0; border-bottom: 2px solid transparent;
    background: none; color: var(--text-2); font: inherit; font-size: var(--text-sm); cursor: pointer;
  }
  .tabs button[aria-selected="true"] { color: var(--text-1); border-bottom-color: var(--accent); font-weight: 600; }
  .single-tab { margin: 0; font-size: var(--text-sm); font-weight: 600; color: var(--text-2); }
  .items { list-style: none; margin: 0; padding: 0; display: grid; }
  .items li { display: grid; gap: 0.1rem; padding: var(--space-2) 0; border-top: 1px solid var(--border); min-width: 0; }
  .items li:first-child { border-top: 0; }
  .items strong, .link-btn { font-size: var(--text-sm); overflow-wrap: anywhere; }
  .items span { font-size: var(--text-xs); color: var(--text-3); overflow-wrap: anywhere; }
  .items li.now strong { color: var(--accent); }
  .link-btn { padding: 0; border: 0; background: none; color: var(--accent); font: inherit; text-align: left; cursor: pointer; }
  .link-btn:hover { text-decoration: underline; }
  .empty { margin: 0; font-size: var(--text-sm); color: var(--text-2); }
</style>
