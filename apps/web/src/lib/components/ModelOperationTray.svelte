<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { ModelOperation } from "../apiTypes";
  let open = $state(false);
  let items = $state<ModelOperation[]>([]);
  let timer: ReturnType<typeof setInterval> | undefined;
  const active = $derived(
    items.filter(
      (item) => !["complete", "failed", "cancelled"].includes(item.state),
    ),
  );
  async function load() {
    try {
      items = (await api.modelOperations()).items;
    } catch {
      /* The tray is optional chrome; the Activity page carries errors. */
    }
  }
  onMount(() => {
    void load();
    timer = setInterval(() => void load(), 5000);
    return () => {
      if (timer) clearInterval(timer);
    };
  });
</script>

{#if active.length > 0}
  <aside class="operation-tray" class:open aria-label="Active model operations">
    <button
      class="tray-toggle"
      type="button"
      onclick={() => (open = !open)}
      aria-expanded={open}
    >
      <span class="pulse" aria-hidden="true"></span><strong
        >{active.length} model job{active.length === 1 ? "" : "s"}</strong
      ><span>{open ? "Hide" : "Show"}</span>
    </button>
    {#if open}<div class="tray-body">
        {#each active as item (item.operation_id)}<a
            href="#/models?tab=activity"
            ><span><strong>{item.kind}</strong> {item.target}</span><small
              >{item.phase.replaceAll(
                "_",
                " ",
              )}{#if item.progress_percent !== null}
                · {item.progress_percent}%{/if}</small
            ></a
          >{/each}
      </div>{/if}
  </aside>
{/if}

<style>
  .operation-tray {
    --text-muted: var(--text-2);
    position: fixed;
    right: 20px;
    bottom: 18px;
    z-index: 45;
    width: min(390px, calc(100vw - 32px));
    border: 1px solid var(--accent-border);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: var(--shadow-2);
    overflow: hidden;
  }
  .tray-toggle {
    width: 100%;
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 9px;
    padding: 11px 13px;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
  }
  .tray-toggle > span:last-child {
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
  .pulse {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 5px var(--accent-soft);
  }
  .tray-body {
    border-top: 1px solid var(--border);
    max-height: 240px;
    overflow: auto;
  }
  .tray-body a {
    display: grid;
    gap: 3px;
    padding: 10px 13px;
    border-bottom: 1px solid var(--border);
    color: inherit;
    text-decoration: none;
  }
  .tray-body a:hover {
    background: var(--surface-raised);
  }
  .tray-body strong {
    text-transform: uppercase;
    font-size: var(--text-2xs);
    letter-spacing: 0.08em;
  }
  .tray-body small {
    color: var(--text-muted);
  }
</style>
