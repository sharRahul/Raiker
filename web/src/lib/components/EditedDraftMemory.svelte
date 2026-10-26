<script lang="ts">
  /**
   * QUI-F20 — a correction made by editing Raiker's draft.
   *
   * When the owner rewrites a change Raiker proposed, the edit says *what* they
   * wanted but not *why*, and Raiker will not guess a lesson from a diff. So it
   * asks, once, for the owner's own words ("Keep commit messages under fifty
   * characters"). Save files those words through the same proposal and decision
   * Memory › Suggestions uses, so secret-like text is still refused; Dismiss
   * keeps nothing. Nothing is offered when there is no conversation to file it
   * against.
   */
  import { api } from "../api";
  import { failure } from "../errorCopy";

  let { sessionId, ondone }: { sessionId: string; ondone?: () => void } = $props();

  let text = $state("");
  let phase = $state<"offer" | "saving" | "saved" | "dismissed">("offer");
  let problem = $state<string | null>(null);

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const words = text.trim();
    if (words === "") return;
    phase = "saving";
    problem = null;
    try {
      const proposed = await api.proposeCorrectionMemory({ text: words, session_id: sessionId });
      await api.decideMemoryProposal(proposed.candidate_id, { decision: "approved", expected_decision: "deferred" });
      phase = "saved";
    } catch (error) {
      phase = "offer";
      problem = failure("It was not remembered", "Nothing was saved.", "Try again, or add it in Memory.", error);
    }
  }

  function dismiss() {
    phase = "dismissed";
    ondone?.();
  }
</script>

{#if phase === "saved"}
  <p class="edited saved" role="status">Remembered. <a href="#/memory?tab=memories">Open Memory</a></p>
{:else if phase !== "dismissed"}
  <form class="edited" aria-label="Remember why you changed it" onsubmit={save}>
    <label for={`edited-${sessionId}`}>You changed Raiker's draft. Anything to remember for next time?</label>
    <div class="row">
      <input
        id={`edited-${sessionId}`}
        class="input"
        bind:value={text}
        maxlength="300"
        placeholder="Keep commit messages under fifty characters"
        disabled={phase === "saving"}
      />
      <button type="submit" class="btn btn-soft btn-sm" disabled={phase === "saving" || text.trim() === ""}>
        {phase === "saving" ? "Saving…" : "Save"}
      </button>
      <button type="button" class="btn btn-ghost btn-sm" disabled={phase === "saving"} onclick={dismiss}>Dismiss</button>
    </div>
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
  </form>
{/if}

<style>
  .edited {
    display: grid;
    gap: var(--space-1);
    margin: 0 0 var(--space-3);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .edited.saved { display: flex; gap: var(--space-2); align-items: center; }
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }
  .row .input { flex: 1 1 18rem; min-width: 0; }
  .problem { margin: 0; color: var(--danger); font-size: var(--text-xs); }
</style>
