<script lang="ts">
  /**
   * VIS-22 — one launcher for everything the product can reach.
   *
   * The rail lost four rows (VIS-01) and the gear's window is a list you have
   * to open and read. Neither is how someone who uses Raiker every day wants to
   * move: they know the name of the thing. `Ctrl/Cmd+K` takes the name.
   *
   * This is what *allows* the rail to shrink. Discoverability and permanence
   * are different problems, and a permanent row is an expensive way to solve
   * discoverability — the palette solves it for every destination at once,
   * including the ones that never earned a row.
   *
   * What it searches, in the order results are grouped:
   *
   * * **Commands** — verbs. Start a chat, open approvals, stop all work.
   * * **Pages** — every destination in `NAV_ITEMS`, on the rail or not.
   * * **Settings** — each section of the settings rail, so "privacy" lands on
   *   Privacy rather than on Settings' front page.
   *
   * Threads, projects and tasks are deliberately not here yet: they need a
   * debounced server search, and a palette that stalls on every keystroke is
   * worse than one that only knows the product. The grouping leaves room.
   */
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";
  import { NAV_ITEMS, HUB_TABS, SIDEBAR_ITEM_IDS } from "../nav";
  import { activateModalDrawer, type DeactivateModalDrawer } from "../modalDrawer";

  let {
    open = false,
    returnFocusTo = null,
    onClose = () => {},
  }: {
    open?: boolean;
    returnFocusTo?: HTMLElement | null;
    onClose?: () => void;
  } = $props();

  interface Entry {
    id: string;
    label: string;
    group: "Commands" | "Pages" | "Settings";
    hint: string;
    icon: IconName;
    href: string;
  }

  const SETTINGS_LABELS: Record<string, string> = {
    general: "General",
    notification: "Notifications",
    personalisation: "Personalisation",
    security: "Security & sign-in",
    privacy: "Privacy",
    account: "Account",
    "web-access": "Web access",
    "git-credential": "Git credentials",
    runtime: "Runtime",
    updates: "Updates",
  };

  const COMMANDS: Entry[] = [
    { id: "cmd-chat", label: "New chat", group: "Commands", hint: "Start a governed conversation", icon: "chat", href: "#/new-chat" },
    { id: "cmd-build", label: "New build session", group: "Commands", hint: "Code against a repository", icon: "code", href: "#/build" },
    { id: "cmd-task", label: "New task", group: "Commands", hint: "Work that continues after you leave", icon: "tasks", href: "#/tasks" },
    { id: "cmd-project", label: "New project", group: "Commands", hint: "A named scope for ongoing work", icon: "projects", href: "#/projects" },
    { id: "cmd-approvals", label: "Open approvals", group: "Commands", hint: "Decisions waiting on you", icon: "approvals", href: "#/approvals" },
  ];

  const PAGES: Entry[] = NAV_ITEMS.map((item) => ({
    id: `page-${item.id}`,
    label: item.label,
    group: "Pages" as const,
    // A destination that is not on the rail says so, because "where do I find
    // this again?" is the question the palette is answering.
    hint: SIDEBAR_ITEM_IDS.includes(item.id) ? item.hint : `${item.hint} · not on the sidebar`,
    icon: item.icon,
    href: `#/${item.id}`,
  }));

  const SETTINGS: Entry[] = (HUB_TABS.settings ?? []).map((section) => ({
    id: `setting-${section}`,
    label: SETTINGS_LABELS[section] ?? section,
    group: "Settings" as const,
    hint: "Settings",
    icon: "settings" as IconName,
    href: `#/settings?tab=${section}`,
  }));

  const ALL: Entry[] = [...COMMANDS, ...PAGES, ...SETTINGS];

  let query = $state("");
  let active = $state(0);
  let panel = $state<HTMLElement>();
  let input = $state<HTMLInputElement>();
  let deactivate: DeactivateModalDrawer | null = null;

  const matches = $derived.by(() => {
    const needle = query.trim().toLowerCase();
    if (needle === "") return ALL.slice(0, 12);
    return ALL.filter(
      (entry) =>
        entry.label.toLowerCase().includes(needle) ||
        entry.hint.toLowerCase().includes(needle),
    ).slice(0, 24);
  });

  // Grouped for display, but `matches` stays the flat list the keyboard moves
  // through — two orders would let the highlight and Enter disagree.
  const grouped = $derived.by(() => {
    const order: Entry["group"][] = ["Commands", "Pages", "Settings"];
    return order
      .map((group) => ({ group, entries: matches.filter((entry) => entry.group === group) }))
      .filter((section) => section.entries.length > 0);
  });

  $effect(() => {
    // Any change to the result set puts the highlight back on the first row;
    // leaving it where it was selects whatever happens to be at that index.
    void matches;
    active = 0;
  });

  function close(restoreFocus = true) {
    deactivate?.(restoreFocus);
    deactivate = null;
    query = "";
    onClose();
  }

  function choose(entry: Entry) {
    window.location.hash = entry.href;
    close(false);
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      active = matches.length === 0 ? 0 : (active + 1) % matches.length;
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      active = matches.length === 0 ? 0 : (active - 1 + matches.length) % matches.length;
    } else if (event.key === "Enter") {
      event.preventDefault();
      const entry = matches[active];
      if (entry !== undefined) choose(entry);
    }
  }

  $effect(() => {
    if (!open || panel === undefined) return;
    deactivate = activateModalDrawer({
      id: "command-palette",
      container: panel,
      returnFocusTo,
      backgroundElements: [],
      onDismiss: () => close(true),
    });
    input?.focus();
    return () => {
      deactivate?.(false);
      deactivate = null;
    };
  });
