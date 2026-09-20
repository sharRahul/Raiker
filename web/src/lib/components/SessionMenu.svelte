<script lang="ts">
  /**
   * What the evidence inspector may do to a conversation.
   *
   * BUG-303 — this used to be the whole conversation library: rename, move to a
   * project, pin, archive. Those are how somebody organises the chats they work
   * in, and they were on the page whose job is *audit*, while Threads — the page
   * work is resumed from — could not express any of them. They live on Threads
   * now.
   *
   * **Delete** stayed, deliberately. It removes the audit record — the turns and
   * the governed events — and it belongs beside the evidence it removes rather
   * than in a library where "tidy this away" is what Archive means. Copying the
   * link stayed too: it is a way of citing this record, not a way of filing it.
   *
   * **Found live on 2026-09-20, while capturing BUG-303's evidence.** The menu
   * was absolutely positioned inside the session table, and the table's card
   * scrolls horizontally on a narrow window — `overflow-x: auto`, which the
   * browser resolves to `overflow-y: auto` as well. On a workspace with one
   * conversation the menu opened 131 pixels below the bottom of that card and
   * was simply cut off, so **Delete**, the only destructive control on the
   * page, was unreachable. It is positioned against the viewport now, measured
   * from the trigger, which no ancestor can clip.
   */
  import { isLoopbackHost } from "../loopback";
  import { conversationLink, workModeRoute } from "../turnAnchor";

  let {
    sessionId, title, origin = "chat", onDelete,
  }: {
    sessionId: string; title: string;
    /** REM-THREAD-03 — which surface owns this conversation, so the copied
     *  link opens where the work was done. It used to be Chat for every
     *  session, including a Build one. */
    origin?: string;
    onDelete: () => void;
  } = $props();
  let open = $state(false);
  let triggerEl: HTMLButtonElement | undefined = $state();
  /** Where the menu sits in the viewport, measured from the trigger on open. */
  let anchor = $state<{ top: number; right: number } | null>(null);

  function place(): void {
    if (!triggerEl) return;
    const box = triggerEl.getBoundingClientRect();
    anchor = { top: box.bottom + 4, right: window.innerWidth - box.right };
  }

  function toggle(): void {
    if (open) {
      open = false;
      return;
    }
    place();
    open = true;
  }

  function close(): void {
    if (!open) return;
    open = false;
  }

  function closeOnEscape(event: KeyboardEvent) {
    if (event.key !== "Escape" || !open) return;
    open = false;
    queueMicrotask(() => triggerEl?.focus());
  }

  async function copyLocalLink() {
    if (!navigator.clipboard || !isLoopbackHost(window.location.hostname)) return;
    await navigator.clipboard.writeText(
      `${window.location.origin}/${conversationLink(workModeRoute(origin), sessionId)}`,
    );
  }
</script>

<div class="wrap">
  <button
    bind:this={triggerEl}
    type="button"
    class="trigger icon-button"
    aria-label={`Session actions for ${title}`}
    aria-expanded={open}
    onclick={toggle}
  >•••</button>
  {#if open}
    <div
      class="menu menu-surface"
      role="menu"
      aria-label={`Actions for ${title}`}
      tabindex="-1"
      onkeydown={closeOnEscape}
      style={anchor ? `top:${anchor.top}px;right:${anchor.right}px` : undefined}
    >
      <button class="menu-item" type="button" role="menuitem" onclick={copyLocalLink}>Copy local link</button>
      <!-- Where the library went, said once rather than left to be discovered. -->
      <a class="menu-item" role="menuitem" href="#/search-chat">Organise in Threads</a>
      <button type="button" role="menuitem" class="menu-item danger" onclick={onDelete}>Delete</button>
    </div>
  {/if}
</div>

<!-- A fixed menu does not travel with the row it belongs to, so the page moving
     under it closes it rather than leaving it pointing at nothing. -->
<svelte:window onscroll={close} onresize={close} />

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
  /* Fixed rather than absolute: an ancestor that scrolls — the session card
     does, so that a wide table can be read on a narrow window — clips an
     absolutely positioned child on both axes, and this menu holds the only
     destructive control on the page. The coordinates come from the trigger. */
  .menu {
    position: fixed;
    right: 0;
    top: 0;
    z-index: var(--z-popover);
    min-width: 11rem;
    display: grid;
    gap: var(--space-1);
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  /* One item is a link now — where the library went — so the styling is on the
     item rather than on the element it happens to be. */
  .menu .menu-item {
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--r-sm);
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }
  .menu .menu-item:hover,
  .menu .menu-item:focus-visible { background: var(--accent-soft); }
  .menu .menu-item.danger { color: var(--danger); }
  .menu .menu-item.danger:hover { background: var(--danger-soft); }
</style>
