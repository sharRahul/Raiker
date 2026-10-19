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
   *
   * **Ask the model to review** (BR-D04 selected model review) sends this same
   * patch, credential-redacted, to the model chosen in the composer and shows
   * what it says under its own heading. Its findings are the model's reading —
   * nothing checked them, and they never decide whether a turn is verified.
   * The same model is never asked twice about the same patch.
   *
   * BR-11 — after the owner asks for a repair, the next time the working tree
   * settles the patch is reviewed again, once: the repair is rereviewed
   * without anyone pressing a button, and nothing loops. A finding that has
   * survived several reviews in a row says how many, so a repair that is not
   * converging is visible before it is asked for again.
   *
   * Each stored review is signed by this installation (BR-D05) and checked on
   * every read: **Signed here** when it is exactly what was taken, and a
   * warning when the stored review no longer matches its signature.
   */
  import { api, ApiError } from "../api";
  import type { CodeRepoReviewView, ModelPatchReview } from "../generated/apiContract";
  import { modelName } from "../modelPresentation";

  let {
    repoId,
    revision = 0,
    onrepair,
    reviewModel = null,
  }: {
    repoId: string;
    revision?: number;
    onrepair?: (request: string) => void;
    /** The composer's model choice; null or empty asks the owner's default. */
    reviewModel?: { profile: string; model: string } | null;
  } = $props();

  let view = $state<CodeRepoReviewView | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let modelBusy = $state(false);
  let modelError = $state<string | null>(null);
  let modelReused = $state(false);
  // BR-11 — a repair was asked for; the next settled working tree is reviewed once.
  let rereviewPending = $state(false);
  let rereviewed = $state(false);
  let lastRevision = -1;

  $effect(() => {
    const id = repoId;
    const current = revision;
    let cancelled = false;
    error = null;
    const changed = lastRevision !== -1 && current !== lastRevision;
    lastRevision = current;
    api
      .readCodeRepoReview(id)
      .then((value) => {
        if (cancelled) return;
        view = value;
        // The turn that carried the repair has settled and the patch moved:
        // review it again, once, so the owner sees whether the repair worked.
        if (changed && rereviewPending && value.has_changes && !value.review) {
          rereviewPending = false;
          rereviewed = true;
          void review();
        }
      })
      .catch(() => {
        if (!cancelled) view = null;
      });
    return () => {
      cancelled = true;
    };
  });

  const MODEL_REFUSALS: Record<string, string> = {
    model_review_unreadable: "The model answered, but not with findings Raiker could read. Nothing was stored; try again or choose another model.",
    model_review_profile_unknown: "The model chosen in the composer is not available. Choose another in the model picker.",
    model_review_model_required: "Choose a model in the composer first.",
  };

  async function askModel(): Promise<void> {
    if (!view) return;
    modelBusy = true;
    modelError = null;
    try {
      const body =
        reviewModel && reviewModel.profile ? { model_profile: reviewModel.profile, model: reviewModel.model || null } : {};
      const answer = await api.modelReviewCodeRepoPatch(repoId, body);
      modelReused = answer.reused;
      view = { ...view, model_review: answer.model_review, model_attestation: answer.model_attestation ?? null };
    } catch (caught) {
      const code = caught instanceof ApiError ? (caught.reasonCode ?? "") : "";
      const known = Object.entries(MODEL_REFUSALS).find(([prefix]) => code.startsWith(prefix));
      modelError = known
        ? known[1]
        : code.startsWith("model_review_provider_error")
          ? "The model's provider refused or failed this request. Check the connection on the Models page."
          : caught instanceof ApiError
            ? caught.message
            : "Couldn't ask the model to review this patch.";
    } finally {
      modelBusy = false;
    }
  }

  const modelReading = $derived<ModelPatchReview | null>(view?.model_review ?? null);

  /** A model's text split on its `backtick` spans, so code reads as code — never parsed as HTML. */
  function spans(text: string): { code: boolean; text: string }[] {
    return text.split(/`([^`]+)`/).map((part, index) => ({ code: index % 2 === 1, text: part }));
  }

  const SIGNED: Record<string, string> = {
    verified: "Signed here",
    invalid: "Signature does not match",
    unknown_key: "Signed by another key",
    unsigned: "",
  };
  const attestation = $derived(view?.attestation ?? null);
  const modelAttestation = $derived(view?.model_attestation ?? null);
  function signedTitle(value: { key_id: string | null; signed_at: string | null } | null): string {
    if (!value?.key_id) return "";
    return `Signed with this installation's key ${value.key_id}${value.signed_at ? ` at ${value.signed_at}` : ""}`;
  }
  const askLabel = $derived(
    reviewModel?.model ? `Ask ${modelName(reviewModel.model)} to review` : "Ask the model to review",
  );

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
  function askForRepair(finding: Finding): void {
    rereviewPending = true;
    rereviewed = false;
    onrepair?.(repairRequest(finding));
  }

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
        {#if attestation && SIGNED[attestation.state]}
          <span class="signed" data-state={attestation.state} title={signedTitle(attestation)}>
            {SIGNED[attestation.state]}
          </span>
        {/if}
      {:else}
        <button type="button" class="btn btn-soft btn-sm" onclick={review} disabled={busy}>
          {busy ? "Reviewing…" : "Review this patch"}
        </button>
      {/if}
    </div>
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}
    {#if attestation?.state === "invalid"}
      <p class="error" role="alert" data-testid="patch-review-tampered">
        This stored review no longer matches the signature Raiker made when it was taken. Something
        changed it afterwards — don't rely on these findings.
      </p>
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
                  {#if (finding.reviews_present ?? 1) > 1}
                    <span class="persisting" title="Raised by this many reviews in a row, this one included">
                      In {finding.reviews_present} reviews in a row
                    </span>
                  {/if}
                </p>
                <p class="evidence">{finding.evidence}</p>
                <p class="next">{finding.next_step}</p>
                {#if onrepair && finding.severity !== "info"}
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm repair"
                    onclick={() => askForRepair(finding)}
                  >Ask Raiker to fix</button>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
      {#if rereviewed}
        <p class="hint" role="status" data-testid="patch-review-rereviewed">Reviewed again after the repair.</p>
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
    <div class="model-review" data-testid="patch-model-review">
      <div class="head">
        <h4>Model review</h4>
        {#if modelReading}
          <span class="fingerprint" title={`Read by ${modelReading.model} · patch ${modelReading.fingerprint}`}>
            {modelName(modelReading.model)}{modelReused ? " · already read" : ""}
          </span>
          {#if modelAttestation && SIGNED[modelAttestation.state]}
            <span class="signed" data-state={modelAttestation.state} title={signedTitle(modelAttestation)}>
              {SIGNED[modelAttestation.state]}
            </span>
          {/if}
        {:else}
          <button type="button" class="btn btn-ghost btn-sm" onclick={askModel} disabled={modelBusy}>
            {modelBusy ? "Asking…" : askLabel}
          </button>
        {/if}
      </div>
      {#if modelError}
        <p class="error" role="alert">{modelError}</p>
      {/if}
      {#if modelReading}
        <p class="summary" role="status">
          {modelReading.findings.length === 0
            ? "The model raised nothing on this patch."
            : `The model raised ${modelReading.findings.length} point${modelReading.findings.length === 1 ? "" : "s"}.`}
          These are its reading, not checks: verify one before acting on it.
        </p>
        {#if modelReading.findings.length}
          <ul class="findings">
            {#each modelReading.findings as finding (finding.finding_id)}
              <li data-severity={finding.severity} data-source="model">
                <span class="severity">{SEVERITY[finding.severity]}</span>
                <div class="body">
                  <p class="title">
                    {#each spans(finding.title) as part, index (index)}{#if part.code}<code class="inline">{part.text}</code>{:else}{part.text}{/if}{/each}
                    {#if finding.path}
                      <code>{finding.path}{finding.line ? `:${finding.line}` : ""}</code>
                    {/if}
                  </p>
                  <p class="evidence">
                    {#each spans(finding.evidence) as part, index (index)}{#if part.code}<code class="inline">{part.text}</code>{:else}{part.text}{/if}{/each}
                  </p>
                  <p class="next">
                    {#each spans(finding.next_step) as part, index (index)}{#if part.code}<code class="inline">{part.text}</code>{:else}{part.text}{/if}{/each}
                  </p>
                  {#if onrepair}
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm repair"
                      onclick={() => askForRepair(finding)}
                    >Ask Raiker to fix</button>
                  {/if}
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      {:else if !modelError}
        <p class="hint">
          Sends this patch, with credentials removed, to the model chosen in the composer and shows what
          it thinks is wrong. The model's reading never decides whether a change is verified.
        </p>
      {/if}
    </div>
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
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  /* The heading on the left; whatever follows it (the fingerprint and its
     signature, or the button) sits together on the right. */
  .head > :nth-child(2) {
    margin-left: auto;
  }
  h3 {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
  }
  .signed {
    padding: 0 0.45rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--ok-border);
    background: var(--ok-soft);
    font-size: var(--text-xs);
    color: var(--ok);
  }
  .signed[data-state="invalid"],
  .signed[data-state="unknown_key"] {
    border-color: var(--danger-border);
    background: var(--danger-soft);
    color: var(--danger);
  }
  .model-review {
    margin-top: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid var(--neutral-border);
  }
  h4 {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
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
  code.inline {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: 0 0.2rem;
    border-radius: var(--r-sm);
    background: var(--neutral-soft);
    overflow-wrap: anywhere;
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
  .persisting {
    margin-left: 0.35rem;
    padding: 0 0.4rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--warn-border);
    background: var(--warn-soft);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--warn);
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
