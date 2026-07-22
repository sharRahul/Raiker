<script lang="ts">
  import Icon from "./Icon.svelte";
  import Logo from "./Logo.svelte";
  import { NAV_GROUPS, navItem } from "../nav";
  import { api } from "../api";
  import type { ProjectView, SessionSummary } from "../apiTypes";
  import { relativeTime } from "../format";

  let { current }: { current: string } = $props();
  let recent = $state<SessionSummary[]>([]);
  let projects = $state<ProjectView[]>([]);

  // "⋯" menu state for recent chats. `menuFor` holds the session_id whose menu
  // is open; `moveOpen` flips the menu from actions → project picker. A
  // transparent backdrop button catches outside clicks to close.
  let menuFor = $state<string | null>(null);
  let moveOpen = $state(false);
  let busy = $state(false);
  let actionError = $state<string | null>(null);
  const phoneNavItems = ["home", "new-chat", "approvals", "connections"].map(navItem);
  let navigationOpen = $state(false);
  let returnFocusTo: HTMLButtonElement | null = null;

  function openNavigation(event: MouseEvent) {
    returnFocusTo = event.currentTarget as HTMLButtonElement;
    navigationOpen = true;
  }

  function closeNavigation(restoreFocus = true) {
    navigationOpen = false;
    if (restoreFocus) returnFocusTo?.focus();
    returnFocusTo = null;
  }

  $effect(() => {
    if (!navigationOpen) return;
    const closeForEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeNavigation();
    };
    const closeForResize = () => closeNavigation(false);
    window.addEventListener("keydown", closeForEscape);
    window.addEventListener("resize", closeForResize);
    return () => {
      window.removeEventListener("keydown", closeForEscape);
      window.removeEventListener("resize", closeForResize);
    };
  });

  async function loadRecent() {
    try {
      const all = await api.sessions();
      // Drop untitled chats from the sidebar — they are freshly-created empty
      // conversations with no first prompt yet. They still exist in Sessions
      // (where they show as their short id), but here they would read as
      // "Untitled chat" noise.
      recent = all.filter((s) => s.title !== null && s.title.trim() !== "").slice(0, 5);
    } catch {
      recent = [];
    }
  }

  async function loadProjects() {
    try {
      projects = (await api.projects()).projects;
    } catch {
      projects = [];
    }
  }

  $effect(() => {
    void loadRecent();
    void loadProjects();
    const refresh = () => { void loadRecent(); void loadProjects(); };
    window.addEventListener("raiker:chats-changed", refresh);
    window.addEventListener("raiker:projects-changed", refresh);
    return () => {
      window.removeEventListener("raiker:chats-changed", refresh);
      window.removeEventListener("raiker:projects-changed", refresh);
    };
  });

  function openMenu(sessionId: string) {
    menuFor = sessionId;
    moveOpen = false;
    actionError = null;
  }
  function closeMenu() {
    menuFor = null;
    moveOpen = false;
    actionError = null;
  }

  function onDragStart(event: DragEvent, chat: SessionSummary) {
    if (event.dataTransfer === null) return;
    event.dataTransfer.setData("text/raiker-session-id", chat.session_id);
    event.dataTransfer.setData("text/plain", chat.session_id);
    event.dataTransfer.effectAllowed = "move";
  }

  async function deleteChat(chat: SessionSummary) {
    if (busy) return;
    if (!window.confirm(`Delete "${chat.title ?? "this chat"}"? This permanently removes the conversation and its turns.`)) return;
    busy = true;
    actionError = null;
    try {
      await api.deleteSession(chat.session_id);
      closeMenu();
      window.dispatchEvent(new CustomEvent("raiker:chats-changed"));
    } catch {
      actionError = "Could not delete this chat.";
    } finally {
      busy = false;
    }
  }

  async function moveToProject(chat: SessionSummary, projectId: string | null) {
    if (busy) return;
    busy = true;
    actionError = null;
    try {
      await api.setSessionProject(chat.session_id, projectId);
      closeMenu();
      window.dispatchEvent(new CustomEvent("raiker:chats-changed"));
    } catch {
      actionError = "Could not move this chat.";
    } finally {
      busy = false;
    }
  }
</script>

<button type="button" class="tablet-toggle btn btn-ghost" aria-expanded={navigationOpen} aria-controls="all-navigation" onclick={openNavigation}>
  Menu
</button>

