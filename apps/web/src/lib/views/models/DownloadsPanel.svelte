<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../api";
  import type { ModelOperation, PartialFiles } from "../../apiTypes";
  import { formatBytes } from "../../composerAttachments.svelte";
  let items = $state<ModelOperation[]>([]);
  let error = $state<string | null>(null);
  // BUG-75 — deleting bytes from disk is its own decision, so it takes its own
  // confirmation and names the exact approved path and size first. `Clear
  // record` stays metadata-only and is deliberately not merged into it.
  let deleting = $state<{ operationId: string; summary: PartialFiles } | null>(null);
  let deleteError = $state<string | null>(null);
  const terminal = (state: string) =>
    ["complete", "failed", "cancelled"].includes(state);
  // GCR-21 — the states a retry may really start from. It used to be offered on
  // `failed` alone while the API accepted it from any state at all, so a job the
  // owner had cancelled could not be started again from here and a *running*
  // one could be started twice from anywhere else. Both halves now say the same
  // thing: a terminal, retryable job, and nothing else.
  const retryableNow = (item: ModelOperation) =>
    item.retryable && ["failed", "cancelled"].includes(item.state);
  async function load() {
    try {
      items = (await api.modelOperations()).items;
      error = null;
    } catch {
      error = "Could not load model activity.";
    }
  }
  async function cancel(id: string) {
    await api.cancelModelOperation(id);
    await load();
  }
  async function retry(id: string) {
    try {
      await api.retryModelOperation(id);
      error = null;
    } catch {
      error = "That job could not be started again. Its original parameters were not recorded.";
    }
    await load();
  }

  async function askDeletePartial(id: string) {
    deleteError = null;
    try {
      deleting = { operationId: id, summary: await api.partialFiles(id) };
    } catch {
      deleteError = "Could not read what this job left behind.";
    }
  }

  async function confirmDeletePartial() {
    if (deleting === null) return;
    try {
      await api.deletePartialFiles(deleting.operationId);
      deleting = null;
      deleteError = null;
    } catch {
      deleteError = "That path is not inside your approved model library, so nothing was deleted.";
    }
    await load();
  }
  async function cleanup(id: string) {
    await api.cleanupModelOperation(id);
    await load();
  }
  // A once-a-second poll is what a running download needs and what an idle
  // panel wastes: on its own it spends half the API's per-minute rate budget,
  // and an owner who leaves Activity open then sees unrelated reads throttled.
  // The cadence follows the work instead — fast while something is running,
  // slow when everything has reached a terminal state.
  const ACTIVE_POLL_MS = 2_000;
  const IDLE_POLL_MS = 15_000;
  let timer: number | undefined;

  function schedule() {
    const anyRunning = items.some((item) => !terminal(item.state));
    timer = window.setTimeout(async () => {
      if (document.visibilityState === "visible") await load();
      schedule();
    }, anyRunning ? ACTIVE_POLL_MS : IDLE_POLL_MS);
  }

  onMount(() => {
    void load().then(schedule);
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
    };
  });
</script>

