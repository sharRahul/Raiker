<script lang="ts">
  import { onMount } from "svelte";
  import Badge from "./Badge.svelte";
  import ApprovalDetail from "./ApprovalDetail.svelte";
  import MetadataOnlyBanner from "./MetadataOnlyBanner.svelte";
  import { api, ApiError } from "./api";
  import type { ApprovalView } from "./apiTypes";

  let approvals = $state<ApprovalView[] | null>(null);
  let error = $state<string | null>(null);
  let selectedId = $state<string | null>(null);

  async function load() {
    error = null;
    try {
      approvals = await api.approvals();
      // Keep the selection valid after a refresh (e.g. once resolved, it leaves the pending list).
      if (selectedId !== null && !approvals.some((a) => a.approval_id === selectedId)) {
        selectedId = null;
      }
    } catch (e) {
      error = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }

  function ageLabel(seconds: number | null): string {
    if (seconds === null) return "—";
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  }

  onMount(load);
</script>

<h1 id="page-title">Approvals</h1>
<p class="lead">
  Review and resolve approval-required actions. Resolving records a human decision — it never runs
  the action.
</p>

<MetadataOnlyBanner />

{#if error}
  <p class="state-error">Approvals unavailable: {error}</p>
{:else if approvals === null}
  <p class="state-loading">Loading approvals…</p>
{:else if approvals.length === 0}
  <p class="state-empty">No pending approvals.</p>
{:else}
  <div class="layout">
    <table class="queue">
      <thead>
        <tr><th>Tool</th><th>Capability</th><th>Risk</th><th>Age</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        {#each approvals as a (a.approval_id)}
          <tr class:selected={a.approval_id === selectedId}>
            <td><code>{a.tool_name}</code></td>
            <td class="mono">{a.capability}</td>
            <td>
              <span class="risk" class:risk-high={a.risk_level === "high"}>{a.risk_level || "—"}</span>
            </td>
            <td class="mono">{ageLabel(a.age_seconds)}</td>
            <td><Badge variant="approval-required" /></td>
            <td>
              <button type="button" onclick={() => (selectedId = a.approval_id)}>Review</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if selectedId !== null}
      {#key selectedId}
        <ApprovalDetail approvalId={selectedId} onResolved={load} />
      {/key}
    {/if}
  </div>
{/if}

<style>
  .lead {
    max-width: 64ch;
    color: #c2c2c9;
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 1rem;
  }
  @media (min-width: 60rem) {
    .layout {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
      align-items: start;
    }
  }
  table.queue {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
  }
  .queue th,
  .queue td {
    text-align: left;
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid #1f1f24;
  }
  .queue th {
    color: #8b8b93;
    font-weight: 600;
  }
  tr.selected {
    background: #14202c;
  }
  .mono {
    font-family: ui-monospace, monospace;
    color: #b6b6bd;
  }
  .risk {
    font-size: 0.74rem;
    border: 1px solid #4a4a52;
    border-radius: 999px;
    padding: 0.05rem 0.45rem;
    color: #d0d0d6;
  }
  .risk-high {
    border-color: #8a2f2f;
    color: #ef9a9a;
  }
  .queue button {
    background: #1c2a3a;
    color: #cfe5ff;
    border: 1px solid #2d5a82;
    border-radius: 5px;
    padding: 0.25rem 0.7rem;
    cursor: pointer;
  }
  .queue button:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
  code {
    font-family: ui-monospace, monospace;
    color: #cdd6e0;
  }
  .state-error {
    color: #ef9a9a;
  }
  .state-loading,
  .state-empty {
    color: #9a9aa2;
  }
</style>
