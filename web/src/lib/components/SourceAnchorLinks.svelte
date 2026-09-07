<script lang="ts">
  /**
   * BUG-245 — the exchanges a cited search returned, as links that open one.
   *
   * `conversation_search` became a citable source in FIXED-317 and a turn
   * coordinate became openable in FIXED-316. The two did not meet: opening a
   * **Past conversations** chip showed each exchange's conversation title and
   * date above its text — which is what made the citation checkable at all —
   * and the exchanges were text, so verifying one still meant retyping the
   * title into chat search.
   *
   * One component for both readers, because Chat opens a source in the file
   * inspector and Build opens it beside the answer. Two copies of a link list
   * is two places for the route to go stale.
   *
   * The coordinates are the runtime's, not the model's: they are built from the
   * tool result the runtime read and stored in a column of their own, never
   * written into the passage as markup — the passage is rendered escape-first,
   * and keeping it so is the one property that stops a source's text from being
   * able to say more than it is.
   */
  import Icon from "./Icon.svelte";
  import { conversationLink } from "../turnAnchor";
  import type { SourceAnchorView } from "../apiTypes";

  let { anchors }: { anchors: SourceAnchorView[] } = $props();

  /** The conversation, and when it happened — the two things that identify it. */
  function label(anchor: SourceAnchorView): string {
    const title = anchor.title.trim() || "Untitled conversation";
    const day = anchor.created_at.slice(0, 10);
    return day ? `${title} · ${day}` : title;
  }
</script>

{#if anchors.length > 0}
  <nav class="anchors" aria-label="Exchanges this search returned">
    <p class="lede">Open one of these exchanges:</p>
    <ul>
      {#each anchors as anchor (`${anchor.session_id}:${anchor.turn_id}`)}
        <li>
          <!-- A Build conversation opens in Build. The right coordinate in the
               wrong room is still the wrong answer. -->
          <a
            href={conversationLink(
              anchor.origin === "build" ? "build" : "new-chat",
              anchor.session_id,
              anchor.turn_id,
            )}
          >
            <Icon name="chat" size="sm" />
            <span>{label(anchor)}</span>
          </a>
        </li>
      {/each}
    </ul>
  </nav>
{/if}

<style>
  /* Every box in here is width-constrained on purpose. A label with
     `white-space: nowrap` and no cap contributes its *whole* text to the
     min-content width of whatever contains it, which pushed the inspector's
     grid column wider than the pane and clipped the passage beside it. The
     ellipsis is the point of the nowrap; the cap is what makes it reachable. */
  .anchors {
    margin-top: var(--space-2);
    min-width: 0;
    max-width: 100%;
  }
  .lede {
    margin: 0 0 0.25rem;
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }
  li {
    min-width: 0;
    max-width: 100%;
  }
  a {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
    max-width: 100%;
    padding: 0.15rem 0.35rem;
    border-radius: var(--r-sm);
    font-size: var(--text-xs);
    color: var(--accent);
    text-decoration: none;
  }
  a:hover,
  a:focus-visible {
    background: var(--surface);
    text-decoration: underline;
  }
  a span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
