<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import { api, ApiError } from "../api";
  import type { ApprovalDetailView, ApprovalView } from "../apiTypes";
  import { approvalBadge } from "../statusMaps";
  import { capabilityLabel } from "../capabilityModel";
  import { relativeTime, shortId } from "../format";
  import { explainReasonCode } from "../reasonCodes";

  const FILTERS = ["pending", "approved", "denied"] as const;

  let filter = $state<(typeof FILTERS)[number]>("pending");
  let approvals = $state<ApprovalView[] | null>(null);
  let loadError = $state<string | null>(null);

  let selected = $state<ApprovalDetailView | null>(null);
  let detailError = $state<string | null>(null);
  let decisionReason = $state("");
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  async function load() {
    loadError = null;
    try {
      approvals = await api.approvals(filter);
    } catch (e) {
      approvals = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  async function openDetail(id: string) {
    detailError = null;
    decisionReason = "";
    notice = null;
    try {
      selected = await api.approval(id);
    } catch (e) {
      selected = null;
      detailError = e instanceof ApiError ? `Could not load approval (${e.status}).` : "Could not load approval.";
    }
  }

  async function resolve(approve: boolean) {
    if (selected === null || busy) return;
    busy = true;
    notice = null;
    try {
      const result = await api.resolveApproval(selected.approval.approval_id, {
        approve,
        reason: decisionReason.trim() || (approve ? "approved via web UI" : "denied via web UI"),
      });
      notice = {
        kind: "ok",
        text: `Recorded: ${result.status}. The action was NOT executed (metadata-only).`,
      };
      selected = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained ? `${explained.plain} ${explained.remediation ?? ""}` : "The decision was rejected.",
      };
    } finally {
      busy = false;
    }
  }

  function setFilter(value: (typeof FILTERS)[number]) {
    filter = value;
    selected = null;
    void load();
  }

  onMount(load);
</script>

<div class="head-row">
  <p class="page-lead">
    Actions the agent proposed that need a human decision. Resolving an approval
    <strong>records your decision only</strong> — it never executes the action.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh approvals">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

<div class="filters" role="tablist" aria-label="Approval status filter">
  {#each FILTERS as f (f)}
    <button
      type="button"
      class="filter-btn"
      class:active={filter === f}
      role="tab"
      aria-selected={filter === f}
      onclick={() => setFilter(f)}
    >
      {f}
    </button>
  {/each}
</div>

{#if loadError}
  <p class="error" role="alert">Unavailable: {loadError}</p>
{:else if approvals === null}
  <p class="loading">Loading…</p>
{:else if approvals.length === 0}
  <div class="card">
    <EmptyState
      icon="approvals"
      title={filter === "pending" ? "Nothing waiting on you" : `No ${filter} approvals`}
      body={filter === "pending"
        ? "When the agent proposes a gated action, it will appear here for your decision."
        : undefined}
    />
  </div>
{:else}
  <div class="card list-card">
    <table class="table">
      <thead>
        <tr>
          <th>Action</th>
          <th>Capability</th>
          <th>Risk</th>
          <th>Status</th>
          <th>Requested</th>
          <th><span class="sr-only">Open</span></th>
        </tr>
      </thead>
      <tbody>
        {#each approvals as a (a.approval_id)}
          <tr>
            <td><code>{a.tool_name}</code></td>
            <td>{capabilityLabel(a.capability)}</td>
            <td><Badge variant={a.risk_level === "critical" || a.risk_level === "high" ? "blocked" : "metadata-only"} label={a.risk_level} /></td>
            <td><Badge variant={approvalBadge(a.status)} label={a.status} /></td>
            <td title={a.created_at}>{relativeTime(a.created_at)}</td>
            <td>
              <button type="button" class="btn btn-sm" onclick={() => openDetail(a.approval_id)}>
                Review
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

{#if detailError}
  <p class="error" role="alert">{detailError}</p>
{/if}

{#if selected !== null}
  <section class="card detail" aria-labelledby="approval-detail-h">
    <div class="detail-head">
      <h2 id="approval-detail-h">
        Review <code>{selected.approval.tool_name}</code>
      </h2>
      <button type="button" class="btn btn-ghost btn-sm" onclick={() => (selected = null)}>
        <Icon name="x" size={14} />
        Close
      </button>
    </div>

    <p class="notice">{selected.metadata_only_notice}</p>

    <dl class="meta">
      <div><dt>Capability</dt><dd>{capabilityLabel(selected.approval.capability)}</dd></div>
      <div><dt>Risk</dt><dd>{selected.approval.risk_level}</dd></div>
      <div><dt>Session</dt><dd class="mono">{shortId(selected.approval.session_id)}</dd></div>
      <div><dt>Requested</dt><dd>{relativeTime(selected.approval.created_at)}</dd></div>
    </dl>

    {#if selected.preview_kind === "file_diff" || selected.preview_kind === "patch"}
      <h3>{selected.preview_kind === "file_diff" ? "Proposed file change" : "Proposed patch"}</h3>
      {#if selected.diff_path}
        <p class="diff-path mono">{selected.diff_path}</p>
      {/if}
      <pre class="diff">{selected.diff ?? "(empty diff)"}</pre>
    {:else}
      <h3>Proposed arguments (redacted)</h3>
      <pre class="diff">{JSON.stringify(selected.arguments, null, 2)}</pre>
    {/if}

    {#if selected.approval.status === "pending"}
      <label class="field-label" for="decision-reason">Decision note (optional)</label>
      <textarea
        id="decision-reason"
        class="textarea"
        rows="2"
        bind:value={decisionReason}
        placeholder="Why are you approving or denying this?"
        disabled={busy}
      ></textarea>
      <div class="decision-actions">
        <button type="button" class="btn btn-danger" onclick={() => resolve(false)} disabled={busy}>
          Deny
        </button>
        <button type="button" class="btn btn-primary" onclick={() => resolve(true)} disabled={busy}>
          {busy ? "Recording…" : "Approve (record only)"}
        </button>
      </div>
    {:else}
      <p class="resolved-note">
        Already resolved: <Badge variant={approvalBadge(selected.approval.status)} label={selected.approval.status} />
      </p>
    {/if}
  </section>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .filters {
    display: inline-flex;
    gap: 2px;
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-pill);
    padding: 3px;
    margin-bottom: var(--space-4);
  }
  .filter-btn {
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: capitalize;
    color: var(--text-2);
    background: transparent;
    border: none;
    border-radius: var(--r-pill);
    padding: 0.25rem 0.85rem;
    cursor: pointer;
  }
  .filter-btn.active {
    background: var(--surface);
    color: var(--accent);
    box-shadow: var(--shadow-1);
  }
  .list-card {
    padding: var(--space-2) var(--space-3);
    overflow-x: auto;
  }
  .detail {
    margin-top: var(--space-4);
  }
  .detail-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.4rem 1rem;
    margin: var(--space-3) 0;
  }
  .meta div {
    display: flex;
    gap: 0.4rem;
    align-items: baseline;
  }
  .meta dt {
    font-size: 0.72rem;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-3);
  }
  .meta dd {
    margin: 0;
    font-size: 0.86rem;
  }
  .diff-path {
    color: var(--text-2);
    font-size: 0.8rem;
    margin: 0 0 0.35rem;
  }
  .diff {
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.7rem 0.9rem;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    overflow-x: auto;
    white-space: pre;
    max-height: 24rem;
  }
  .decision-actions {
    display: flex;
    gap: 0.6rem;
    justify-content: flex-end;
    margin-top: var(--space-3);
  }
  .resolved-note {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-2);
    margin: var(--space-3) 0 0;
  }
  .error {
    color: var(--danger);
  }
  .loading {
    color: var(--text-2);
  }
</style>
