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
   *
   * **Ask Raiker to fix** (BR-D04 bounded repair) only writes a scoped request
   * into the composer — this finding, this file, nothing else, no merge — for
   * the owner to read and send. It never sends itself, so a repair is one more
   * ordinary turn under the same modes and approvals, never a loop.
   */
  import { api, ApiError } from "../api";
  import type { CodeRepoReviewView } from "../generated/apiContract";

  let {
    repoId,
    revision = 0,
    onrepair,
  }: { repoId: string; revision?: number; onrepair?: (request: string) => void } = $props();

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

  type Finding = NonNullable<CodeRepoReviewView["review"]>["findings"][number];

  /** The one change a repair turn is asked to make — and the limits it keeps. */
  function repairRequest(finding: Finding): string {
    const where = finding.path ? ` in ${finding.path}${finding.line ? ` at line ${finding.line}` : ""}` : "";
    return (
      `Fix this patch review finding${where}: ${finding.title}. ${finding.next_step} ` +
      "Change only what this finding needs, then run the project's checks. " +
      "Do not commit, push or merge."
    );
  }

  const resolved = $derived(view?.review?.resolved ?? []);

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
                  {#if finding.since === "new"}<span class="since">New</span>{/if}
                </p>
                <p class="evidence">{finding.evidence}</p>
                <p class="next">{finding.next_step}</p>
                {#if onrepair && finding.severity !== "info"}
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm repair"
                    onclick={() => onrepair?.(repairRequest(finding))}
                  >Ask Raiker to fix</button>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
      {#if resolved.length}
        <div class="resolved" data-testid="patch-review-resolved">
          <p>Fixed since the last review:</p>
          <ul>
            {#each resolved as item, index (`${item.rule}:${item.path}:${index}`)}
              <li>{item.title}{#if item.path}<code class="resolved-path">{item.path}</code>{/if}</li>
            {/each}
          </ul>
        </div>
      {/if}
    {:else}
      {#if view.previous}
        <p class="stale" role="status" data-testid="patch-review-stale">
          The last review was of an earlier version of this patch ({view.previous.findings}
          finding{view.previous.findings === 1 ? "" : "s"}). Review it again to see what changed.
        </p>
      {/if}
      <p class="hint">
        Checks this exact patch for credentials, conflict markers, debugging left in, workflow
        changes, instruction-like text, missing tests and files that no longer parse. The review is
        kept for this patch.
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
  .since {
    margin-left: 0.35rem;
    padding: 0 0.4rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--accent-border);
    background: var(--accent-soft);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-1);
  }
  .repair {
    margin-top: 0.2rem;
    padding-inline: 0;
  }
  .resolved,
  .stale {
    margin: var(--space-2) 0 0;
    color: var(--text-2);
  }
  .resolved p {
    margin: 0;
    color: var(--ok);
    font-weight: 600;
  }
  .resolved ul {
    margin: 0.2rem 0 0;
    padding-left: 1.1rem;
  }
  .resolved code {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  /* Spacing in CSS, not in markup: whitespace before an element at the start
     of an {#if} block is dropped, which ran the title into the path. */
  .resolved-path {
    margin-left: 0.4rem;
  }
</style>
