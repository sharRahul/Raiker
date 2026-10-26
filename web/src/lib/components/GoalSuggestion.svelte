<script lang="ts">
  /**
   * QUI-F03 — goals noticed in conversation.
   *
   * When this conversation's latest request is an aim that also came up in
   * another conversation, offer once: *This looks like an ongoing goal. Track
   * it?* The server decides (`GET /api/goals/suggestion`, local, no model);
   * this only draws the offer. **Track it** opens the Goals form filled in,
   * where nothing is saved until Save. **Not now** is remembered as the aim, so
   * it is never offered again, here or in another conversation.
   *
   * Asked again whenever `revision` changes (a turn finished), so the offer can
   * appear under the answer that made the pattern, never in the middle of one.
   */
  import Icon from "./Icon.svelte";
  import { contract } from "../generated/apiContract";
  import type { GoalSuggestionView } from "../generated/apiContract";

  let {
    sessionId,
    revision,
    ontrack,
  }: {
    sessionId: string;
    /** Changes when a turn settles; the check runs again then. */
    revision: number;
    ontrack: (suggestion: GoalSuggestionView) => void;
  } = $props();

  let suggestion = $state<GoalSuggestionView | null>(null);
  let dismissing = $state(false);

  $effect(() => {
    const id = sessionId;
    void revision;
    suggestion = null;
    void contract
      .goalSuggestion({ session_id: id })
      .then((answer) => {
        if (id === sessionId) suggestion = answer.suggestion;
      })
      .catch(() => {
        // An offer is a convenience. Without one the conversation is unchanged.
        suggestion = null;
      });
  });

  async function notNow() {
    if (suggestion === null) return;
    dismissing = true;
    try {
      await contract.dismissGoalSuggestion({ keywords: suggestion.keywords });
      suggestion = null;
    } catch {
      // Left on screen: the owner can press it again. Hiding it would pretend
      // the dismissal was kept when it was not.
    } finally {
      dismissing = false;
    }
  }

  const elsewhere = $derived(
    suggestion === null
      ? ""
      : suggestion.session_titles.length === 1
        ? `It also came up in “${suggestion.session_titles[0]}”.`
        : `It also came up in ${suggestion.session_titles.length} other conversations.`,
  );
</script>

{#if suggestion !== null}
  <aside class="goal-offer" aria-label="Suggested goal">
    <span class="mark" aria-hidden="true"><Icon name="goal" size="md" /></span>
    <div class="text">
      <p class="lead">This looks like an ongoing goal. Track it?</p>
      <p class="detail">{elsewhere} Tracked goals live in Work › Goals with their next step.</p>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-ghost btn-sm" disabled={dismissing} onclick={() => void notNow()}>Not now</button>
      <button type="button" class="btn btn-soft btn-sm" onclick={() => suggestion && ontrack(suggestion)}>Track it</button>
    </div>
  </aside>
{/if}

<style>
  .goal-offer {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    margin: var(--space-3) 0;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
  }
  .mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: var(--r-pill);
    background: var(--accent-soft);
    color: var(--accent-strong);
  }
  .text { min-width: 0; }
  .lead {
    margin: 0;
    font-weight: 600;
    color: var(--text-1);
  }
  .detail {
    margin: 0.1rem 0 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .actions {
    display: flex;
    gap: var(--space-1);
  }
  @media (max-width: 720px) {
    .goal-offer { grid-template-columns: auto minmax(0, 1fr); }
    .actions { grid-column: 1 / -1; justify-content: flex-end; }
  }
</style>
