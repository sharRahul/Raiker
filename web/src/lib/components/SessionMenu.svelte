<script lang="ts">
  import { isLoopbackHost } from "../loopback";

  type Project = { project_id: string; name: string };
  let {
    sessionId, title, projects = [], pinned = false, archived = false,
    onRename, onMove, onPin, onArchive, onDelete,
  }: {
    sessionId: string; title: string; projects?: Project[]; pinned?: boolean; archived?: boolean;
    onRename: (title: string) => void;
    onMove: (projectId: string) => void; onPin: () => void; onArchive: () => void; onDelete: () => void;
  } = $props();
  let open = $state(false);
  let renaming = $state(false);
  let moving = $state(false);
  let name = $state("");
  let triggerEl: HTMLButtonElement | undefined = $state();

  function closeOnEscape(event: KeyboardEvent) {
    if (event.key !== "Escape" || !open) return;
    open = false;
    queueMicrotask(() => triggerEl?.focus());
  }

  async function copyLocalLink() {
    if (!navigator.clipboard || !isLoopbackHost(window.location.hostname)) return;
    await navigator.clipboard.writeText(`${window.location.origin}/#/new-chat?session=${encodeURIComponent(sessionId)}`);
  }
</script>

<div class="wrap">
  <button
    bind:this={triggerEl}
    type="button"
    class="trigger icon-button"
    aria-label={`Session actions for ${title}`}
    aria-expanded={open}
    onclick={() => (open = !open)}
  >•••</button>
  {#if open}
    <div class="menu menu-surface" role="menu" aria-label={`Actions for ${title}`} tabindex="-1" onkeydown={closeOnEscape}>
      <button class="menu-item" type="button" role="menuitem" onclick={copyLocalLink}>Copy local link</button>
      <button class="menu-item" type="button" role="menuitem" onclick={() => { name = title; renaming = true; }}>Rename</button>
      {#if renaming}
        <label>Session title <input bind:value={name} /></label>
        <button class="menu-item" type="button" role="menuitem" onclick={() => { onRename(name); renaming = false; }}>Save name</button>
      {/if}
      <button class="menu-item" type="button" role="menuitem" onclick={() => (moving = !moving)}>Move to project</button>
      {#if moving}
        <button class="menu-item" type="button" role="menuitem" onclick={() => onMove("")}>No project</button>
        {#each projects as project (project.project_id)}
          <button class="menu-item" type="button" role="menuitem" onclick={() => onMove(project.project_id)}>{project.name}</button>
        {/each}
      {/if}
      <button class="menu-item" type="button" role="menuitem" onclick={onPin}>{pinned ? "Unpin" : "Pin"}</button>
      <button class="menu-item" type="button" role="menuitem" onclick={onArchive}>{archived ? "Unarchive" : "Archive"}</button>
      <button type="button" role="menuitem" class="menu-item danger" onclick={onDelete}>Delete</button>
    </div>
  {/if}
</div>

<style>
  .wrap { position: relative; display: inline-block; }
  .trigger {
    border: 1px solid transparent;
    border-radius: var(--r-sm);
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    padding: 0.15rem 0.4rem;
    line-height: 1;
  }
  .trigger:hover { background: var(--sunken); color: var(--text-1); }
  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 40;
    min-width: 11rem;
    display: grid;
    gap: var(--space-1);
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .menu button {
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--r-sm);
    text-align: left;
    cursor: pointer;
  }
  .menu button:hover { background: var(--accent-soft); }
  .menu button.danger { color: var(--danger); }
  .menu button.danger:hover { background: var(--danger-soft); }
  .menu label {
    display: grid;
    gap: 0.2rem;
    font-size: var(--text-xs);
    color: var(--text-2);
    padding: 0 var(--space-2);
  }
  .menu input {
    font: inherit;
    font-size: var(--text-sm);
    padding: 0.25rem 0.4rem;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-1);
  }
</style>
