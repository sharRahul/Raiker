<script lang="ts" module>
  import { api } from "../api";

  type Proposal = Awaited<ReturnType<typeof api.memoryProposals>>[number];

  /*
   * One read serves every answer on screen: a conversation with forty turns
   * asks once, not forty times. Kept for a few seconds, so a proposal the
   * observer files just after the answer finishes is found on the next look.
   */
  let held: { at: number; read: Promise<Proposal[]> } | null = null;
  const HOLD_MS = 3_000;

  export function readProposals(now = Date.now()): Promise<Proposal[]> {
    if (held === null || now - held.at > HOLD_MS) {
      held = { at: now, read: api.memoryProposals().catch(() => [] as Proposal[]) };
    }
    return held.read;
  }

  export function forgetHeldProposals(): void {
    held = null;
  }
</script>

<script lang="ts">
  /**
   * RU-10 — a memory Raiker proposed from this answer, kept or skipped where
   * the answer is. Nothing is stored until **Keep**, exactly as in
   * Memory › Suggestions, through the same decision route and its rules;
   * **Not this** rejects it. Batch review stays in Memory.
   */
  import { onMount } from "svelte";
  import { failure } from "../errorCopy";

  let { sessionId, turnId }: { sessionId: string; turnId: string } = $props();

  let proposals = $state<Proposal[]>([]);
  let decided = $state<Record<string, "kept" | "skipped">>({});
  let busy = $state<string | null>(null);
  let problem = $state<string | null>(null);

  onMount(() => {
    let live = true;
    const look = async (): Promise<void> => {
      const all = await readProposals();
      if (!live) return;
      proposals = all.filter(
        (item) => item.source_session_id === sessionId && item.source_turn_id === turnId && item.decision === "deferred",
      );
    };
    void look();
    // The observer files its proposal after the turn ends; look once more.
    const again = setTimeout(() => void look(), HOLD_MS + 500);
    return () => {
      live = false;
      clearTimeout(again);
    };
  });

  async function decide(item: Proposal, decision: "approved" | "rejected"): Promise<void> {
    busy = item.candidate_id;
    problem = null;
    try {
      await api.decideMemoryProposal(item.candidate_id, { decision, expected_decision: "deferred" });
      decided = { ...decided, [item.candidate_id]: decision === "approved" ? "kept" : "skipped" };
      forgetHeldProposals();
    } catch (error) {
      problem = failure(
        decision === "approved" ? "It was not kept" : "It was not skipped",
        "Nothing changed.",
        "Try again, or decide in Memory › Suggestions.",
        error,
      );
    } finally {
      busy = null;
    }
  }
</script>

{#each proposals as item (item.candidate_id)}
  {#if decided[item.candidate_id] === "kept"}
    <p class="proposal" role="status">Kept. <a href="#/memory?tab=memories">Open Memory</a></p>
  {:else if decided[item.candidate_id] !== "skipped"}
    <div class="proposal" role="group" aria-label="Memory Raiker proposed from this answer">
      <span>Remember: <strong>“{item.text}”</strong></span>
      <button
        type="button"
        class="btn btn-soft btn-sm"
        disabled={busy !== null}
        onclick={() => void decide(item, "approved")}>{busy === item.candidate_id ? "Saving…" : "Keep"}</button
      >
      <button type="button" class="btn btn-ghost btn-sm" disabled={busy !== null} onclick={() => void decide(item, "rejected")}
        >Not this</button
      >
    </div>
  {/if}
{/each}
{#if problem}<p class="problem" role="alert">{problem}</p>{/if}

<style>
  .proposal{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap;margin:var(--space-2) 0 0;font-size:var(--text-sm);color:var(--text-2)}
  .proposal strong{color:var(--text-1);font-weight:600;overflow-wrap:anywhere}
  .problem{margin:var(--space-1) 0 0;color:var(--danger);font-size:var(--text-xs)}
</style>
