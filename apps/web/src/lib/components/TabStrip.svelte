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
   * Whether the strip is scrolled away from each end, so the edges can say so.
   *
   * A strip that scrolls with `scrollbar-width: none` and no fade looks like a
   * strip with four tabs in it. At 390px the Observability hub shows Overview,
   * Sessions, Audit log and a clipped Checkpoints, and Diagnostics, Work in
   * action and Notifications are not merely off-screen — nothing on the page
   * says they exist. The fade is the whole affordance: no extra control, no
   * extra words, and it is absent entirely when everything fits.
   */
  let overflowStart = $state(false);
  let overflowEnd = $state(false);

  function measure() {
    if (!strip) return;
    const slack = strip.scrollWidth - strip.clientWidth;
    // A sub-pixel remainder is not an overflow; two pixels of tolerance keeps a
    // strip that exactly fits from painting a fade over its last tab.
    overflowStart = slack > 2 && strip.scrollLeft > 2;
    overflowEnd = slack > 2 && strip.scrollLeft < slack - 2;
  }

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
    if (!active || !strip) return;
    if (strip.scrollWidth > strip.clientWidth) {
      active.scrollIntoView({ inline: "nearest", block: "nearest" });
    }
    measure();
  });

  // Re-measured on resize as well as on scroll: rotating a phone or dragging a
  // desktop window across the breakpoint changes whether the strip overflows
  // without anyone scrolling it.
  $effect(() => {
    // Guarded because the component test environment has no ResizeObserver,
    // and an affordance is not worth taking the strip down over.
    if (!strip || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(strip);
    return () => observer.disconnect();
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

<div
  class="tab-strip"
  class:fade-start={overflowStart}
  class:fade-end={overflowEnd}
  role="tablist"
  aria-label={label}
  bind:this={strip}
  onscroll={measure}
>
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
  /* The fade is a mask rather than a gradient overlay so it works on the strip's
     own sunken background in either theme, and so it cannot sit above a tab and
     swallow its click. */
  .tab-strip.fade-end {
    mask-image: linear-gradient(to right, #000 calc(100% - 2rem), transparent 100%);
  }
  .tab-strip.fade-start {
    mask-image: linear-gradient(to right, transparent 0, #000 2rem);
  }
  .tab-strip.fade-start.fade-end {
    mask-image: linear-gradient(
      to right,
      transparent 0,
      #000 2rem,
      #000 calc(100% - 2rem),
      transparent 100%
    );
  }
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