<section class="activity" aria-labelledby="activity-title">
  <header>
    <div>
      <p class="eyebrow">Durable operations</p>
      <h2 id="activity-title">Downloads and model jobs</h2>
      <p>
        Jobs survive navigation and interrupted app sessions. Failed work is
        never silently retried.
      </p>
    </div>
    <button class="btn btn-ghost" type="button" onclick={load}>Refresh</button>
  </header>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if deleting !== null}
    <div class="confirm" role="alertdialog" aria-labelledby="delete-partial-title">
      <h3 id="delete-partial-title">Delete the files this job left behind?</h3>
      {#if deleting.summary.exists && deleting.summary.paths.length > 0}
        <!--
          GCR-19 — every path, not "the destination". A conversion writes into
          the model-library folder the owner chose, which holds the models
          earlier conversions succeeded at; naming the folder here would have
          been asking them to confirm the deletion of all of it.
        -->
        <p>
          {deleting.summary.file_count}
          {deleting.summary.file_count === 1 ? "file" : "files"},
          {formatBytes(deleting.summary.bytes)}. Only what this job created is removed —
          nothing else in your model library. This cannot be undone.
        </p>
        <ul class="paths">
          {#each deleting.summary.paths as path (path)}<li><code>{path}</code></li>{/each}
        </ul>
      {:else}
        <p>Nothing is left on disk for this job.</p>
      {/if}
      {#if deleteError}<p class="error" role="alert">{deleteError}</p>{/if}
      <div class="actions">
        <button
          class="btn btn-sm"
          type="button"
          disabled={!deleting.summary.exists}
          onclick={() => void confirmDeletePartial()}>Delete files</button
        >
        <button class="btn btn-ghost btn-sm" type="button" onclick={() => (deleting = null)}
          >Keep them</button
        >
      </div>
    </div>
  {/if}
  {#if items.length === 0}<div class="empty">
      <strong>No model activity yet</strong><span
        >Downloads, conversions, runtime installs, pulls, and deployments appear
        here.</span
      >
    </div>
  {:else}<div class="timeline">
      {#each items as item (item.operation_id)}<article>
          <div
            class="rail"
            class:done={item.state === "complete"}
            class:failed={item.state === "failed"}
          ></div>
          <div class="job">
            <div class="job-head">
              <div>
                <span class="kind">{item.kind}</span>
                <h3>{item.target}</h3>
              </div>
              <strong class:bad={item.state === "failed"}
                >{item.state.replaceAll("_", " ")}</strong
              >
            </div>
            <p>
              {item.phase.replaceAll("_", " ")}{#if item.error_code}
                · {item.error_code.replaceAll("_", " ")}{/if}
            </p>
            {#if item.progress_percent !== null}<div
                class="progress"
                aria-label={`${item.progress_percent}% complete`}
              >
                <span style={`width:${item.progress_percent}%`}></span>
              </div>{/if}
            <div class="actions">
              {#if !terminal(item.state)}<button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  onclick={() => void cancel(item.operation_id)}>Cancel</button
                >{:else if retryableNow(item)}<button
                  class="btn btn-sm"
                  type="button"
                  onclick={() => void retry(item.operation_id)}>Retry</button
                >{/if}{#if item.partial_files_present}<button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  onclick={() => void askDeletePartial(item.operation_id)}
                  >Delete partial files</button
                >{/if}{#if terminal(item.state)}<button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  onclick={() => void cleanup(item.operation_id)}
                  >Clear record</button
                >{/if}
            </div>
            {#if ["failed", "cancelled"].includes(item.state) && !item.retryable}
              <p class="note">
                This job cannot be started again — it has no recorded parameters to run from.
                Start it fresh from its own page.
              </p>
            {/if}
          </div>
        </article>{/each}
    </div>{/if}
</section>

<style>
  .activity {
    --text-muted: var(--text-2);
    display: grid;
    gap: 18px;
  }
  .activity > header {
    display: flex;
    justify-content: space-between;
    gap: 20px;
  }
  .activity h2 {
    margin: 2px 0 6px;
  }
  .activity header p {
    margin: 0;
    color: var(--text-muted);
  }
  .empty {
    display: grid;
    place-items: center;
    gap: 6px;
    padding: 64px 20px;
    border: 1px dashed var(--border);
    border-radius: 14px;
    color: var(--text-muted);
  }
  .timeline {
    display: grid;
  }
  .timeline article {
    display: grid;
    grid-template-columns: 18px 1fr;
    gap: 12px;
  }
  .rail {
    width: 3px;
    height: 100%;
    min-height: 110px;
    background: var(--border);
    position: relative;
  }
  .rail:before {
    content: "";
    position: absolute;
    left: -5px;
    top: 5px;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: var(--warn);
    border: 3px solid var(--surface);
  }
  .rail.done:before {
    background: var(--success);
  }
  .rail.failed:before {
    background: var(--danger);
  }
  .job {
    padding: 0 0 24px;
  }
  .job-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .job h3 {
    margin: 3px 0;
  }
  .job p {
    color: var(--text-muted);
    margin: 5px 0;
  }
  .kind {
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: var(--text-2xs);
    font-weight: 750;
  }
  .bad {
    color: var(--danger);
  }
  .progress {
    height: 5px;
    background: var(--border);
    margin: 12px 0;
    border-radius: 4px;
    overflow: hidden;
  }
  .progress span {
    display: block;
    height: 100%;
    background: var(--accent);
  }
  .actions {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }
  .note {
    margin: 8px 0 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
  .confirm {
    display: grid;
    gap: 8px;
    padding: 14px 16px;
    border: 1px solid var(--warn-border);
    border-radius: 12px;
    background: var(--warn-soft);
  }
  .confirm h3 {
    margin: 0;
  }
  .confirm p {
    margin: 0;
  }
  .confirm code {
    word-break: break-all;
  }
  .paths {
    margin: 0;
    padding-left: 20px;
    display: grid;
    gap: 4px;
    max-height: 180px;
    overflow-y: auto;
  }
</style>
