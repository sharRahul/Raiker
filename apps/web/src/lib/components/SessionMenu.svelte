<script lang="ts">
  import { isLoopbackHost } from "../loopback";

  type Project = { project_id: string; name: string };
  let {
    sessionId, title, projects = [], onRename, onMove, onPin, onArchive, onDelete,
  }: {
    sessionId: string; title: string; projects?: Project[]; onRename: (title: string) => void;
    onMove: (projectId: string) => void; onPin: () => void; onArchive: () => void; onDelete: () => void;
  } = $props();
  let open = $state(false);
  let renaming = $state(false);
  let moving = $state(false);
  let name = $state("");

  async function copyLocalLink() {
    if (!navigator.clipboard || !isLoopbackHost(window.location.hostname)) return;
    await navigator.clipboard.writeText(`${window.location.origin}/#/new-chat?session=${encodeURIComponent(sessionId)}`);
  }
</script>

<button type="button" class="trigger" aria-label="Session actions" aria-expanded={open} onclick={() => (open = !open)}>•••</button>
{#if open}
  <div class="menu" role="menu">
    <button type="button" role="menuitem" onclick={copyLocalLink}>Copy local link</button>
    <button type="button" role="menuitem" onclick={() => { name = title; renaming = true; }}>Rename</button>
    {#if renaming}
      <label>Session title <input bind:value={name} /></label>
      <button type="button" role="menuitem" onclick={() => { onRename(name); renaming = false; }}>Save name</button>
    {/if}
    <button type="button" role="menuitem" onclick={() => (moving = !moving)}>Move to project</button>
    {#if moving}
      <button type="button" role="menuitem" onclick={() => onMove("")}>No project</button>
      {#each projects as project (project.project_id)}
        <button type="button" role="menuitem" onclick={() => onMove(project.project_id)}>{project.name}</button>
      {/each}
    {/if}
    <button type="button" role="menuitem" onclick={onPin}>Pin</button>
    <button type="button" role="menuitem" onclick={onArchive}>Archive</button>
    <button type="button" role="menuitem" onclick={onDelete}>Delete</button>
  </div>
{/if}

<style>
  .trigger { border: 0; background: transparent; color: var(--text-2); cursor: pointer; }
  .menu { display: grid; gap: var(--space-1); padding: var(--space-2); border: 1px solid var(--border); border-radius: var(--r-md); background: var(--raised); box-shadow: var(--shadow-1); }
  .menu button { border: 0; background: transparent; color: var(--text-1); padding: var(--space-1) var(--space-2); text-align: left; cursor: pointer; }
  .menu button:hover { background: var(--accent-soft); }
</style>
