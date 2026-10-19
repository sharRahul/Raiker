<script lang="ts">
  /**
   * BR-12 — the pull requests Raiker opened on this repository, as GitHub
   * confirmed them.
   *
   * After a pull request is created, Raiker reads it back from GitHub with the
   * same credential. **Confirmed by GitHub** means that read returned this
   * number with the head and base branch Raiker asked for; **GitHub answered
   * differently** means it returned another branch or number; **Not confirmed**
   * means the read-back failed, so only the create response is known. Evidence
   * only — merging stays with the owner, on GitHub.
   */
  import { api } from "../api";
  import type { CodeRepoPullRequestsView } from "../generated/apiContract";

  let { repoId, revision = 0 }: { repoId: string; revision?: number } = $props();

  let view = $state<CodeRepoPullRequestsView | null>(null);

  $effect(() => {
    const id = repoId;
    void revision;
    let cancelled = false;
    api
      .readCodeRepoPullRequests(id)
      .then((value) => {
        if (!cancelled) view = value;
      })
      .catch(() => {
        if (!cancelled) view = null;
      });
    return () => {
      cancelled = true;
    };
  });

  const CONFIRMATION: Record<string, string> = {
    confirmed: "Confirmed by GitHub",
    mismatch: "GitHub answered differently",
    unconfirmed: "Not confirmed",
  };
</script>

{#if view && view.receipts.length}
  <section class="pull-requests" aria-label="Pull requests" data-testid="pull-request-receipts">
    <h3>Pull requests</h3>
    <ul>
      {#each view.receipts.slice(0, 6) as receipt (receipt.receipt_id)}
        <li data-confirmation={receipt.confirmation}>
          <a href={receipt.url} target="_blank" rel="noopener noreferrer" class="number">#{receipt.number}</a>
          <span class="branches">
            <code>{receipt.head_branch}</code> → <code>{receipt.base_branch}</code>
            {#if receipt.head_sha}<code class="sha" title={receipt.head_sha}>{receipt.head_sha.slice(0, 7)}</code>{/if}
          </span>
          <span class="badge" title={receipt.confirmed_at ? `Read back ${receipt.confirmed_at}` : ""}>
            {CONFIRMATION[receipt.confirmation]}{receipt.state && receipt.state !== "open" ? ` · ${receipt.state}` : ""}
          </span>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .pull-requests {
    margin: var(--space-2) 0;
    font-size: var(--text-sm);
  }
  h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.25rem;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    min-width: 0;
    color: var(--text-2);
  }
  .number {
    font-weight: 600;
    color: var(--text-1);
  }
  .branches {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  code {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  .sha {
    margin-left: 0.35rem;
    color: var(--text-3);
  }
  .badge {
    margin-left: auto;
    padding: 0.05rem 0.45rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    font-size: var(--text-xs);
  }
  li[data-confirmation="confirmed"] .badge {
    border-color: var(--ok-border);
    background: var(--ok-soft);
    color: var(--ok);
  }
  li[data-confirmation="mismatch"] .badge {
    border-color: var(--danger-border);
    background: var(--danger-soft);
    color: var(--danger);
  }
  li[data-confirmation="unconfirmed"] .badge {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
</style>
