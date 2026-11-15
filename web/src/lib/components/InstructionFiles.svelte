<script lang="ts">
  /**
   * RAIKER.md — a project's reviewed instruction files, on the project's page.
   *
   * Two files only: the owner's global RAIKER.md and the one at the project's
   * root. Turning file instructions on approves nothing: each file is read,
   * shown as Build would see it, and used only after the owner reviews that
   * exact revision. A changed file asks again. The text is guidance, never a
   * permission (docs/architecture/RAIKER_MD_INSTRUCTIONS.md).
   */
  import { failure } from "../errorCopy";
  import { ApiError } from "../api";
  import { knownReasonCopy } from "../reasonCodes";
  import { contract } from "../generated/apiContract";
  import type { InstructionFileSource, ProjectInstructionFilesView } from "../generated/apiContract";

  let { projectId }: { projectId: string } = $props();

  let view = $state<ProjectInstructionFilesView | null>(null);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let open = $state<Record<string, boolean>>({});
  let readSeq = 0;

  const STATE_WORD: Record<string, string> = {
    absent: "Not found",
    empty: "Empty",
    disabled: "Off",
    unreviewed: "Needs review",
    approved: "In use",
    changed: "Changed — needs review",
    unsafe: "Not read",
    unreadable: "Not read",
    invalid: "Not read",
    oversized: "Too long",
    root_unavailable: "Folder unavailable",
  };

  $effect(() => {
    const id = projectId;
    view = null;
    void load(id);
    return () => { readSeq += 1; };
  });

  async function load(id: string) {
    const seq = ++readSeq;
    loadError = null;
    try {
      const answer = await contract.getProjectInstructionFiles(id);
      if (seq === readSeq && id === projectId) view = answer;
    } catch (e) {
      if (seq !== readSeq || id !== projectId) return;
      loadError = failure(
        "File instructions could not be read",
        "Whether Build uses a RAIKER.md here is unconfirmed.",
        "Choose Retry file instructions.",
        e,
      );
    }
  }

  async function act(key: string, run: () => Promise<ProjectInstructionFilesView>, what: string) {
    busy = key;
    actionError = null;
    try {
      view = await run();
    } catch (e) {
      const code = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      actionError = failure(
        what,
        "Nothing was changed.",
        knownReasonCopy(code)?.remediation ?? "Choose Retry file instructions to read the files again.",
        e,
      );
      if (code === "instruction_file_changed_since_preview") void load(projectId);
    } finally {
      busy = null;
    }
  }

  const setEnabled = (enabled: boolean) =>
    act("enabled", () => contract.setProjectInstructionFiles(projectId, { enabled }), enabled ? "File instructions were not turned on" : "File instructions were not turned off");

  const review = (source: InstructionFileSource) =>
    act(`review-${source.scope}`, () => contract.reviewProjectInstructionFile(projectId, { scope: source.scope, digest: source.digest }), `${source.label} was not approved`);

  const disable = (source: InstructionFileSource) =>
    act(`disable-${source.scope}`, () => contract.disableProjectInstructionFile(projectId, { scope: source.scope }), `${source.label} was not turned off`);

  const reviewable = (source: InstructionFileSource) => source.state === "unreviewed" || source.state === "changed";
  const tone = (state: string) =>
    state === "approved" ? "ok" : state === "unreviewed" || state === "changed" ? "attention" : ["absent", "empty", "disabled"].includes(state) ? "quiet" : "warn";
</script>

