<script lang="ts">
  /**
   * B18 — the rewind funnel, in one component, wherever the rewind is asked for.
   *
   * The executor, the capability and the route have existed since Workstream B:
   * `POST /api/checkpoints/{id}/restore` raises an ordinary approval for
   * `checkpoint_restore_execution`, and a cross-principal restore takes the
   * human-only lifecycle instead. What did not exist was a way to reach it from
   * the place the work happens. Checkpoints is a *record* of the run; the turn
   * that broke something is in the transcript, and asking the owner to copy a
   * checkpoint id into another route to undo it is the same defect this product
   * keeps finding: a capability built and never routed.
   *
   * So the funnel lives here rather than in the Checkpoints page, and Chat,
   * Build and Checkpoints all open the same one. A rewind therefore reads
   * identically wherever it is asked for, exactly as a diff does since
   * FIXED-312.
   *
   * Three properties this keeps, and they are the reason it is a funnel rather
   * than a button:
   *
   * * **Reading the plan changes nothing.** The preflight is server-computed
   *   metadata: which files would be rewritten, deleted, or skipped, and which
   *   were last touched by another principal.
   * * **This never performs a restore.** It asks for one. The server recomputes
   *   its own plan — a caller cannot name the files — records the proposal and
   *   returns an approval id.
   * * **The escalation is stated before the ask, not after.** A rewind over
   *   another principal's work is critical and says so here.
   */
  import Icon from "./Icon.svelte";
  import PageState from "./PageState.svelte";
  import SidePanel from "./SidePanel.svelte";
  import { api, ApiError } from "../api";
  import type { RestorePlan, RestoreRequestResult } from "../apiTypes";
  import { shortId } from "../format";

  let {
    checkpointId = null,
    subtitle = null,
    scrollIntoViewOnOpen = false,
    onclose,
  }: {
    /** The checkpoint to rewind to, or null when the panel is closed. */
    checkpointId?: string | null;
    subtitle?: string | null;
    scrollIntoViewOnOpen?: boolean;
    onclose: () => void;
  } = $props();

  let plan = $state<RestorePlan | null>(null);
  let planError = $state<string | null>(null);
  let planBusy = $state(false);
  let acknowledged = $state(false);
  let requestBusy = $state(false);
  let requested = $state<RestoreRequestResult | null>(null);
  let requestError = $state<string | null>(null);
  let loadedFor: string | null = null;

  const escalates = $derived(plan?.touches_other_principal === true);
  const nothingToRestore = $derived(
    plan !== null && plan.restore_content_count + plan.delete_count === 0,
  );

  // One read per checkpoint the panel is opened on. Re-opening the same
  // checkpoint after closing recomputes it, because the workspace may have
  // moved on since — a stale plan is the one thing this surface must not show.
  $effect(() => {
    const id = checkpointId;
    if (id === null) {
      loadedFor = null;
      plan = null;
      planError = null;
      acknowledged = false;
      requested = null;
      requestError = null;
      return;
    }
    if (id === loadedFor) return;
    loadedFor = id;
    plan = null;
    planError = null;
    acknowledged = false;
    requested = null;
    requestError = null;
    planBusy = true;
    void (async () => {
      try {
        plan = await api.checkpointRestorePlan(id);
      } catch (e) {
        planError =
          e instanceof ApiError
            ? `Could not compute the restore plan (${e.status}).`
            : "Could not compute the restore plan.";
      } finally {
        planBusy = false;
      }
    })();
  });

  async function requestRestore() {
    if (checkpointId === null || requestBusy) return;
    requestBusy = true;
    requestError = null;
    try {
      requested = await api.requestCheckpointRestore(checkpointId);
    } catch (e) {
      requestError =
        e instanceof ApiError
          ? `Could not raise the approval (${e.status}).`
          : "Could not raise the approval.";
    } finally {
      requestBusy = false;
    }
  }

  function opLabel(op: string): string {
    if (op === "restore_content") return "Rewrite to its checkpoint state";
    if (op === "delete") return "Delete — it did not exist at the checkpoint";
    return "Skipped — too large to have been captured, so it cannot be rewound";
  }
</script>

<SidePanel
  open={checkpointId !== null}
  title="Rewind preflight"
  subtitle={subtitle ?? (checkpointId ? `Checkpoint ${shortId(checkpointId)}` : null)}
  {onclose}
  {scrollIntoViewOnOpen}
