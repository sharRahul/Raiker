<script lang="ts">
  /*
   * 03 Composer execution states — the follow-ups queued for a running turn,
   * each in the owner's own words with the state the runtime reported:
   * Queued, Read, or Not read when the turn ended before reaching them.
   */
  import Icon from "./Icon.svelte";
  import type { RunningTurn } from "../runningTurn.svelte";

  let { control, onuse }: { control: RunningTurn; onuse: (text: string) => void } = $props();

  const WORDS = { pending: "Sending…", queued: "Queued", read: "Read", unread: "Not read" } as const;
</script>

{#if control.followUps.length > 0}
  <ul class="follow-ups" aria-label="Follow-ups for the running turn">
    {#each control.followUps as item (item.id)}
      <li class="follow-up follow-up-{item.state}">
        <Icon name={item.state === "read" ? "check" : item.state === "queued" ? "clock" : "info"} size="sm" />
        <span class="follow-up-text" title={item.text}>{item.text}</span>
        <span class="follow-up-state">{WORDS[item.state]}</span>
        {#if item.state === "unread"}
          <button
            type="button"
            class="btn btn-ghost btn-sm"
            onclick={() => {
              control.dismiss(item.id);
              onuse(item.text);
            }}>Use as next message</button
          >
          <button
            type="button"
            class="pill-dismiss"
            aria-label={`Dismiss "${item.text.slice(0, 40)}"`}
            onclick={() => control.dismiss(item.id)}
          ><Icon name="x" size="sm" /></button>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .follow-ups {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  .follow-up {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    max-width: 100%;
    min-height: 1.75rem;
    padding: 0 var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    font-size: var(--text-xs);
    color: var(--text-2);
  }
  .follow-up-text {
    min-width: 0;
    max-width: 24rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-1);
  }
  .follow-up-state { color: var(--text-3); }
  .follow-up-unread { border-color: var(--warn-border); }
  .follow-up-unread .follow-up-state { color: var(--warn-text); }
  .pill-dismiss {
    display: inline-grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    padding: 0;
    border: 0;
    border-radius: var(--r-pill);
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
  }
  .pill-dismiss:hover { background: var(--sunken); }
  .pill-dismiss:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
</style>