<section class="files" aria-labelledby={`instruction-files-${projectId}`}>
  <div class="head">
    <h3 id={`instruction-files-${projectId}`} class="kicker">File instructions</h3>
    {#if view}
      <label class="switch">
        <input
          type="checkbox"
          role="switch"
          checked={view.enabled}
          disabled={busy !== null}
          onchange={(e) => void setEnabled((e.currentTarget as HTMLInputElement).checked)}
          data-testid="instruction-files-toggle"
        />
        <span>Use RAIKER.md in Build</span>
      </label>
    {/if}
  </div>
  {#if loadError}
    <p class="error" role="alert">{loadError}</p>
    <button type="button" class="btn btn-sm" onclick={() => void load(projectId)}>Retry file instructions</button>
  {:else if view === null}
    <p class="sub">Reading this project's RAIKER.md…</p>
  {:else}
    <p class="sub">
      {#if view.enabled}
        Build follows the revisions you reviewed. A file that changes waits for you again.
      {:else}
        Off. Build ignores any RAIKER.md here. Turning this on approves nothing by itself.
      {/if}
    </p>
    {#if view.enabled && view.needs_review}
      <p class="notice" role="status" data-testid="instruction-files-needs-review">
        Build turns in this project wait until you review the file below or turn this off.
      </p>
    {/if}
    <ul class="sources">
      {#each view.sources as source (source.scope)}
        <li class="source" data-testid={`instruction-file-${source.scope}`}>
          <div class="row">
            <span class="name">{source.label}</span>
            <span class={`state ${tone(source.state)}`} data-testid={`instruction-file-${source.scope}-state`}>{STATE_WORD[source.state] ?? source.state}</span>
          </div>
          <p class="sub">{source.reason}</p>
          {#if source.preview}
            <p class="meta">
              {source.chars.toLocaleString()} characters · revision <code>{source.digest.slice(0, 12)}</code>
            </p>
            {#if !reviewable(source)}
              <!-- A file waiting for review always shows its text: that is what is approved. -->
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                aria-expanded={open[source.scope] ?? false}
                onclick={() => (open = { ...open, [source.scope]: !(open[source.scope] ?? false) })}
              >{open[source.scope] ? "Hide text" : "Show text"}</button>
            {/if}
            {#if open[source.scope] || reviewable(source)}
              <pre class="preview" data-testid={`instruction-file-${source.scope}-preview`}>{source.preview}</pre>
            {/if}
          {/if}
          <div class="actions">
            {#if reviewable(source)}
              <button type="button" class="btn btn-primary btn-sm" disabled={busy !== null} onclick={() => void review(source)}>
                {source.state === "changed" ? "Approve this revision" : "Review and use"}
              </button>
            {/if}
            {#if source.state === "approved" || reviewable(source)}
              <button type="button" class="btn btn-ghost btn-sm" disabled={busy !== null} onclick={() => void disable(source)}>Turn off</button>
            {/if}
            {#if source.state === "disabled" && source.preview}
              <button type="button" class="btn btn-sm" disabled={busy !== null} onclick={() => void review(source)}>Review and use again</button>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
    {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
  {/if}
</section>

<style>
  .files { margin-top: var(--space-4); }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .switch {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-1);
  }
  .sub { color: var(--text-2); font-size: var(--text-sm); margin: var(--space-1) 0 0; }
  .meta { color: var(--text-2); font-size: var(--text-xs); margin: var(--space-1) 0; font-variant-numeric: tabular-nums; }
  .notice { margin: var(--space-2) 0 0; font-size: var(--text-sm); color: var(--text-1); }
  .sources { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: grid; gap: var(--space-3); }
  .source { border-top: 1px solid var(--border); padding-top: var(--space-2); }
  .row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-2); }
  .name { font-weight: 600; color: var(--text-1); font-size: var(--text-sm); }
  .state { font-size: var(--text-sm); color: var(--text-2); }
  .state.ok { color: var(--ok-text); }
  .state.attention { color: var(--warn-text); font-weight: 600; }
  .state.warn { color: var(--danger); }
  .preview {
    margin: var(--space-2) 0 0;
    padding: var(--space-2) var(--space-3);
    max-height: 14rem;
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
  .actions { display: flex; gap: var(--space-2); margin-top: var(--space-2); flex-wrap: wrap; }
  .actions:empty { display: none; }
  .error { color: var(--danger); font-size: var(--text-sm); margin: var(--space-2) 0 0; }
</style>