</script>

{#if open}
  <div class="scrim">
    <div
      class="palette motion-enter"
      role="dialog"
      aria-modal="true"
      aria-label="Search and commands"
      bind:this={panel}
    >
      <div class="search">
        <Icon name="search" size="md" />
        <input
          type="text"
          bind:this={input}
          bind:value={query}
          onkeydown={onKeydown}
          placeholder="Search pages, settings and commands"
          aria-label="Search pages, settings and commands"
          aria-controls="palette-results"
          autocomplete="off"
        />
        <kbd>Esc</kbd>
      </div>
      <div class="results" id="palette-results" role="listbox" aria-label="Results">
        {#if matches.length === 0}
          <p class="no-match">Nothing matches “{query}”.</p>
        {:else}
          {#each grouped as section (section.group)}
            <p class="group">{section.group}</p>
            {#each section.entries as entry (entry.id)}
              <button
                type="button"
                role="option"
                aria-selected={matches[active]?.id === entry.id}
                class="row"
                class:active={matches[active]?.id === entry.id}
                onclick={() => choose(entry)}
                onmouseenter={() => { active = matches.findIndex((m) => m.id === entry.id); }}
              >
                <Icon name={entry.icon} size="md" />
                <span class="row-label">{entry.label}</span>
                <span class="row-hint">{entry.hint}</span>
              </button>
            {/each}
          {/each}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 120;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 12vh var(--space-4) var(--space-4);
    background: var(--overlay);
  }
  .palette {
    width: min(40rem, 100%);
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--raised);
    box-shadow: var(--shadow-3);
    overflow: hidden;
  }
  .search {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border);
    color: var(--text-3);
  }
  .search input {
    flex: 1;
    min-width: 0;
    border: 0;
    background: transparent;
    color: var(--text-1);
    font-size: var(--text-base);
    outline: none;
  }
  .search kbd {
    font-family: var(--font-mono);
    font-size: var(--text-2xs);
    color: var(--text-3);
    border: 1px solid var(--border);
    border-radius: var(--r-xs);
    padding: 0.05rem 0.3rem;
  }
  .results {
    overflow-y: auto;
    padding: var(--space-2);
  }
  /* VIS-06 — sentence case, no tracking. A group label is a quiet signpost, not
     a heading that has to shout to be found. */
  .group {
    margin: var(--space-2) var(--space-2) 0.15rem;
    color: var(--text-3);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .row {
    display: grid;
    grid-template-columns: auto auto 1fr;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: 0.45rem var(--space-2);
    border: 0;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-1);
    text-align: left;
    font-size: var(--text-md);
  }
  .row.active {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .row-label {
    font-weight: 600;
  }
  .row-hint {
    color: var(--text-3);
    font-size: var(--text-xs);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .row.active .row-hint {
    color: var(--accent);
    opacity: 0.75;
  }
  .no-match {
    margin: 0;
    padding: var(--space-4);
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  @media (max-width: 720px) {
    .scrim {
      padding: var(--space-4) var(--space-3);
    }
    .row-hint {
      display: none;
    }
  }
</style>
