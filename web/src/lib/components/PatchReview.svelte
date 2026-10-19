<script lang="ts">
  /**
   * BR-D04 — the review of the exact patch in the working tree.
   *
   * Reads the stored review for the current patch (none until asked for) and
   * offers **Review this patch**, which reviews it once on the server. The
   * review is keyed by the patch's fingerprint, so pressing it again on the same
   * patch shows the same findings — "Already reviewed" — rather than a second
   * set, and any change to the patch makes the stored review stale by itself.
   *
   * Findings are deterministic rules, each tied to a file and line with its
   * evidence and a next step. Nothing here changes a file; acting on a finding
   * is an ordinary governed change.
   */
  import { api, ApiError } from "../api";
  import type { CodeRepoReviewView } from "../generated/apiContract";

  let { repoId, revision = 0 }: { repoId: string; revision?: number } = $props();

  let view = $state<CodeRepoReviewView | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    const id = repoId;
    void revision;
    let cancelled = false;
    error = null;
    api
      .readCodeRepoReview(id)
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

  async function review(): Promise<void> {
    busy = true;
    error = null;
    try {
      view = await api.reviewCodeRepoPatch(repoId);
    } catch (caught) {
      error = caught instanceof ApiError ? caught.message : "Couldn't review this patch.";
    } finally {
      busy = false;
    }
  }

  const SEVERITY: Record<string, string> = { high: "High", medium: "Medium", low: "Low", info: "Note" };

  const findings = $derived(view?.review?.findings ?? []);
  const counts = $derived(view?.review?.counts ?? {});
  const summary = $derived.by(() => {
    if (!view?.review) return "";
    if (findings.length === 0) return "No findings on this patch.";
    const parts = (["high", "medium", "low", "info"] as const)
      .filter((key) => (counts[key] ?? 0) > 0)
      .map((key) => `${counts[key]} ${SEVERITY[key].toLowerCase()}`);
    return `${findings.length} finding${findings.length === 1 ? "" : "s"}: ${parts.join(", ")}.`;
  });
</script>

{#if view?.has_changes}
  <section class="patch-review" aria-label="Patch review" data-testid="patch-review">
    <div class="head">
      <h3>Patch review</h3>
      {#if view.review}
        <span class="fingerprint" title={`Patch fingerprint ${view.fingerprint}`}>
          {view.reused ? "Reviewed" : "Reviewed just now"} · {view.fingerprint.slice(0, 8)}
        </span>
      {:else}
        <button type="button" class="btn btn-soft btn-sm" onclick={review} disabled={busy}>
          {busy ? "Reviewing…" : "Review this patch"}
        </button>
      {/if}
    </div>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if view.review}
      <p class="summary" role="status">{summary}</p>
      {#if findings.length}
        <ul class="findings">
          {#each findings as finding (finding.finding_id)}
            <li data-severity={finding.severity}>
              <span class="severity">{SEVERITY[finding.severity]}</span>
              <div class="body">
                <p class="title">
                  {finding.title}
                  {#if finding.path}
                    <code>{finding.path}{finding.line ? `:${finding.line}` : ""}</code>
                  {/if}
                </p>
                <p class="evidence">{finding.evidence}</p>
                <p class="next">{finding.next_step}</p>
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    {:else}
      <p class="hint">
        Checks this exact patch for credentials, conflict markers, debugging left in, workflow
        changes, instruction-like text and missing tests. The review is kept for this patch.
      </p>
    {/if}
  </section>
{/if}

<style>
  .patch-review {
    margin: var(--space-2) 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--surface);
    font-size: var(--text-sm);
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  h3 {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
  }
  .fingerprint {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .summary,
  .hint,
  .error {
    margin: var(--space-1) 0 0;
    color: var(--text-2);
  }
  .hint {
    color: var(--text-3);
  }
  .error {
    color: var(--danger);
  }
  .findings {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .findings li {
    display: flex;
    gap: var(--space-2);
    align-items: flex-start;
  }
  .severity {
    flex: none;
    min-width: 4.5rem;
    padding: 0.05rem 0.45rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    font-size: var(--text-xs);
    text-align: center;
    color: var(--text-2);
  }
  li[data-severity="high"] .severity {
    border-color: var(--danger-border);
    background: var(--danger-soft);
    color: var(--danger);
  }
  li[data-severity="medium"] .severity {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
  .body {
    min-width: 0;
  }
  .body p {
    margin: 0;
  }
  .title {
    color: var(--text-1);
    font-weight: 600;
  }
  .title code {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 400;
    color: var(--text-2);
    overflow-wrap: anywhere;
  }
  .evidence,
  .next {
    color: var(--text-2);
  }
  .next {
    color: var(--text-3);
  }
</style>
