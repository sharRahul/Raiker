<script lang="ts">
  /**
   * The decision, where the owner is standing.
   *
   * An approval could only be answered in two places: inline in the Chat turn
   * that raised it, or in the Approvals inbox. Both require already being
   * there. A task running in the background, a standing agent, or a turn in a
   * conversation the owner has navigated away from raised a decision that
   * nothing on screen mentioned — so work sat parked until somebody thought to
   * open the inbox.
   *
   * This is the missing surface: whatever page is open, a pending decision
   * announces itself and can be answered in place. It is deliberately *not*
   * modal — Raiker does not seize the screen — and "Later" is a first-class
   * answer that leaves the approval exactly where it was, in the inbox.
   *
   * Two decisions are never taken here, both on purpose:
   *
   * * A **critical** approval needs the owner's password or MFA code. That
   *   ceremony belongs in the inbox, so this card links there and says why.
   * * The **Approvals page itself** already lists everything, so the card stays
   *   out of the way while the owner is on it.
   */
  import { onDestroy } from "svelte";
  import { api, ApiError, hasToken } from "../api";
  import { publishApprovalResolved, subscribeApprovalResolved } from "../approvalResume";
  import type { ApprovalView } from "../apiTypes";
  import { capabilityLabel } from "../capabilityModel";
  import { humanize } from "../format";
  import Icon from "./Icon.svelte";

  /** How often pending approvals are re-read while the tab is visible. */
  const POLL_MS = 5000;

  let pending = $state<ApprovalView[]>([]);
  let deferred = $state<string[]>([]);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;

  const onApprovals = $derived(
    typeof window !== "undefined" && window.location.hash.startsWith("#/approvals"),
  );
  const queue = $derived(pending.filter((item) => !deferred.includes(item.approval_id)));
  const current = $derived(queue[0] ?? null);

  async function poll() {
    if (!hasToken()) return;
    try {
      pending = await api.approvals("pending");
    } catch {
      // A read that fails changes nothing on screen: the inbox is still there,
      // and the next tick tries again.
    }
  }

  function schedule() {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(async () => {
      if (typeof document === "undefined" || !document.hidden) await poll();
      schedule();
    }, POLL_MS);
  }

  async function decide(approve: boolean) {
    if (current === null || busy) return;
    busy = true;
    failure = null;
    const approvalId = current.approval_id;
    const sessionId = current.session_id;
    try {
      const result = await api.resolveApproval(approvalId, {
        approve,
        reason: approve ? "approved from the prompt" : "denied from the prompt",
      });
      // The turn this parked is very often in a Chat tab that is still open, so
      // the same broadcast the inbox sends is sent here: that tab continues
      // without the owner going back to it.
      publishApprovalResolved({
        approvalId: result.approval_id,
        sessionId: result.resume?.session_id ?? sessionId ?? null,
        turnId: result.resume?.turn_id ?? null,
        approved: approve,
      });
      pending = pending.filter((item) => item.approval_id !== approvalId);
      await poll();
    } catch (error) {
      failure =
        error instanceof ApiError && error.reasonCode
          ? `That decision was not accepted (${error.reasonCode}).`
          : "That decision was not accepted.";
    } finally {
      busy = false;
    }
  }

  function later() {
    if (current === null) return;
    deferred = [...deferred, current.approval_id];
    failure = null;
  }

  function review() {
    window.location.hash = "#/approvals";
  }

  $effect(() => {
    void poll();
    schedule();
  });

  // A decision made in another tab removes this card without waiting for the
  // next poll.
  const unsubscribe = subscribeApprovalResolved((message) => {
    pending = pending.filter((item) => item.approval_id !== message.approvalId);
  });

  onDestroy(() => {
    if (timer !== null) clearTimeout(timer);
    unsubscribe();
  });
</script>

{#if current !== null && !onApprovals}
  <section class="approval-prompt" aria-label="Approval needed">
    <header>
      <Icon name="shield" size={15} />
      <strong>Approval needed</strong>
      {#if queue.length > 1}<span class="more">{queue.length - 1} more</span>{/if}
      <button type="button" class="dismiss" aria-label="Decide later" onclick={later}>
        <Icon name="x" size={14} />
      </button>
    </header>
    <p class="what">
      <strong>{humanize(current.tool_name)}</strong>
      <span>{capabilityLabel(current.capability)}</span>
    </p>
    {#if current.critical}
      <p class="note">This one needs your password or a code.</p>
      <div class="actions"><button type="button" class="primary" onclick={review}>Review</button></div>
    {:else}
      {#if failure}<p class="note" role="alert">{failure}</p>{/if}
      <div class="actions">
        <button type="button" class="primary" disabled={busy} onclick={() => void decide(true)}>
          <Icon name="check" size={14} /> Approve
        </button>
        <button type="button" disabled={busy} onclick={() => void decide(false)}>Deny</button>
        <button type="button" class="quiet" onclick={review}>Details</button>
      </div>
    {/if}
  </section>
{/if}

<style>
  .approval-prompt {
    position: fixed;
    right: 20px;
    bottom: 18px;
    z-index: 46;
    width: min(21rem, calc(100vw - 40px));
    display: grid;
    gap: 0.5rem;
    padding: 0.72rem 0.8rem;
    border: 1px solid var(--warn-border, var(--neutral-border));
    border-radius: var(--r-md);
    background: var(--surface);
    color: var(--text-2);
    box-shadow: 0 10px 30px rgb(0 0 0 / 18%);
  }
  header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--text-1);
    font-size: 0.78rem;
  }
  .more {
    color: var(--text-3);
    font-size: 0.7rem;
  }
  .dismiss {
    margin-left: auto;
    border: 0;
    background: transparent;
    color: var(--text-3);
    cursor: pointer;
    padding: 0.1rem;
  }
  .what {
    margin: 0;
    display: grid;
    gap: 0.1rem;
    font-size: 0.76rem;
  }
  .what strong {
    color: var(--text-1);
  }
  .what span {
    color: var(--text-3);
    font-size: 0.72rem;
  }
  .note {
    margin: 0;
    color: var(--text-3);
    font-size: 0.72rem;
  }
  .actions {
    display: flex;
    gap: 0.4rem;
  }
  button {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-pill);
    padding: 0.3rem 0.66rem;
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: 0.74rem;
    font-weight: 650;
    cursor: pointer;
  }
  button:disabled {
    cursor: wait;
    opacity: 0.6;
  }
  .primary {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }
  .quiet {
    margin-left: auto;
    border-color: transparent;
    color: var(--text-3);
  }
</style>
