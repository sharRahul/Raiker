<script lang="ts">
  import Icon from "./Icon.svelte";
  import Logo from "./Logo.svelte";
  import { NAV_GROUPS } from "../nav";
  import { api } from "../api";
  import type { SessionSummary } from "../apiTypes";
  import { relativeTime } from "../format";

  let { current }: { current: string } = $props();
  let recent = $state<SessionSummary[]>([]);

  async function loadRecent() {
    try { recent = (await api.sessions()).slice(0, 5); } catch { recent = []; }
  }
  $effect(() => {
    void loadRecent();
    const refresh = () => void loadRecent();
    window.addEventListener("raiker:chats-changed", refresh);
    return () => window.removeEventListener("raiker:chats-changed", refresh);
  });
</script>

<nav class="sidebar" aria-label="Primary">
  <a class="brand" href="#/chat">
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
              title={item.hint}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </a>
          </li>
        {/each}
      </ul>
      {#if group.label === "The Hustle" && recent.length > 0}
        <div class="recent" aria-label="Recent chats">
          <p class="recent-label">Recent chats</p>
          {#each recent as chat (chat.session_id)}
            <a class="recent-chat" href={`#/new-chat?session=${encodeURIComponent(chat.session_id)}`} title={chat.title ?? "Untitled chat"}>
              <span>{chat.title ?? "Untitled chat"}</span><small>{relativeTime(chat.updated_at)}</small>
            </a>
          {/each}
        </div>
      {/if}
    </div>
  {/each}

  <p class="local-note">
    <Icon name="lock" size={13} />
    Local &amp; loopback-only
  </p>
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
    font-weight: 800;
    font-size: 0.98rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
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
  .recent { border-top: 1px solid var(--border); margin: var(--space-3) 0 0.45rem; padding: var(--space-3) 0.55rem 0; }
  .recent-label { color: var(--text-3); font-size: 0.66rem; font-weight: 700; letter-spacing: 0.08em; margin: 0 0 0.35rem; text-transform: uppercase; }
  .recent-chat { color: var(--text-2); display: flex; flex-direction: column; font-size: 0.78rem; gap: 0.1rem; padding: 0.28rem 0; text-decoration: none; }
  .recent-chat:hover { color: var(--accent); text-decoration: none; }
  .recent-chat span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .recent-chat small { color: var(--text-3); font-size: 0.67rem; }
</style>
