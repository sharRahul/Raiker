<script lang="ts">
  /**
   * QUI-P05 — the approval card ("Raiker Safety"), where the conversation parked.
   *
   * Drawn by the app from the approval record, never from a model's message,
   * and styled unlike any message: a model's text goes through the Markdown
   * renderer, which cannot produce this element or its `data-raiker-safety`
   * mark (see `Markdown.test.ts`). Answering here clears the same decision in
   * the top bar's count, the floating card and the Approvals queue, because
   * every one of them reads the same record and hears the same announcement.
   *
   * What it never offers: "Always allow". **Allow for this task** waits for
   * limits the runtime can enforce (QUI-P03), so it is not shown yet. A
   * critical action keeps its password-or-code ceremony in Approvals.
   *
   * QUI-P06 — an approval nobody answered within the owner's time limit is
   * past deciding. The task did not proceed and does not proceed on its own;
   * the card says so and offers **Ask again**, which asks the same request
   * again as a new turn.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type { ApprovalDetailView, ApprovalInfo } from "../apiTypes";
  import { publishApprovalResolved } from "../approvalResume";
  import { safetyRows } from "../approvalSafety";
  import {
    APPROVAL_TIMEOUT_ROUTE,
    approvalTimeoutLabel,
    approvalTimeoutMinutes,
  } from "../approvalTimeout";
  import { humanize } from "../format";
  import { shownInline } from "../inlineDecisions.svelte";
  import Icon from "./Icon.svelte";

  let {
    approval,
    sessionId = null,
    disabled = false,
    onDecided,
    onAskAgain,
    onExpired,
  }: {
    approval: ApprovalInfo;
    sessionId?: string | null;
    /** A turn is streaming, so nothing here may start another. */
    disabled?: boolean;
    /** The decision was recorded; `resumable` says whether a parked turn can continue. */
    onDecided?: (approved: boolean, resumable: boolean) => void;
    /** Ask the same request again, as a new turn. */
    onAskAgain?: () => void;
    /**
     * The approval expired with no decision, so the call it parked will not
     * run. Given the call's action id from the approval's own record, because a
     * reopened conversation's parked approval does not carry one.
     */
    onExpired?: (actionId: string) => void;
  } = $props();

  let detail = $state<ApprovalDetailView | null>(null);
  let sideEffect = $state<string | null>(null);
  let expired = $state(false);
  let timeLimit = $state<number | null>(null);
  let busy = $state(false);
  let failure = $state<string | null>(null);

  const critical = $derived(detail?.approval.critical ?? false);
  const settled = $derived(detail !== null && detail.approval.status !== "pending");
  // Only while it can still be decided here: an expired or critical card has
  // no Change to point at.
  const changeable = $derived(
    detail !== null &&
      !expired &&
      !detail.approval.critical &&
      detail.approval.status === "pending" &&
      (detail.preview_kind === "patch" || detail.preview_kind === "file_diff"),
  );
  const rows = $derived(
    safetyRows({
      toolTitle: humanize(approval.tool_name),
      message: approval.message ?? "",
      expectedEffect: approval.expected_effect ?? "",
      capability: detail?.approval.capability ?? null,
      sideEffect,
      reasons: approval.reasons ?? [],
      arguments: approval.arguments,
      changeable,
    }),
  );
  const changeHref = $derived(`#/approvals?item=${encodeURIComponent(approval.approval_id)}`);

  async function readTimeLimit() {
    try {
      timeLimit = approvalTimeoutMinutes((await api.settings()).settings);
    } catch {
      timeLimit = null;
    }
  }

  onMount(() => {
    void (async () => {
      try {
        detail = await api.approval(approval.approval_id);
      } catch {
        // The card still says what the proposal names; the decision is checked
        // again by the server when it is made.
        return;
      }
      expired = detail.approval.is_expired || detail.approval.status === "expired";
      if (expired) {
        void readTimeLimit();
        onExpired?.(detail.approval.action_id || approval.action_id);
      }
      try {
        sideEffect = (await api.capabilityGate(detail.approval.capability)).side_effect || null;
      } catch {
        sideEffect = null;
      }
    })();
  });

  async function decide(approve: boolean) {
    if (busy || disabled) return;
    busy = true;
    failure = null;
    try {
      const result = await api.resolveApproval(approval.approval_id, {
        approve,
        reason: approve ? "allowed once in the conversation" : "declined in the conversation",
      });
      publishApprovalResolved({
        approvalId: result.approval_id,
        sessionId: result.resume?.session_id ?? sessionId,
        turnId: result.resume?.turn_id ?? null,
        approved: approve,
      });
      onDecided?.(approve, result.resume?.resumable ?? false);
    } catch (error) {
      if (error instanceof ApiError && error.reasonCode === "approval_expired") {
        expired = true;
        void readTimeLimit();
        onExpired?.(detail?.approval.action_id || approval.action_id);
      } else if (error instanceof ApiError && error.reasonCode === "approval_already_resolved") {
        failure = "This was already decided somewhere else. The conversation continues from that decision.";
      } else {
        failure = "That decision was not recorded. Nothing ran. Try again, or decide in Approvals.";
      }
    } finally {
      busy = false;
    }
  }
