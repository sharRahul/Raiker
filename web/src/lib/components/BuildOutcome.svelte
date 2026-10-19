<script lang="ts">
  /**
   * BR-D01 — what a finished Build turn may claim about the change it made.
   *
   * Read from the server, which reads only the runtime's own records — the
   * turn's tool actions and command runs — against the checks the owner
   * declared for the project. A turn that wrote nothing shows nothing. The
   * label is never a model's account of what it ran.
   */
  import { api } from "../api";
  import type { BuildTurnOutcome } from "../generated/apiContract";

  let { sessionId, turnId }: { sessionId: string; turnId: string } = $props();

  let outcome = $state<BuildTurnOutcome | null>(null);

  const LABEL: Record<BuildTurnOutcome["outcome"], string> = {
    no_change: "",
    completed_verified: "Verified",
    completed_unverified: "Not verified",
    failed: "Checks failed",
    blocked: "Waiting on a check",
    outcome_unknown: "Result unknown",
  };
  const RESULT: Record<BuildTurnOutcome["checks"][number]["result"], string> = {
    passed: "passed",
    failed: "failed",
    not_run: "not run after the last change",
    ran_before_change: "ran before the last change",
    waiting: "waiting for your approval",
    unknown: "did not finish",
    wrong_directory: "ran outside the repository folder",
  };
  const READBACK: Record<BuildTurnOutcome["readback"][number]["state"], string> = {
    matches: "on disk as written",
    present: "on disk",
    changed_since: "changed since this turn",
    missing: "no longer on disk",
    unreadable: "could not be read back",
  };
  const DRIFT: Record<string, string> = {
    branch: "branch",
    folder: "folder",
    identity: "repository",
    repo_kind: "repository",
    environment: "command environment",
    folder_exists: "folder (it is gone)",
  };

  const drift = $derived(
    [...new Set((outcome?.target_drift ?? []).map((name) => DRIFT[name] ?? name))],
  );
  // Files that read back as anything but what was written are worth a line;
  // a file on disk exactly as written is the expected case and stays quiet.
  const notable = $derived(
    (outcome?.readback ?? []).filter((row) => row.state !== "matches" && row.state !== "present"),
  );

  $effect(() => {
    const session = sessionId;
    const turn = turnId;
    outcome = null;
    api
      .getBuildTurnOutcome(session, turn)
      .then((value) => {
        if (session === sessionId && turn === turnId) outcome = value;
      })
      .catch(() => {
        // No record to read is not a claim either way; the line stays absent.
      });
  });
</script>

{#if outcome && outcome.outcome !== "no_change"}
  <div class="build-outcome" data-outcome={outcome.outcome} data-testid="build-outcome">
    <p>
      <span class="label">{LABEL[outcome.outcome]}</span>
      <span class="reason">{outcome.reason}</span>
    </p>
    {#if outcome.checks.length}
      <ul>
        {#each outcome.checks as check (check.command)}
          <li>
            <code>{check.command}</code> — {RESULT[check.result]}{check.exit_code !== null && check.result === "failed" ? ` (exit ${check.exit_code})` : ""}{check.result === "wrong_directory" && check.cwd ? ` (in ${check.cwd === "." ? "the workspace root" : check.cwd})` : ""}
          </li>
        {/each}
      </ul>
    {:else}
      <p class="hint">Add checks to this project's context so a change can be verified.</p>
    {/if}
    {#if notable.length}
      <ul class="readback" aria-label="Files read back">
        {#each notable as row (row.path)}
          <li data-state={row.state}><code>{row.path}</code> — {READBACK[row.state]}</li>
        {/each}
      </ul>
    {/if}
    {#if outcome.review && outcome.review.high > 0}
      <p class="review-note" data-testid="build-outcome-review">
        The review of the current patch has {outcome.review.high} high-severity finding{outcome.review.high === 1 ? "" : "s"} — see Changes.
      </p>
    {/if}
    {#if drift.length}
      <p class="drift" data-testid="build-target-drift">
        The {drift.join(", ")} this turn started on has changed since{outcome.target?.branch ? ` (it began on ${outcome.target.branch})` : ""}.
      </p>
    {:else if outcome.target}
      <p class="where">
        Ran in <code>{outcome.target.folder}</code>{outcome.target.branch ? ` on ${outcome.target.branch}` : ""}{outcome.target.head ? ` from ${outcome.target.head}` : ""}.
      </p>
    {/if}
  </div>
{/if}

<style>
  .build-outcome {
    margin: 0 0 0.5rem;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-md);
    background: var(--surface);
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .build-outcome p { margin: 0; }
  .label { font-weight: 650; margin-right: var(--space-2); color: var(--text-1); }
  .build-outcome[data-outcome="completed_verified"] { border-color: var(--ok-border); background: var(--ok-soft); }
  .build-outcome[data-outcome="completed_verified"] .label { color: var(--ok); }
  .build-outcome[data-outcome="failed"] { border-color: var(--danger-border); background: var(--danger-soft); }
  .build-outcome[data-outcome="failed"] .label { color: var(--danger); }
  .build-outcome[data-outcome="completed_unverified"],
  .build-outcome[data-outcome="blocked"],
  .build-outcome[data-outcome="outcome_unknown"] { border-color: var(--warn-border); background: var(--warn-soft); }
  .build-outcome[data-outcome="completed_unverified"] .label,
  .build-outcome[data-outcome="blocked"] .label,
  .build-outcome[data-outcome="outcome_unknown"] .label { color: var(--warn); }
  ul { margin: var(--space-1) 0 0; padding-left: 1.1rem; }
  code { font-family: var(--font-mono); font-size: var(--text-xs); }
  .hint { margin-top: var(--space-1); color: var(--text-3); }
  .readback li[data-state="missing"] { color: var(--danger); }
  .drift { margin-top: var(--space-1); color: var(--warn); }
  .review-note { margin-top: var(--space-1); color: var(--danger); }
  .where { margin-top: var(--space-1); color: var(--text-3); }
</style>
