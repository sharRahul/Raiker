<script lang="ts">
  /**
   * QUI-F20 — "Remember: Anna prefers short replies?" Save · Dismiss.
   *
   * Offered under the turn that answered a correction. Save files the owner's
   * words as a memory proposal and approves it in the same step, through the
   * route Memory › Suggestions uses, so the same rules apply (secret-like text
   * is refused). Dismiss stores nothing and the offer does not come back for
   * this message.
   */
  import { api } from "../api";
  import { rememberQuestion } from "../corrections";
  import { failure } from "../errorCopy";

  let { sessionId, turnId, text }: { sessionId: string; turnId: string; text: string } = $props();

  let phase = $state<"offer" | "saving" | "saved" | "dismissed">("offer");
  let problem = $state<string | null>(null);

  async function save(): Promise<void> {
    phase = "saving";
    problem = null;
    try {
      const proposed = await api.proposeCorrectionMemory({ text, session_id: sessionId, turn_id: turnId });
      await api.decideMemoryProposal(proposed.candidate_id, { decision: "approved", expected_decision: "deferred" });
      phase = "saved";
    } catch (error) {
      phase = "offer";
      problem = failure("It was not remembered", "Nothing was saved.", "Try again, or add it in Memory.", error);
    }
  }
</script>

{#if phase === "saved"}
  <p class="correction" role="status">Remembered. <a href="#/memory?tab=memories">Open Memory</a></p>
{:else if phase !== "dismissed"}
  <div class="correction" role="group" aria-label="Remember this correction">
    <span>Remember: <strong>{rememberQuestion(text)}</strong></span>
    <button type="button" class="btn btn-soft btn-sm" disabled={phase === "saving"} onclick={() => void save()}
      >{phase === "saving" ? "Saving…" : "Save"}</button
    >
    <button type="button" class="btn btn-ghost btn-sm" disabled={phase === "saving"} onclick={() => (phase = "dismissed")}>Dismiss</button>
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
  </div>
{/if}

<style>
  .correction{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap;margin:var(--space-2) 0 0;font-size:var(--text-sm);color:var(--text-2)}
  .correction strong{color:var(--text-1);font-weight:600}
  .problem{flex-basis:100%;margin:0;color:var(--danger);font-size:var(--text-xs)}
</style>
