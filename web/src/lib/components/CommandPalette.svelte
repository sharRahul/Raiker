<script lang="ts">
  /**
   * One launcher for everything the product can reach.
   *
   * The rail lost four rows (the rail's row budget) and the gear's window is a list you have
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
   * * **Help** — every help article (QUI-L05), which opens in the help panel.
   *
   * QUI-F22 — and the owner's own things: **Chats** (the server's chat
   * search, debounced, so a keystroke never waits on it), **Tasks** and
   * **Memories** (read once when the palette opens, matched as you type). A
   * row of type filters narrows the list to one kind.
   */
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";
  import { NAV_ITEMS, HUB_TABS, SIDEBAR_ITEM_IDS } from "../nav";
  import { settingsSection } from "../settingsSections";
  import { activateModalDrawer, type DeactivateModalDrawer } from "../modalDrawer";
  import { api } from "../api";
  import { humanize, relativeTime } from "../format";

  let {
    open = false,
    returnFocusTo = null,
    onClose = () => {},
  }: {
    open?: boolean;
    returnFocusTo?: HTMLElement | null;
    onClose?: () => void;
  } = $props();

  type Group = "Commands" | "Pages" | "Chats" | "Tasks" | "Memories" | "Settings" | "Help";
  const GROUPS: Group[] = ["Commands", "Pages", "Chats", "Tasks", "Memories", "Settings", "Help"];
  /** QUI-F22 — the type filters, in the order the results are grouped. */
  const FILTERS: { id: "all" | Group; label: string }[] = [
    { id: "all", label: "All" },
    { id: "Chats", label: "Chats" },
    { id: "Tasks", label: "Tasks" },
    { id: "Memories", label: "Memories" },
    { id: "Settings", label: "Settings" },
    { id: "Help", label: "Help" },
  ];
  let filter = $state<"all" | Group>("all");

  interface Entry {
    id: string;
    label: string;
    group: Group;
    hint: string;
    icon: IconName;
    href: string;
    /** What is matched besides the label and hint, when the row shows less. */
    search?: string;
  }


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
    label: settingsSection(section)?.label ?? section,
    group: "Settings" as const,
    hint: "Settings",
    icon: settingsSection(section)?.icon ?? ("settings" as IconName),
    href: `#/settings?tab=${section}`,
  }));

  // QUI-L05 — the help articles, read once the palette is first opened.
  let HELP = $state<Entry[]>([]);
  let helpRead = false;
  $effect(() => {
    if (!open || helpRead) return;
    helpRead = true;
    void api
      .guide()
      .then((index) => {
        HELP = (index.sections ?? []).map((section) => ({
          id: `help-${section.slug}`,
          label: section.title,
          group: "Help" as const,
          hint: section.summary ?? "Help article",
          icon: "help" as IconName,
          href: `#/guide?section=${section.slug}`,
        }));
      })
      .catch(() => {
        // Help is one group among four; the others still answer.
      });
  });

  // QUI-F22 — tasks and memories, read once per opening; chats searched as typed.
  let TASKS = $state<Entry[]>([]);
  let MEMORIES = $state<Entry[]>([]);
  let CHATS = $state<Entry[]>([]);
  $effect(() => {
    if (!open) return;
    void api
      .tasks()
      .then((tasks) => {
        TASKS = tasks.map((task) => ({
          id: `task-${task.task_id}`,
          label: task.title || "Untitled task",
          group: "Tasks" as const,
          hint: (task.objective ?? "").slice(0, 120) || humanize(task.status),
          icon: "tasks" as IconName,
          href: `#/tasks?task=${encodeURIComponent(task.task_id)}`,
        }));
      })
      .catch(() => (TASKS = []));
    void api
      .memories()
      .then((records) => {
        MEMORIES = records.map((record) => ({
          id: `memory-${record.memory_id}`,
          label: record.text.length > 80 ? `${record.text.slice(0, 79)}…` : record.text,
          group: "Memories" as const,
          hint: `Memory · ${relativeTime(record.created_at)}`,
          search: record.text,
          icon: "memory" as IconName,
          href: `#/memory?tab=memories&record=${encodeURIComponent(record.memory_id)}`,
        }));
      })
      .catch(() => (MEMORIES = []));
  });
  $effect(() => {
    const needle = query.trim();
    if (!open || needle.length < 2) {
      CHATS = [];
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api
        .searchChats(needle)
        .then((sessions) => {
          if (cancelled) return;
          CHATS = sessions.slice(0, 8).map((session) => ({
            id: `chat-${session.session_id}`,
            label: session.title || "Untitled conversation",
            group: "Chats" as const,
            // The server already matched it: its snippet says where.
            hint: (session.match_snippet ?? "").trim() || needle,
            icon: "chat" as IconName,
            href: `#/new-chat?session=${encodeURIComponent(session.session_id)}${session.match_turn_id ? `&turn=${encodeURIComponent(session.match_turn_id)}` : ""}`,
          }));
        })
        .catch(() => {
          if (!cancelled) CHATS = [];
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  });

  const ALL: Entry[] = $derived([...COMMANDS, ...PAGES, ...CHATS, ...TASKS, ...MEMORIES, ...SETTINGS, ...HELP]);

  let query = $state("");
  let active = $state(0);
  let panel = $state<HTMLElement>();
  let input = $state<HTMLInputElement>();
  let deactivate: DeactivateModalDrawer | null = null;

  const matches = $derived.by(() => {
    const needle = query.trim().toLowerCase();
    const pool = filter === "all" ? ALL : ALL.filter((entry) => entry.group === filter);
    if (needle === "") {
      // Unfiltered, an empty query shows the product's own places; a filter
      // shows what it holds.
      return filter === "all" ? pool.filter((entry) => entry.group !== "Tasks" && entry.group !== "Memories").slice(0, 12) : pool.slice(0, 24);
    }
    return pool
      .filter(
        (entry) =>
          entry.group === "Chats" ||
          entry.label.toLowerCase().includes(needle) ||
          entry.hint.toLowerCase().includes(needle) ||
          (entry.search ?? "").toLowerCase().includes(needle),
      )
      .slice(0, 30);
  });

  // Grouped for display, but `matches` stays the flat list the keyboard moves
  // through — two orders would let the highlight and Enter disagree.
  const grouped = $derived.by(() => {
    return GROUPS
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
    filter = "all";
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
          placeholder="Search chats, tasks, memories, settings and help"
          aria-label="Search everything"
          aria-controls="palette-results"
          autocomplete="off"
        />
        <kbd>Esc</kbd>
      </div>
      <div class="filters" role="group" aria-label="Show only">
        {#each FILTERS as item (item.id)}
          <button
            type="button"
            class="filter"
            aria-pressed={filter === item.id}
            onclick={() => {
              filter = item.id;
              input?.focus();
            }}>{item.label}</button
          >
        {/each}
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
    z-index: var(--z-palette);
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
  .filters {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
    padding: var(--space-2) var(--space-4) 0;
  }
  .filter {
    padding: 0.15rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: var(--text-xs);
    cursor: pointer;
  }
  .filter[aria-pressed="true"] {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--accent);
  }
  .results {
    overflow-y: auto;
    padding: var(--space-2);
  }
  /* Sentence case, no tracking. A group label is a quiet signpost, not
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
