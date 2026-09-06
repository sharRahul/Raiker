<script lang="ts">
  /**
   * MODEL-15 / VIS2-18 — the second half of "one primary action per row".
   *
   * A rule that says "at most one visible action" is only half a design; the
   * other half is where the rest go. Without a shared answer each surface
   * invents one, and the page ends up with three different overflow idioms —
   * which is how the provider cards came to carry Test, Details, Select models…
   * and Select side by side in the first place. Four controls repeated down a
   * list of providers is not four controls, it is four times however many
   * providers, and the owner reads all of them to find the one they want.
   *
   * Deliberately small: a trigger, a menu, dismissal, and nothing else. It does
   * not own the actions, their labels or their order — the row does, because
   * only the row knows which of them is the primary one that should *not* be in
   * here.
   */
  import Icon from "./Icon.svelte";

  export interface OverflowItem {
    label: string;
    run: () => void;
    disabled?: boolean;
  }

  let {
    items,
    /** Names the row in the trigger's accessible name. */
    label,
  }: {
    items: OverflowItem[];
    label: string;
  } = $props();

  let open = $state(false);
  let root = $state<HTMLDivElement>();
  let trigger = $state<HTMLButtonElement>();
  let menu = $state<HTMLDivElement>();

  /**
   * Which edge the menu hangs from.
   *
   * `end` — the menu's right edge on the trigger's — is right for a row whose
   * actions sit at the far right, which is most of them. It is wrong for a
   * trigger near the left of the page: the menu then reaches leftwards past the
   * content column, and the shell's content area is a scroller, so the part
   * that spills is *clipped* rather than merely overlapping. Found on the
   * Models provider cards, where the first card's overflow opened with its left
   * third cut off and the visible remainder was not where a pointer expected it.
   *
   * Measured rather than declared by the call site: whether a menu fits is a
   * fact about this viewport at this scroll position, and a prop would be the
   * author guessing about both.
   */
  let align = $state<"start" | "end">("end");

  function choose(item: OverflowItem) {
    if (item.disabled) return;
    open = false;
    item.run();
  }

  $effect(() => {
    if (!open || menu === undefined) return;
    // Re-measure on every open: the row may have scrolled since the last one.
    const box = menu.getBoundingClientRect();
    const limit = root?.closest<HTMLElement>(".content")?.getBoundingClientRect().left ?? 0;
    if (box.left < limit + 8) align = "start";
  });

  $effect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (root !== undefined && !root.contains(event.target as Node)) open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      open = false;
      trigger?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  });
</script>

{#if items.length > 0}
  <div class="overflow" bind:this={root}>
    <button
      type="button"
      class="btn btn-ghost btn-sm overflow-trigger"
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label={`More actions for ${label}`}
      bind:this={trigger}
      onclick={() => (open = !open)}
    ><Icon name="more" size="sm" /></button>

    {#if open}
      <div
        class="overflow-menu menu-surface"
        data-align={align}
        role="menu"
        aria-label={`${label} actions`}
        bind:this={menu}
      >
        {#each items as item (item.label)}
          <button
            type="button"
            role="menuitem"
            class="menu-item"
            disabled={item.disabled}
            onclick={() => choose(item)}
          >{item.label}</button>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .overflow {
    position: relative;
    display: inline-flex;
  }
  .overflow-trigger {
    padding: 0.25rem 0.4rem;
  }
  .overflow-menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 45;
    width: max-content;
    min-width: 12rem;
    display: grid;
    gap: 1px;
    padding: 0.25rem;
    text-align: left;
  }
  .overflow-menu[data-align="start"] {
    right: auto;
    left: 0;
  }
</style>