{#if navigationOpen}
  <button type="button" class="drawer-scrim" aria-label="Close navigation" onclick={() => closeNavigation()}></button>
{/if}

<nav id="all-navigation" class="sidebar" class:open={navigationOpen} aria-label="All navigation">
  <button type="button" class="drawer-close btn btn-ghost" onclick={() => closeNavigation()}>Close</button>
  <a class="brand" href="#/home">
    <Logo size={30} />
    <span class="brand-text">
      <span class="brand-name">Raiker</span>
      <span class="brand-sub">Governed agent</span>
    </span>
  </a>

  {#each NAV_GROUPS as group (group.label)}
    <div class="group">
      <p class="group-label">{group.label}</p>
      <ul>
        {#each group.items as item (item.id)}
          <li>
            <a
              href={`#/${item.id}`}
              class="nav-link"
              class:active={current === item.id}
              aria-current={current === item.id ? "page" : undefined}
              aria-label={item.label}
              title={item.hint}
              onclick={() => closeNavigation(false)}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </a>
          </li>
        {/each}
      </ul>
      {#if group.label === "Work" && recent.length > 0}
        <div class="recent" aria-label="Recent chats">
          <p class="recent-label">Recent chats</p>
          {#each recent as chat (chat.session_id)}
            <div class="recent-row" class:menu-open={menuFor === chat.session_id}>
              <a
                class="recent-chat"
                href={`#/new-chat?session=${encodeURIComponent(chat.session_id)}`}
                title={chat.title ?? "Untitled chat"}
                draggable="true"
                ondragstart={(e) => onDragStart(e, chat)}
              >
                <span>{chat.title ?? "Untitled chat"}</span>
                <small>{relativeTime(chat.updated_at)}</small>
              </a>
              <button
                type="button"
                class="chat-menu-btn"
                aria-label={`More options for ${chat.title ?? "Untitled chat"}`}
                aria-expanded={menuFor === chat.session_id}
                onclick={(e) => { e.preventDefault(); e.stopPropagation(); if (menuFor === chat.session_id) { closeMenu(); } else { openMenu(chat.session_id); } }}
              >⋯</button>

              {#if menuFor === chat.session_id}
                <div class="chat-menu" role="menu">
                  {#if !moveOpen}
                    <button type="button" class="menu-item danger" role="menuitem" onclick={() => void deleteChat(chat)} disabled={busy}>Delete chat</button>
                    <button type="button" class="menu-item" role="menuitem" onclick={() => (moveOpen = true)} disabled={busy}>Move to project…</button>
                  {:else}
                    <p class="menu-hint">Move “{chat.title ?? "Untitled chat"}” to:</p>
                    <button type="button" class="menu-item" role="menuitem" onclick={() => void moveToProject(chat, null)} disabled={busy}>No project</button>
                    {#each projects as p (p.project_id)}
                      <button type="button" class="menu-item" role="menuitem" onclick={() => void moveToProject(chat, p.project_id)} disabled={busy}>{p.name}</button>
                    {/each}
                    <button type="button" class="menu-item back" role="menuitem" onclick={() => (moveOpen = false)} disabled={busy}>← Back</button>
                  {/if}
                  {#if actionError}<p class="menu-error" role="alert">{actionError}</p>{/if}
                </div>
              {/if}
            </div>
          {/each}
          {#if menuFor !== null}
            <button type="button" class="menu-backdrop" aria-label="Close menu" tabindex="-1" onclick={closeMenu}></button>
          {/if}
        </div>
      {/if}
    </div>
  {/each}

  <p class="local-note">
    <Icon name="lock" size={13} />
    Local &amp; loopback-only
  </p>
</nav>

<nav class="phone-nav" aria-label="Primary">
  {#each phoneNavItems as item (item.id)}
    <a
      class="phone-link"
      class:active={current === item.id}
      href={`#/${item.id}`}
      aria-current={current === item.id ? "page" : undefined}
      aria-label={item.label}
    >
      <Icon name={item.icon} size={18} />
      <span>{item.label}</span>
    </a>
  {/each}
  <button type="button" class="phone-more" aria-label="More navigation" aria-expanded={navigationOpen} aria-controls="all-navigation" onclick={openNavigation}>
    <Icon name="chevron-right" size={18} />
    <span>More</span>
  </button>
</nav>

<style>
  .sidebar {
    width: var(--sidebar-w);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-3);
    border-right: 1px solid var(--border);
    background: var(--surface);
    overflow-y: auto;
  }
  .tablet-toggle, .phone-nav, .drawer-scrim, .drawer-close { display: none; }
  .brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.25rem 0.5rem;
    text-decoration: none;
  }
  .brand:hover {
    text-decoration: none;
  }
  .brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }
  .brand-name {
    font-family: var(--font-sans);
    font-weight: 800;
    font-size: 0.78rem;
    letter-spacing: 0.45em;
    text-transform: uppercase;
    color: var(--text-1);
  }
  .brand-sub {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--text-3);
  }
  .group-label {
    font-size: 0.68rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--text-3);
    margin: 0 0 0.3rem;
    padding: 0 0.55rem;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nav-link {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.42rem 0.55rem;
    border-radius: var(--r-sm);
    color: var(--text-2);
    font-size: 0.88rem;
    font-weight: 550;
    text-decoration: none;
    transition:
      background 100ms var(--ease),
      color 100ms var(--ease);
  }
  .nav-link:hover {
    background: var(--sunken);
    color: var(--text-1);
    text-decoration: none;
  }
  .nav-link.active {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 650;
  }
  .local-note {
    margin-top: auto;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.72rem;
    color: var(--text-3);
    padding: 0 0.55rem;
  }
  .recent { border-top: 1px solid var(--border); margin: var(--space-3) 0 0.45rem; padding: var(--space-3) 0.55rem 0; position: relative; }
  .recent-label { color: var(--text-3); font-size: 0.66rem; font-weight: 700; letter-spacing: 0.08em; margin: 0 0 0.35rem; text-transform: uppercase; }
  .recent-row { position: relative; }
  .recent-chat { color: var(--text-2); display: flex; flex-direction: column; font-size: 0.78rem; gap: 0.1rem; padding: 0.28rem 1.6rem 0.28rem 0; text-decoration: none; cursor: pointer; }
  .recent-chat:hover { color: var(--accent); text-decoration: none; }
  .recent-chat span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .recent-chat small { color: var(--text-3); font-size: 0.67rem; }
  .recent-row.menu-open .recent-chat { color: var(--accent); }

  .chat-menu-btn {
    position: absolute;
    top: 0.18rem;
    right: 0;
    appearance: none;
    border: 0;
    background: transparent;
    color: var(--text-3);
    font-size: 1rem;
    line-height: 1;
    padding: 0.18rem 0.25rem;
    border-radius: var(--r-sm);
    cursor: pointer;
    opacity: 0;
    transition: opacity 120ms var(--ease), background 120ms var(--ease);
  }
  .recent-row:hover .chat-menu-btn,
  .recent-row.menu-open .chat-menu-btn,
  .chat-menu-btn:focus-visible { opacity: 1; }
  .chat-menu-btn:hover { background: var(--sunken); color: var(--text-1); }

  .chat-menu {
    position: absolute;
    z-index: 60;
    top: 1.55rem;
    right: 0;
    left: 0;
    background: var(--raised);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    box-shadow: var(--shadow-2);
    padding: 0.3rem;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 11rem;
  }
  .menu-item {
    appearance: none;
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: 0.82rem;
    text-align: left;
    padding: 0.4rem 0.55rem;
    border-radius: var(--r-sm);
    cursor: pointer;
  }
  .menu-item:hover:not(:disabled) { background: var(--accent-soft); color: var(--accent); }
  .menu-item.danger { color: var(--danger); }
  .menu-item.danger:hover:not(:disabled) { background: var(--danger-soft); }
  .menu-item.back { color: var(--text-3); margin-top: 2px; border-top: 1px solid var(--border); border-radius: 0 0 var(--r-sm) var(--r-sm); padding-top: 0.35rem; }
  .menu-item:disabled { opacity: 0.5; cursor: not-allowed; }
  .menu-hint { color: var(--text-3); font-size: 0.7rem; margin: 0.15rem 0.55rem 0.3rem; line-height: 1.25; }
  .menu-error { color: var(--danger); font-size: 0.72rem; margin: 0.25rem 0.55rem; }

  .menu-backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    background: transparent;
    border: 0;
    cursor: default;
    appearance: none;
  }
  @media (max-width: 1023px) {
    .tablet-toggle { display: inline-flex; position: fixed; top: 0.5rem; left: var(--space-3); z-index: 70; }
    .drawer-scrim { display: block; position: fixed; inset: 0; z-index: 90; border: 0; background: var(--overlay); cursor: default; }
    .sidebar { position: fixed; inset: 0 auto 0 0; z-index: 100; width: min(19rem, 84vw); transform: translateX(-105%); transition: transform 160ms var(--ease); box-shadow: var(--shadow-2); }
    .sidebar.open { transform: translateX(0); }
    .drawer-close { display: inline-flex; align-self: flex-end; }
  }
  @media (max-width: 639px) {
    .tablet-toggle { display: none; }
    .phone-nav { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); position: fixed; inset: auto 0 0; z-index: 70; min-height: 4rem; padding-bottom: env(safe-area-inset-bottom); background: var(--surface); border-top: 1px solid var(--border); box-shadow: var(--shadow-1); }
    .phone-link, .phone-more { display: grid; place-items: center; gap: 0.1rem; min-width: 0; padding: 0.4rem 0.2rem; color: var(--text-3); background: transparent; border: 0; font: inherit; font-size: 0.64rem; font-weight: 650; text-decoration: none; }
    .phone-link.active, .phone-more[aria-expanded="true"] { color: var(--accent); }
    .phone-link:hover, .phone-more:hover { background: var(--sunken); color: var(--text-1); text-decoration: none; }
  }
  @media (min-width: 1024px) {
    .phone-nav, .tablet-toggle, .drawer-scrim, .drawer-close { display: none; }
  }
</style>
