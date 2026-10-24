<script lang="ts">
  /**
   * QUI-F04 — one line in the top bar while something runs, from every page.
   *
   * One item is a link straight to it. Several are a button whose menu lists
   * each with its own step. Nothing running, nothing drawn: the line is not a
   * placeholder, it is a fact that is true only while the work is.
   */
  import { onMount } from "svelte";
  import { api } from "../api";
  import type { TaskView } from "../apiTypes";
  import { foregroundWork, liveWorkItems, liveWorkLine } from "../liveWork.svelte";
  import Icon from "./Icon.svelte";

  /** The cadence the stop switch and Chat's background toggle read at. */
  const POLL_MS = 15_000;

  let tasks = $state<TaskView[]>([]);
  let menuOpen = $state(false);
  let trigger = $state<HTMLButtonElement>();
  const items = $derived(liveWorkItems(tasks, foregroundWork));
  const line = $derived(liveWorkLine(items));
  const waiting = $derived(items.some((item) => item.waiting));

  async function read(): Promise<void> {
    try {
      tasks = await api.tasks();
    } catch {
      // The last known list stays. A failed read is not "nothing is running".
    }
  }

  onMount(() => {
    void read();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void read();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void read();
    };
    document.addEventListener("visibilitychange", onVisible);
    // A route change is the moment the owner may have started or finished
    // something from a page; read then rather than up to a poll later.
    const onRoute = () => {
      menuOpen = false;
      void read();
    };
    window.addEventListener("hashchange", onRoute);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("hashchange", onRoute);
    };
  });

  $effect(() => {
    if (items.length < 2) menuOpen = false;
  });

  $effect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        menuOpen = false;
        trigger?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
</script>

{#if items.length === 1}
  <a class="live-work" class:waiting href={items[0].href} title={line} data-testid="live-work-line">
    <span class="dot" aria-hidden="true"></span><span class="text">{line}</span>
  </a>
{:else if items.length > 1}
  <div class="live-wrap">
    <button
      type="button"
      class="live-work"
      class:waiting
      aria-expanded={menuOpen}
      aria-haspopup="true"
      title={line}
      data-testid="live-work-line"
      bind:this={trigger}
      onclick={() => (menuOpen = !menuOpen)}
    >
      <span class="dot" aria-hidden="true"></span><span class="text">{line}</span>
      <Icon name="chevron-down" size="sm" />
    </button>
    {#if menuOpen}
      <button type="button" class="backdrop" aria-label="Close running work" tabindex="-1" onclick={() => (menuOpen = false)}></button>
      <ul class="menu" aria-label="Running work">
        {#each items as item (item.id)}
          <li>
            <a href={item.href} class:waiting={item.waiting}>
              <strong>{item.label}</strong>
              <span>{item.step}</span>
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<style>
  /* Never wider than the room the top bar has left: a long task title is cut
     with an ellipsis rather than pushing the stop switch off screen (found
     live, RT-QUI-55). The full line is the tooltip. */
  .live-work{display:inline-flex;align-items:center;gap:.4rem;max-width:min(20rem,24vw);min-width:0;padding:.2rem .65rem;border:1px solid var(--border);border-radius:var(--r-pill);background:var(--sunken);color:var(--text-2);font:inherit;font-size:var(--text-xs);font-weight:600;text-decoration:none;cursor:pointer}
  .live-work:hover{color:var(--text-1);text-decoration:none}
  .live-work .text{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
  /* Status never relies on colour alone: the words say "waiting for you". */
  .dot{width:.45rem;height:.45rem;border-radius:50%;background:var(--accent);flex-shrink:0}
  .live-work.waiting .dot{background:var(--warn)}
  .live-wrap{position:relative}
  .backdrop{position:fixed;inset:0;z-index:var(--z-popover);border:0;background:transparent;cursor:default}
  .menu{position:absolute;right:0;top:calc(100% + 6px);z-index:var(--z-popover-panel);width:min(22rem,80vw);margin:0;padding:var(--space-2);list-style:none;border:1px solid var(--border);border-radius:var(--r-md);background:var(--raised);box-shadow:var(--shadow-2);display:grid;gap:2px}
  .menu a{display:grid;gap:.1rem;padding:.4rem .5rem;border-radius:var(--r-sm);color:var(--text-1);text-decoration:none;font-size:var(--text-sm)}
  .menu a:hover,.menu a:focus-visible{background:var(--sunken)}
  .menu a span{color:var(--text-3);font-size:var(--text-xs)}
  .menu a.waiting span{color:var(--warn-text)}
</style>