</script>

<section
  class="safety-card"
  class:expired
  data-raiker-safety="approval"
  aria-label="Raiker Safety"
  use:shownInline={approval.approval_id}
>
  <header>
    <Icon name="shield" size="sm" />
    <strong class="brand">Raiker Safety</strong>
    {#if (approval.queue_total ?? 1) > 1}
      <span class="batch">Decision {approval.queue_position} of {approval.queue_total}</span>
    {/if}
    {#if expired}
      <span class="status" role="status">Not done: no decision</span>
    {:else if settled}
      <span class="status" role="status">Decided</span>
    {:else}
      <span class="status" role="status" aria-live="polite">Waiting for your decision</span>
    {/if}
  </header>

  <dl class="rows">
    {#each rows as row (row.key)}
      <div data-testid={`safety-${row.key}`}>
        <dt>{row.label}</dt>
        <dd>{row.value}</dd>
      </div>
    {/each}
  </dl>

  {#if expired}
    <p class="note">
      Nobody answered within {timeLimit === null ? "the time limit" : approvalTimeoutLabel(timeLimit)}, so
      nothing ran and the task stopped here.
      <a href={APPROVAL_TIMEOUT_ROUTE}>Change the time limit</a>
    </p>
    {#if onAskAgain}
      <div class="actions">
        <button type="button" class="btn btn-primary btn-sm" {disabled} onclick={() => onAskAgain?.()}>
          Ask again
        </button>
      </div>
    {/if}
  {:else if critical}
    <p class="note">This one needs your password or a code, so it is decided in Approvals.</p>
    <div class="actions">
      <a class="btn btn-primary btn-sm" href={changeHref}>Review in Approvals</a>
    </div>
  {:else if !settled}
    {#if failure}<p class="note failure" role="alert">{failure}</p>{/if}
    <div class="actions">
      <button type="button" class="btn btn-sm" disabled={busy || disabled} onclick={() => void decide(false)}>
        Decline
      </button>
      <a class="btn btn-ghost btn-sm" href={changeHref}>Change</a>
      <button
        type="button"
        class="btn btn-primary btn-sm allow"
        disabled={busy || disabled}
        onclick={() => void decide(true)}
      >
        <Icon name="check" size="sm" /> Allow once
      </button>
    </div>
  {/if}
</section>

<style>
  /* Not a message: no bubble, no avatar, a fixed frame in the attention colour
     with the app's own name on it. */
  .safety-card {
    margin-top: 0.65rem;
    display: grid;
    gap: 0.55rem;
    border: 1px solid var(--warn-border);
    border-radius: var(--r-sm);
    background: var(--surface);
    padding: 0.7rem 0.9rem 0.8rem;
    max-width: 680px;
  }
  .safety-card.expired {
    border-color: var(--border-strong);
    border-color: var(--neutral-border, var(--border));
  }
  header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--text-sm);
    color: var(--warn-text, var(--warn));
  }
  .safety-card.expired header {
    color: var(--text-2);
  }
  .brand {
    font-weight: 700;
    letter-spacing: 0.01em;
  }
  .batch {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .status {
    margin-left: auto;
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .rows {
    display: grid;
    gap: 0.3rem;
    margin: 0;
  }
  .rows div {
    display: grid;
    grid-template-columns: 9rem minmax(0, 1fr);
    gap: 0.6rem;
    font-size: var(--text-sm);
  }
  dt {
    color: var(--text-3);
  }
  dd {
    margin: 0;
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .note {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-2);
  }
  .note.failure {
    color: var(--danger);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .actions .allow {
    margin-left: auto;
  }
</style>
