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

  type Remembered = Awaited<ReturnType<typeof api.rememberedInSession>>[number];
  const heldRemembered = new Map<string, { at: number; read: Promise<Remembered[]> }>();

  export function readRemembered(sessionId: string, now = Date.now()): Promise<Remembered[]> {
    const current = heldRemembered.get(sessionId);
    if (current === undefined || now - current.at > HOLD_MS) {
      const read = api.rememberedInSession(sessionId).catch(() => [] as Remembered[]);
      heldRemembered.set(sessionId, { at: now, read });
      return read;
    }
    return current.read;
  }

  export function forgetHeldProposals(): void {
    held = null;
    heldRemembered.clear();
  }
</script>

<script lang="ts">
  /**
   * RU-10 — a memory Raiker proposed from this answer, kept or skipped where
   * the answer is. Nothing is stored until **Keep**, exactly as in
   * Memory › Suggestions, through the same decision route and its rules;
   * **Not this** rejects it. Batch review stays in Memory.
   *
   * Most memories are no longer asked about: the owner's own words and
   * evidence-backed lessons are kept as the turn ends and shown here as
   * *Remembered* with **Undo**, which forgets them. Only what the model wrote
   * and personal identifiers still wait for Keep.
   */
  import { onMount } from "svelte";
  import { failure } from "../errorCopy";

  let { sessionId, turnId }: { sessionId: string; turnId: string } = $props();

  let proposals = $state<Proposal[]>([]);
  let remembered = $state<Remembered[]>([]);
  let undone = $state<Record<string, boolean>>({});
  let decided = $state<Record<string, "kept" | "skipped">>({});
  let busy = $state<string | null>(null);
  let problem = $state<string | null>(null);

  onMount(() => {
    let live = true;
    const look = async (): Promise<void> => {
      const [all, kept] = await Promise.all([readProposals(), readRemembered(sessionId)]);
      if (!live) return;
      remembered = kept.filter((item) => item.source_turn_id === turnId);
      proposals = all.filter(
        (item) =>
          item.source_session_id === sessionId &&
          item.source_turn_id === turnId &&
          item.decision === "deferred" &&
          // Only the owner's own words are offered here. A sentence the model
          // wrote may be invented; it waits in Memory › Suggestions, marked as
          // Raiker's, for a deliberate review.
          item.source_role !== "assistant",
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

  async function undo(item: Remembered): Promise<void> {
    busy = item.memory_id;
    problem = null;
    try {
      await api.forgetMemory(item.memory_id);
      undone = { ...undone, [item.memory_id]: true };
      forgetHeldProposals();
    } catch (error) {
      problem = failure("It was not undone", "Raiker still remembers it.", "Try again, or forget it in Memory.", error);
    } finally {
      busy = null;
    }
  }

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

{#each remembered as item (item.memory_id)}
  {#if undone[item.memory_id]}
    <p class="proposal" role="status">Forgotten.</p>
  {:else}
    <div class="proposal" role="group" aria-label="Memory Raiker kept from this answer">
      <span>{item.memory_type === "lesson" ? "Learned for this project" : "Remembered"}: <strong>“{item.text}”</strong></span>
      <button type="button" class="btn btn-ghost btn-sm" disabled={busy !== null} onclick={() => void undo(item)}
        >{busy === item.memory_id ? "Undoing…" : "Undo"}</button
      >
    </div>
  {/if}
{/each}
{#each proposals as item (item.candidate_id)}
  {#if decided[item.candidate_id] === "kept"}
    <p class="proposal" role="status">Kept. <a href="#/memory?tab=memories">Open Memory</a></p>
  {:else if decided[item.candidate_id] !== "skipped"}
    <div class="proposal" role="group" aria-label="Memory Raiker proposed from this answer">
      <!-- RU-12 — a lesson comes from this task's own command records, not the model's prose. -->
      <span>{item.memory_type === "check_fix" ? "Fix this project's check" : item.source_role === "raiker_lesson" ? "Lesson for this project" : "Remember"}: <strong>“{item.text}”</strong></span>
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
