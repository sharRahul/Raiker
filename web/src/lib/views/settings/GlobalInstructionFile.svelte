<script lang="ts">
  /**
   * RAIKER.md — this account's global instruction file.
   *
   * It applies to Build in every project where file instructions are on, and
   * only after the owner reviews the exact revision. Its path is shown so the
   * owner can open it in their own editor; Raiker never edits it after the
   * starter, and a starter never overwrites.
   */
  import { failure } from "../../errorCopy";
  import { ApiError } from "../../api";
  import { knownReasonCopy } from "../../reasonCodes";
  import { contract } from "../../generated/apiContract";
  import type { InstructionFileSource } from "../../generated/apiContract";

  let source = $state<InstructionFileSource | null>(null);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state(false);
  let disclosure = $state<boolean | null>(null);
  const opened = $derived(disclosure ?? (source?.state === "unreviewed" || source?.state === "changed"));

  const STATE_WORD: Record<string, string> = {
    absent: "No file yet",
    empty: "Empty",
    disabled: "Off",
    unreviewed: "Needs review",
    approved: "In use",
    changed: "Changed — needs review",
    unsafe: "Not read",
    unreadable: "Not read",
    invalid: "Not read",
    oversized: "Too long",
    root_unavailable: "Unavailable",
  };

  async function load() {
    loadError = null;
    try {
      source = (await contract.getGlobalInstructionFile()).source;
    } catch (e) {
      loadError = failure("Your global RAIKER.md could not be read", "Whether Build uses it is unconfirmed.", "Choose Retry to read it again.", e);
    }
  }

  async function act(run: () => Promise<{ source: InstructionFileSource }>, what: string) {
    busy = true;
    actionError = null;
    try {
      source = (await run()).source;
    } catch (e) {
      const code = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      actionError = failure(what, "Nothing was changed.", knownReasonCopy(code)?.remediation ?? "Choose Retry to read the file again.", e);
      if (code === "instruction_file_changed_since_preview") void load();
    } finally {
      busy = false;
    }
  }

  void load();
</script>

<section class="settings-card" aria-labelledby="global-raiker-md-h" data-testid="global-instruction-file">
  <details class="tuning" open={opened} ontoggle={(event) => (disclosure = event.currentTarget.open)}>
    <summary>
      <span class="summary-title" id="global-raiker-md-h">Global RAIKER.md</span>
      <span class="summary-hint" data-testid="global-instruction-file-state">
        {source ? STATE_WORD[source.state] ?? source.state : loadError ? "Unavailable" : "Reading…"}
      </span>
    </summary>
    {#if loadError}
      <p class="error" role="alert">{loadError}</p>
      <button type="button" class="btn btn-sm" onclick={() => void load()}>Retry</button>
    {:else if source}
      <p class="lead">
        Notes Build follows in every project where you turn on file instructions, after you review them.
        They are guidance, never permissions.
      </p>
      {#if source.path}
        <p class="path">Edit it in any editor at <code>{source.path}</code></p>
      {/if}
      <p class="sub">{source.reason}</p>
      {#if source.preview}
        <p class="meta">{source.chars.toLocaleString()} characters · revision <code>{source.digest.slice(0, 12)}</code></p>
        <pre class="preview" data-testid="global-instruction-file-preview">{source.preview}</pre>
      {/if}
      <div class="actions">
        {#if source.state === "absent"}
          <button type="button" class="btn btn-sm" disabled={busy} onclick={() => void act(() => contract.createGlobalInstructionFile(), "The starter file was not created")}>Create starter file</button>
        {/if}
        {#if source.state === "unreviewed" || source.state === "changed" || (source.state === "disabled" && source.preview)}
          <button type="button" class="btn btn-primary btn-sm" disabled={busy} onclick={() => void act(() => contract.reviewGlobalInstructionFile({ scope: "global", digest: source!.digest }), "Your global RAIKER.md was not approved")}>
            {source.state === "changed" ? "Approve this revision" : "Review and use"}
          </button>
        {/if}
        {#if source.state === "approved" || source.state === "unreviewed" || source.state === "changed"}
          <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => void act(() => contract.disableGlobalInstructionFile(), "Your global RAIKER.md was not turned off")}>Turn off</button>
        {/if}
        <button type="button" class="btn btn-ghost btn-sm" disabled={busy} onclick={() => void load()}>Read again</button>
      </div>
      {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
    {/if}
  </details>
</section>

<style>
  /* The same fold as Personalisation's *Layout & type*, so the page keeps one shape. */
  .tuning > summary {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    flex-wrap: wrap;
    cursor: pointer;
    list-style: none;
  }
  .tuning > summary::-webkit-details-marker { display: none; }
  .tuning > summary::before {
    content: "";
    width: 0; height: 0;
    border-inline-start: 5px solid var(--text-3);
    border-block: 4px solid transparent;
    transition: transform var(--motion-fast) var(--ease);
  }
  .tuning[open] > summary::before { transform: rotate(90deg); }
  .tuning > summary:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
  .summary-title { font-weight: 650; }
  .summary-hint { color: var(--text-2); font-size: var(--text-sm); }
  .lead, .sub { color: var(--text-2); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
  .path { font-size: var(--text-sm); color: var(--text-1); margin: var(--space-2) 0 0; overflow-wrap: anywhere; }
  .meta { color: var(--text-2); font-size: var(--text-xs); margin: var(--space-2) 0 0; font-variant-numeric: tabular-nums; }
  .preview {
    margin: var(--space-2) 0 0;
    padding: var(--space-2) var(--space-3);
    max-height: 12rem;
    overflow: auto;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-size: var(--text-sm);
    line-height: 1.5;
    background: var(--surface-raised);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    color: var(--text-1);
  }
  .actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); flex-wrap: wrap; }
  .error { color: var(--danger); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
</style>
