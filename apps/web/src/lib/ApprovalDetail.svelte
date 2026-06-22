<script lang="ts">
  import Badge from "./Badge.svelte";
  import MetadataOnlyBanner from "./MetadataOnlyBanner.svelte";
  import { api, ApiError } from "./api";
  import type { ApprovalDetailView } from "./apiTypes";
  import { explainReasonCode } from "./reasonCodes";

  let { approvalId, onResolved }: { approvalId: string; onResolved: () => void } = $props();

  let detail = $state<ApprovalDetailView | null>(null);
  let loadError = $state<string | null>(null);
  let reason = $state("");
  let submitting = $state(false);
  let resolveError = $state<string | null>(null);
  let resolvedAs = $state<string | null>(null);

  const argEntries = $derived(detail ? Object.entries(detail.arguments) : []);
  const reasonMissing = $derived(reason.trim() === "");

  async function load() {
    detail = null;
    loadError = null;
    resolvedAs = null;
    try {
      detail = await api.approval(approvalId);
    } catch (e) {
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function resolve(approve: boolean) {
    if (reasonMissing || submitting) return;
    submitting = true;
    resolveError = null;
    try {
      const result = await api.resolveApproval(approvalId, { approve, reason: reason.trim() });
      resolvedAs = result.status;
      onResolved();
    } catch (e) {
      if (e instanceof ApiError) {
        const explained = explainReasonCode(e.reasonCode);
        resolveError = explained ? explained.plain : `Could not resolve (${e.status}).`;
      } else {
        resolveError = "Could not resolve.";
      }
    } finally {
      submitting = false;
    }
  }

  function formatArg(v: unknown): string {
    return typeof v === "string" ? v : JSON.stringify(v);
  }

  $effect(() => {
    // Reload whenever the selected approval changes.
    void approvalId;
    void load();
  });
</script>

<section class="detail" aria-label="Approval detail">
  {#if loadError}
    <p class="state-error">Approval unavailable: {loadError}</p>
  {:else if detail === null}
    <p class="state-loading">Loading approval…</p>
  {:else}
    <header class="detail-head">
      <h2>
        <code>{detail.approval.tool_name}</code>
        <span class="cap">{detail.approval.capability}</span>
      </h2>
      <div class="detail-badges">
        <Badge variant="approval-required" />
        <span class="risk" class:risk-high={detail.approval.risk_level === "high"}>
          Risk: {detail.approval.risk_level || "—"}
        </span>
      </div>
    </header>

    <MetadataOnlyBanner />

    <div class="block">
      <h3>Proposed arguments (preview)</h3>
      {#if argEntries.length === 0}
        <p class="muted">No arguments.</p>
      {:else}
        <dl class="args">
          {#each argEntries as [key, value] (key)}
            <dt>{key}</dt>
            <dd><code>{formatArg(value)}</code></dd>
          {/each}
        </dl>
      {/if}
    </div>

    {#if detail.preview_kind === "file_diff" && detail.diff}
      <div class="block">
        <h3>Diff{detail.diff_path ? ` — ${detail.diff_path}` : ""}</h3>
        <pre class="diff">{detail.diff}</pre>
      </div>
    {:else if detail.preview_kind === "patch" && detail.diff}
      <div class="block">
        <h3>Patch{detail.diff_path ? ` — ${detail.diff_path}` : ""}</h3>
        <pre class="diff">{detail.diff}</pre>
      </div>
    {/if}

    {#if resolvedAs}
      <p class="resolved" role="status">
        Recorded decision: <strong>{resolvedAs}</strong>. No action was executed.
      </p>
    {:else}
      <div class="block resolve">
        <h3>Decision</h3>
        <label for="resolve-reason">Reason (required)</label>
        <textarea
          id="resolve-reason"
          bind:value={reason}
          rows="2"
          placeholder="Why are you approving or denying this?"
          disabled={submitting}
        ></textarea>
        {#if resolveError}
          <p class="state-error" role="alert">{resolveError}</p>
        {/if}
        <div class="actions">
          <button
            type="button"
            class="deny"
            disabled={reasonMissing || submitting}
            onclick={() => resolve(false)}
          >
            Deny
          </button>
          <button
            type="button"
            class="approve"
            disabled={reasonMissing || submitting}
            onclick={() => resolve(true)}
          >
            Approve (records decision only)
          </button>
        </div>
        {#if reasonMissing}
          <p class="muted hint">A reason is required before you can record a decision.</p>
        {/if}
      </div>
    {/if}
  {/if}
</section>

<style>
  .detail {
    border: 1px solid #2a2a2e;
    border-radius: 10px;
    background: #101013;
    padding: 1rem 1.25rem;
  }
  .detail-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .detail-head h2 {
    margin: 0;
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .cap {
    font-size: 0.72rem;
    color: #8b8b93;
    font-family: ui-monospace, monospace;
  }
  .detail-badges {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .risk {
    font-size: 0.75rem;
    border: 1px solid #4a4a52;
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
    color: #d0d0d6;
  }
  .risk-high {
    border-color: #8a2f2f;
    color: #ef9a9a;
  }
  .block {
    margin-top: 0.8rem;
  }
  .block h3 {
    margin: 0 0 0.35rem;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #8b8b93;
  }
  .args {
    margin: 0;
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.2rem 0.75rem;
    font-size: 0.84rem;
  }
  .args dt {
    color: #9a9aa2;
  }
  .args dd {
    margin: 0;
  }
  code {
    font-family: ui-monospace, monospace;
    color: #cdd6e0;
  }
  .diff {
    background: #0e0e11;
    border: 1px solid #33333a;
    border-radius: 6px;
    padding: 0.5rem 0.6rem;
    font-size: 0.78rem;
    color: #cdd6e0;
    max-height: 20rem;
    overflow: auto;
    white-space: pre-wrap;
  }
  .resolve label {
    display: block;
    font-size: 0.78rem;
    color: #b0b0b6;
    margin-bottom: 0.25rem;
  }
  .resolve textarea {
    width: 100%;
    box-sizing: border-box;
    background: #0e0e11;
    border: 1px solid #33333a;
    color: #d6d6dc;
    border-radius: 6px;
    padding: 0.5rem 0.6rem;
    font: inherit;
    resize: vertical;
  }
  .resolve textarea:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
    margin-top: 0.6rem;
  }
  .actions button {
    padding: 0.4rem 0.9rem;
    border-radius: 6px;
    border: 1px solid #4a4a52;
    background: #1f1f25;
    color: #d4d4da;
    cursor: pointer;
    font-weight: 600;
  }
  .actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .actions button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  .actions .approve {
    border-color: #2f7d3a;
    color: #9be0a8;
  }
  .actions .deny {
    border-color: #8a2f2f;
    color: #ef9a9a;
  }
  .resolved {
    margin-top: 0.8rem;
    color: #9be0a8;
    font-size: 0.88rem;
  }
  .muted {
    color: #8b8b93;
    font-size: 0.8rem;
  }
  .hint {
    margin: 0.35rem 0 0;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading {
    color: #9a9aa2;
  }
</style>
