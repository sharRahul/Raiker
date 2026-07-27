<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "../components/Badge.svelte";
  import EmptyState from "../components/EmptyState.svelte";
  import Icon from "../components/Icon.svelte";
  import PageState from "../components/PageState.svelte";
  import { api, auth, getToken, setToken, ApiError } from "../api";
  import type { ApprovalDetailView, ApprovalView } from "../apiTypes";
  import { approvalBadge } from "../statusMaps";
  import { capabilityLabel } from "../capabilityModel";
  import { formatTimestamp, humanize, relativeTime } from "../format";
  import { explainReasonCode } from "../reasonCodes";

  let { sessionId = null }: { sessionId?: string | null } = $props();

  // `executed` is the terminal status of an approval the execution relay
  // actually carried out, so it needs its own tab — otherwise the file writes
  // the owner approved would vanish from every filter.
  const FILTERS = ["pending", "approved", "executed", "denied"] as const;
  const RISK_RANK: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };

  let filter = $state<(typeof FILTERS)[number]>("pending");
  let sort = $state<"risk" | "newest">("risk");
  let approvals = $state<ApprovalView[] | null>(null);
  let loadError = $state<string | null>(null);

  let selected = $state<ApprovalDetailView | null>(null);
  let detailError = $state<string | null>(null);
  let decisionReason = $state("");
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  let criticalDecision = $state<"approve" | "deny" | null>(null);
  let criticalReason = $state("");
  let criticalPassword = $state("");
  let criticalMfaCode = $state("");
  let criticalError = $state<string | null>(null);
  let criticalBusy = $state(false);
  // B2 — a decision closes the tool call the model was waiting on, so the turn
  // it parked can pick up from here. Offered rather than automatic: the inbox is
  // not the transcript, and continuing is the owner's call.
  let resumable = $state<{ approval_id: string; session_id: string } | null>(null);
  let resumeBusy = $state(false);

  const orderedApprovals = $derived.by(() => {
    const requestedAt = (approval: ApprovalView) => Date.parse(approval.created_at) || 0;
    const scoped = sessionId
      ? (approvals ?? []).filter((approval) => approval.session_id === sessionId)
      : (approvals ?? []);
    return [...scoped].sort((left, right) => {
      const newestFirst = requestedAt(right) - requestedAt(left);
      if (sort === "newest") return newestFirst || left.approval_id.localeCompare(right.approval_id);
      return (
        (RISK_RANK[right.risk_level] ?? 0) - (RISK_RANK[left.risk_level] ?? 0) ||
        newestFirst ||
        left.approval_id.localeCompare(right.approval_id)
      );
    });
  });

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
        text: result.executes_action
          ? result.execution?.path
            ? `Executed once — wrote ${result.execution.path}. The previous contents were checkpointed.`
            : `Executed once: ${result.status}.`
          : `Recorded: ${result.status}. The action was NOT executed (metadata-only).`,
      };
      resumable =
        result.resume?.resumable && result.resume.session_id
          ? { approval_id: result.approval_id, session_id: result.resume.session_id }
          : null;
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

  async function resumeTurn() {
    if (resumable === null || resumeBusy) return;
    resumeBusy = true;
    try {
      const response = await api.resumeAfterApproval(resumable.approval_id);
      notice = { kind: "ok", text: `The agent continued the turn: ${response.message}` };
      resumable = null;
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      notice = {
        kind: "error",
        text: explained
          ? `${explained.plain} ${explained.remediation ?? ""}`
          : "The turn could not be continued.",
      };
    } finally {
      resumeBusy = false;
    }
  }

  function beginCriticalDecision(decision: "approve" | "deny") {
    criticalDecision = decision;
    criticalReason = "";
    criticalPassword = "";
    criticalMfaCode = "";
    criticalError = null;
  }

  async function resolveCritical() {
    if (selected === null || criticalDecision === null || criticalBusy || criticalReason.trim() === "") return;
    if (criticalPassword.trim() === "" && criticalMfaCode.trim() === "") return;
    criticalBusy = true;
    criticalError = null;
    const controlToken = getToken();
    try {
      const { token: elevatedToken } = await auth.elevate(
        criticalPassword.trim() || undefined,
        criticalMfaCode.trim() || undefined,
      );
      setToken(elevatedToken);
      const result = await api.resolveCriticalApproval(selected.approval.approval_id, {
        approve: criticalDecision === "approve",
        reason: criticalReason.trim(),
      });
      notice = {
        kind: "ok",
        text: result.executes_action
          ? "Critical action executed through the governed approval lifecycle."
          : result.status === "denied"
            ? "Critical action was denied."
            : `Critical approval result: ${result.message}.`,
      };
      selected = null;
      criticalDecision = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      criticalError = explained
        ? `${explained.plain} ${explained.remediation ?? ""}`
        : "Step-up verification was rejected.";
    } finally {
      setToken(controlToken);
      criticalBusy = false;
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
    Actions the agent proposed that need a human decision. Each one states whether approving
    <strong>performs it</strong> or only <strong>records your decision</strong> — the server
    decides which, from the capability gates you control.
  </p>
  <button type="button" class="btn btn-ghost btn-sm" onclick={load} aria-label="Refresh approvals">
    <Icon name="refresh" size={15} />
    Refresh
  </button>
</div>

{#if notice}
  <p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>
{/if}

{#if resumable !== null}
  <div class="notice notice-ok resume-row">
    <span>
      A turn was waiting on this decision. Continuing picks it up where it stopped, so the agent keeps
      what it had already worked out.
    </span>
    <span class="resume-actions">
      <button type="button" class="btn btn-primary btn-sm" onclick={resumeTurn} disabled={resumeBusy}>
        {resumeBusy ? "Continuing…" : "Continue the turn"}
      </button>
      <a class="btn btn-ghost btn-sm" href={`#/sessions?session=${encodeURIComponent(resumable.session_id)}`}>
        Open the session
      </a>
    </span>
  </div>
{/if}

<div class="queue-controls">
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
  <label class="sort-control">
    <span class="sr-only">Sort approvals</span>
    <select class="select" aria-label="Sort approvals" bind:value={sort}>
      <option value="risk">Highest risk first</option>
      <option value="newest">Newest first</option>
    </select>
  </label>
</div>

{#if loadError}
  <PageState state="error" title="Couldn't load approvals" detail={loadError} />
{:else if approvals === null}
  <PageState state="loading" title="Loading approvals…" />
{:else if orderedApprovals.length === 0}
  <div class="card">
    <EmptyState
      icon="approvals"
      title={sessionId ? "No approvals for this session" : filter === "pending" ? "Nothing waiting on you" : `No ${filter} approvals`}
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
        {#each orderedApprovals as a (a.approval_id)}
          <tr>
            <td>{humanize(a.tool_name)}</td>
            <td>{capabilityLabel(a.capability)}</td>
            <td><Badge variant={a.risk_level === "critical" || a.risk_level === "high" ? "blocked" : "metadata-only"} label={a.risk_level} /></td>
            <td><Badge variant={approvalBadge(a.is_expired ? "expired" : a.status)} label={a.is_expired ? "expired" : a.status} /></td>
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
        Review {humanize(selected.approval.tool_name)}
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
      <div><dt>Session</dt><dd><a class="mono" href={`#/sessions?session=${encodeURIComponent(selected.approval.session_id)}`}>View session</a></dd></div>
      <div><dt>Requested</dt><dd>{relativeTime(selected.approval.created_at)}</dd></div>
      {#if selected.approval.expires_at}
        <div><dt>Expires</dt><dd>{formatTimestamp(selected.approval.expires_at)}</dd></div>
      {/if}
    </dl>

    {#if selected.approval.is_expired}
      <p class="notice notice-danger" role="alert">
        This approval expired at {formatTimestamp(selected.approval.expires_at)}. The server will not accept a decision.
        Refresh the queue to retrieve the current state.
      </p>
    {/if}

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

    {#if selected.approval.status === "pending" && !selected.approval.is_expired && selected.approval.critical}
      <p class="notice notice-danger">This is a critical action. Re-authenticate before the server can resolve it through the human-only critical lifecycle.</p>
      <div class="decision-actions">
        <button type="button" class="btn btn-danger" onclick={() => beginCriticalDecision("deny")} disabled={busy || criticalBusy}>
          Begin critical denial
        </button>
        <button type="button" class="btn btn-primary" onclick={() => beginCriticalDecision("approve")} disabled={busy || criticalBusy}>
          Begin critical approval
        </button>
      </div>
    {:else if selected.approval.status === "pending" && !selected.approval.is_expired}
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
          {busy
            ? selected.executes_on_approval
              ? "Executing…"
              : "Recording…"
            : selected.executes_on_approval
              ? "Approve and execute once"
              : "Approve (record only)"}
        </button>
      </div>
    {:else if selected.approval.is_expired}
      <p class="resolved-note">Expired before a decision was recorded.</p>
    {:else}
      <p class="resolved-note">
        Already resolved: <Badge variant={approvalBadge(selected.approval.status)} label={selected.approval.status} />
      </p>
    {/if}
  </section>
{/if}

{#if criticalDecision !== null}
  <div class="overlay">
    <div class="step-up" role="dialog" aria-modal="true" aria-labelledby="critical-step-up-title" tabindex="-1">
      <h2 id="critical-step-up-title">Step up to {criticalDecision} this critical action</h2>
      <p>Raiker will obtain a short-lived elevated session, then ask the server to re-check this immutable intent.</p>
      <label class="field-label" for="critical-reason">Decision note</label>
      <textarea id="critical-reason" class="textarea" rows="2" bind:value={criticalReason} disabled={criticalBusy}></textarea>
      <label class="field-label" for="critical-password">Password</label>
      <input id="critical-password" class="input" type="password" bind:value={criticalPassword} autocomplete="current-password" disabled={criticalBusy} />
      <label class="field-label" for="critical-mfa">MFA code (optional)</label>
      <input id="critical-mfa" class="input" inputmode="numeric" autocomplete="one-time-code" bind:value={criticalMfaCode} disabled={criticalBusy} />
      <p class="hint">Provide your password or an MFA code. Neither is stored by the browser.</p>
      {#if criticalError}<p class="error" role="alert">{criticalError}</p>{/if}
      <div class="decision-actions">
        <button type="button" class="btn" onclick={() => (criticalDecision = null)} disabled={criticalBusy}>Cancel</button>
        <button type="button" class:btn-danger={criticalDecision === "deny"} class="btn btn-primary" onclick={resolveCritical} disabled={criticalBusy || criticalReason.trim() === "" || (criticalPassword.trim() === "" && criticalMfaCode.trim() === "")}>
          {criticalBusy ? "Verifying..." : criticalDecision === "approve" ? "Approve critical action" : "Deny critical action"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .head-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
  }
  @media (max-width: 720px) {
    .head-row {
      flex-direction: column;
    }
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
  .queue-controls {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .sort-control .select {
    min-width: 10.5rem;
  }
  @media (max-width: 520px) {
    .queue-controls {
      flex-direction: column;
    }
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
  .resume-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
  }
  .resume-actions {
    display: inline-flex;
    gap: var(--space-2);
    flex-shrink: 0;
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
  .overlay {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: var(--overlay);
    z-index: 60;
  }
  .step-up {
    width: min(34rem, calc(100% - 2rem));
    display: grid;
    gap: 0.55rem;
    padding: var(--space-5);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    background: var(--raised);
    box-shadow: var(--shadow-2);
  }
  .step-up h2, .step-up p { margin: 0; }
  .hint { color: var(--text-3); font-size: 0.8rem; }
</style>