>
  {#if planBusy}
    <PageState state="loading" title="Computing what a rewind would change…" />
  {:else if planError}
    <PageState state="error" title="Preflight unavailable" detail={planError} />
  {:else if plan}
    <p class="preflight-lead">
      Rewinding puts every workspace file changed after this point back as it was. This preview is
      computed from stored metadata and changed nothing.
    </p>
    <div class="impact">
      <span><strong>{plan.restore_content_count}</strong> to rewrite</span>
      <span><strong>{plan.delete_count}</strong> to delete</span>
      <span><strong>{plan.skip_count}</strong> skipped</span>
      <span><strong>{plan.changed_count}</strong> changed since</span>
    </div>

    <!-- Nothing to rewind is an answer, not a form to fill in. The impact
         list, the reminders and the ask are all about a change that would be
         made; when there is none, none of them is worth reading. -->
    {#if nothingToRestore}
      <p class="quiet">
        No captured file changes after this point, so a rewind would change nothing.
      </p>
    {:else}
      <ul class="affected">
        {#each plan.files as file (file.workspace_path)}
          <li class:changed={file.changed}>
            <span class="path mono">{file.workspace_path}</span>
            <span class="op">{opLabel(file.op)}</span>
            {#if file.changed_by_other_principal}
              <span class="escalation">Last changed by a different principal</span>
            {/if}
          </li>
        {/each}
      </ul>

      {#if escalates}
        <div class="notice notice-danger" role="alert">
          <Icon name="warning" size="md" />
          <span>
            This would overwrite work last changed by a different principal — a cross-principal
            escalation, so only a live human can approve it.
          </span>
        </div>
      {/if}

      <div class="undo-facts">
        <h3>Before you ask for this</h3>
        <ul>
          <li>The rewind itself is captured, so it can be rewound the same way.</li>
          <li>Skipped files are left as they are — they were never captured.</li>
          <li>
            Every step is written to the append-only record.
            <a href={`#/observe?tab=activity&session=${encodeURIComponent(plan.session_id)}`}
              >Open this session's audit log</a
            >
          </li>
        </ul>
      </div>

      {#if requested}
        <div class="notice notice-ok" role="status">
          <Icon name="check" size="md" />
          <span>
            Raised as approval <span class="mono">{shortId(requested.approval_id)}</span>. Nothing
            has changed yet.
            {#if requested.critical}
              It is critical, so only a live human can resolve it and you will be asked to
              re-authenticate.
            {/if}
            <a href="#/approvals">Open Approvals</a>
          </span>
        </div>
      {:else}
        {#if requestError}
          <p class="notice notice-danger" role="alert">{requestError}</p>
        {/if}
        <label class="ack">
          <input type="checkbox" bind:checked={acknowledged} />
          I have read what this would change.
        </label>
        <button
          type="button"
          class="btn btn-primary"
          onclick={requestRestore}
          disabled={!acknowledged || requestBusy}
        >
          {requestBusy ? "Raising approval…" : "Request this rewind"}
        </button>
        <p class="handoff" class:ready={acknowledged}>
          {acknowledged
            ? "This raises a governed approval. The rewind runs only once you approve it, and it re-passes its capability gate, policy review and posture check then."
            : "Confirm you have read the impact above before requesting the rewind."}
        </p>
      {/if}
    {/if}
    {#if !nothingToRestore}
      <p class="quiet">This panel never performs a rewind. It asks for one; a human decision runs it.</p>
    {/if}
  {/if}
</SidePanel>

<style>
  .preflight-lead {
    margin: 0;
    color: var(--text-2);
  }
  .impact {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    font-size: var(--text-sm);
    color: var(--text-2);
  }
  .impact strong {
    font-size: var(--text-base);
    font-variant-numeric: tabular-nums;
  }
  .affected {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
    max-height: 16rem;
    overflow: auto;
  }
  .affected li {
    display: grid;
    gap: 0.1rem;
    border-left: 2px solid var(--border);
    padding: 0.2rem 0 0.2rem 0.55rem;
  }
  .affected li.changed {
    border-left-color: var(--warn);
  }
  .path {
    overflow-wrap: anywhere;
    font-size: var(--text-sm);
  }
  .op {
    color: var(--text-3);
    font-size: var(--text-xs);
  }
  .escalation {
    color: var(--danger);
    font-size: var(--text-xs);
    font-weight: 650;
  }
  .undo-facts h3 {
    margin: 0 0 0.3rem;
    font-size: var(--text-sm);
  }
  .undo-facts ul {
    margin: 0;
    padding-left: 1.1rem;
    color: var(--text-2);
    font-size: var(--text-sm);
    display: grid;
    gap: 0.2rem;
  }
  .ack {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .handoff {
    margin: 0;
    color: var(--text-3);
    font-size: var(--text-sm);
  }
  .handoff.ready {
    color: var(--text-1);
  }
  .quiet {
    color: var(--text-3);
    font-size: var(--text-sm);
    margin: 0;
  }
</style>
