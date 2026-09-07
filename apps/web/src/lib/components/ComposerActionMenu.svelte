<script lang="ts">
  /**
   * COMPOSER-03 / COMPOSER-04 — the `+` and the Tools control, once.
   *
   * Two menus with one implementation, because they differ only in what they
   * list: `+` brings something *into* this turn, Tools asks Raiker to *do* a
   * kind of thing. Everything else about them — the trigger, the popover, how
   * a governed-off entry reads, dismissal, the keyboard — is the same, and two
   * copies of it would drift the way the two composers drifted before
   * `Composer.svelte` existed.
   *
   * The list is derived from the typed registry (COMPOSER-19) rather than
   * written here, so adding a capability does not mean editing a menu, and the
   * rule that visibility never grants authority holds in one place: an entry
   * whose gate is off is drawn with its reason and the route that changes it,
   * and pressing it goes there instead of pretending to run.
   *
   * COMPOSER-16 — below the split this is a bottom sheet rather than a popover.
   * A dropdown anchored to a 44px control at the bottom of a phone opens
   * upwards into the transcript and is thumb-hostile; the same items in a sheet
   * are one reach away.
   */
  import Icon from "./Icon.svelte";
  import type { ComposerMenuItem } from "../composerCapabilities";

  let {
    kind,
    items,
    disabled = false,
    onchoose,
  }: {
    /** Which control this is. Decides the glyph, the label and the heading. */
    kind: "add" | "tools";
    items: ComposerMenuItem[];
    disabled?: boolean;
    /** Invoked for an item that is available. A blocked one is a link. */
    onchoose: (id: string) => void;
  } = $props();

  let open = $state(false);
  let root = $state<HTMLDivElement>();
  let trigger = $state<HTMLButtonElement>();

  const TRIGGER = {
    add: { icon: "plus" as const, label: "Add to this turn", heading: "Add to this turn" },
    tools: { icon: "tool" as const, label: "Tools", heading: "Tools" },
  };
  const chrome = $derived(TRIGGER[kind]);

  function choose(item: ComposerMenuItem) {
    open = false;
    if (item.blocked === null) onchoose(item.id);
  }

  $effect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (root !== undefined && !root.contains(event.target as Node)) open = false;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
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
  <div class="action-menu" bind:this={root}>
    <button
      type="button"
      class="composer-control action-trigger"
      class:is-tools={kind === "tools"}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label={chrome.label}
      title={chrome.label}
      {disabled}
      bind:this={trigger}
      onclick={() => (open = !open)}
    >
      <Icon name={chrome.icon} size="sm" />
      {#if kind === "tools"}<span class="trigger-label">Tools</span>{/if}
    </button>

    {#if open}
      <div class="sheet-scrim" role="presentation" onclick={() => (open = false)}></div>
      <div class="menu menu-surface" role="menu" aria-label={chrome.heading}>
        <p class="menu-heading">{chrome.heading}</p>
        {#each items as item (item.id)}
          {#if item.blocked === null}
            <!-- The name is the label; the hint is a description. Without
                 that split an item announces as "Dictate Speak instead of
                 typing. Transcribed by the runtime you chose." — one long
                 sentence where a screen-reader user expects a name, and a
                 different string every time the copy is edited. -->
            <button
              type="button"
              role="menuitem"
              class="menu-item entry"
              aria-label={item.label}
              aria-describedby={`${kind}-${item.id}-hint`}
              onclick={() => choose(item)}
            >
              <Icon name={item.icon} size="sm" />
              <span class="entry-copy">
                <span class="entry-label">{item.label}</span>
                <span class="entry-hint" id={`${kind}-${item.id}-hint`}>{item.hint}</span>
              </span>
            </button>
          {:else}
            <!-- COMPOSER-04 — a capability that is off stays listed, with the
                 reason and the way to change it. Hiding it teaches the owner
                 that Raiker cannot do the thing at all, which is a worse and
                 less true answer than "this is off, here is the switch". -->
            <a
              role="menuitem"
              class="menu-item entry blocked"
              href={item.blocked.href ?? "#/capabilities"}
              aria-label={item.label}
              aria-describedby={`${kind}-${item.id}-hint`}
              onclick={() => (open = false)}
            >
              <Icon name={item.icon} size="sm" />
              <span class="entry-copy">
                <span class="entry-label">{item.label}</span>
                <span class="entry-hint blocked-hint" id={`${kind}-${item.id}-hint`}
                  >{item.blocked.reason}</span
                >
              </span>
              <Icon name="chevron-right" size="sm" />
            </a>
          {/if}
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .action-menu {
    position: relative;
    display: inline-flex;
  }
  /* The same shape the composer's attach control already had, so the bar keeps
     one button language rather than gaining a third. */
  .action-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.3rem;
    min-height: 32px;
    width: 32px;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    cursor: pointer;
  }
  .action-trigger.is-tools {
    width: auto;
    padding: 0 0.6rem;
  }
  .action-trigger:hover:not(:disabled) {
    border-color: var(--accent-border);
    color: var(--accent);
  }
  .action-trigger[aria-expanded="true"] {
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--accent);
  }
  .action-trigger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .action-trigger:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 1px;
  }
  .trigger-label {
    font-size: var(--text-xs);
  }
  .menu {
    position: absolute;
    left: 0;
    bottom: calc(100% + 6px);
    z-index: 70;
    width: min(21rem, calc(100vw - 2rem));
    display: grid;
    gap: 1px;
    padding: 0.3rem;
    text-align: left;
  }
  .menu-heading {
    margin: 0;
    padding: 0.25rem 0.45rem 0.35rem;
    color: var(--text-3);
    font-size: var(--text-2xs);
    font-weight: 650;
  }
  .entry {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.45rem;
    border-radius: var(--r-sm);
    color: var(--text-1);
    text-align: left;
    text-decoration: none;
  }
  .entry-copy {
    display: grid;
    gap: 0.05rem;
    min-width: 0;
  }
  .entry-label {
    font-size: var(--text-sm);
  }
  .entry-hint {
    color: var(--text-3);
    font-size: var(--text-2xs);
    overflow-wrap: anywhere;
  }
  /* VIS2-16 — the one toned line, because it is the one that is not ordinary. */
  .blocked-hint {
    color: var(--warn);
  }
  .entry.blocked:hover {
    text-decoration: none;
  }
  .sheet-scrim {
    display: none;
  }

  /* COMPOSER-16 — a bottom sheet below the split. */
  @media (max-width: 47.9rem) {
    .sheet-scrim {
      display: block;
      position: fixed;
      inset: 0;
      z-index: 95;
      background: var(--overlay);
    }
    .menu {
      position: fixed;
      inset: auto 0 0 0;
      z-index: 100;
      width: auto;
      max-height: 70vh;
      overflow-y: auto;
      border-radius: var(--r-lg) var(--r-lg) 0 0;
      padding: var(--space-3) var(--space-3) var(--space-5);
      box-shadow: var(--shadow-3);
    }
    .entry {
      min-height: 2.75rem;
    }
  }
</style>
