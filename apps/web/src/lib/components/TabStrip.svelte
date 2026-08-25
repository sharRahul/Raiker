<script lang="ts">
  /**
   * Tab strip for the consolidated hubs. Implements the ARIA tabs pattern:
   * arrow keys move between tabs, Home/End jump to the ends, and only the
   * selected tab is in the tab order.
   *
   * Selecting a tab writes it into the hash so the panel is a shareable
   * location, not hidden client state.
   */
  export interface Tab { id: string; label: string; badge?: number | null }

  let {
    tabs,
    selected,
    onselect,
    label,
  }: {
    tabs: Tab[];
    selected: string;
    onselect: (id: string) => void;
    label: string;
  } = $props();

  let strip = $state<HTMLDivElement>();

  /**
   * Keep the selected tab visible when the strip is scrollable.
   *
   * The strip is `overflow-x: auto`, and on a phone six tabs are wider than the
   * screen. Landing on `#/extensions?tab=plugins` at 390px rendered the strip at
   * `scrollLeft: 0` with the selected tab at 365px in a 364px viewport — so the
   * page showed the Plugins panel under a strip that appeared to have Hooks
   * selected, and there was nothing on screen saying otherwise.
   *
   * `nearest` rather than `center`: when the tab is already visible this does
   * nothing, so arrow-key navigation is not fighting a scroll animation, and the
   * first and last tabs keep their strip edge rather than being pulled inward.
   * `block: "nearest"` because a horizontal strip must never scroll the page.
   */
  $effect(() => {
    const active = strip?.querySelector<HTMLButtonElement>(`[data-tab="${selected}"]`);
    if (!active || !strip || strip.scrollWidth <= strip.clientWidth) return;
    active.scrollIntoView({ inline: "nearest", block: "nearest" });
  });

  function onKeydown(event: KeyboardEvent) {
    const index = tabs.findIndex((tab) => tab.id === selected);
    if (index < 0) return;
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    onselect(tabs[next].id);
    queueMicrotask(() => {
      strip?.querySelector<HTMLButtonElement>(`[data-tab="${tabs[next].id}"]`)?.focus();
    });
  }
</script>

<div class="tab-strip" role="tablist" aria-label={label} bind:this={strip}>
  {#each tabs as tab (tab.id)}
    <button
      type="button"
      class="tab-control"
      role="tab"
      data-tab={tab.id}
      id={`tab-${tab.id}`}
      aria-selected={selected === tab.id}
      aria-controls={`panel-${tab.id}`}
      tabindex={selected === tab.id ? 0 : -1}
      class:active={selected === tab.id}
      onclick={() => onselect(tab.id)}
      onkeydown={onKeydown}
    >
      {tab.label}
      {#if tab.badge !== undefined && tab.badge !== null && tab.badge > 0}
        <span class="badge">{tab.badge}</span>
      {/if}
    </button>
  {/each}
</div>

<style>
  .tab-strip {
    display: flex;
    gap: 0.25rem;
    padding: 0.22rem;
    margin-bottom: var(--space-4);
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .tab-strip::-webkit-scrollbar { display: none; }
  button {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    white-space: nowrap;
    border: 0;
    border-radius: var(--r-pill);
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.38rem 0.85rem;
    cursor: pointer;
    transition: background 120ms var(--ease), color 120ms var(--ease);
  }
  button:hover { color: var(--text-1); }
  button.active {
    background: var(--surface);
    color: var(--text-1);
    box-shadow: var(--shadow-1);
  }
  .badge {
    display: inline-grid;
    place-items: center;
    min-width: 1.1rem;
    height: 1.1rem;
    padding: 0 0.25rem;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 0.66rem;
    font-weight: 700;
  }
  @media (max-width: 1023px) {
    button { min-height: 44px; }
  }
</style>
