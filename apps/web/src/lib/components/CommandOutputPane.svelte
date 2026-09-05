<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "../api";
  import type {
    CommandChunkView,
    CommandReceiptView,
    CommandRunView,
    ExecutionEnvironment,
  } from "../apiTypes";
  import { humanize } from "../format";
  import { boundaryLabel, posturaLine } from "../sandboxPosture";
  import Icon from "./Icon.svelte";
  import CredentialDeltaReview from "./CredentialDeltaReview.svelte";

  let {
    sessionId = null,
    visible = true,
    open = $bindable(false),
  }: {
    sessionId?: string | null;
    visible?: boolean;
    /**
     * B19 — bindable so `/terminal` in the Build composer opens the same pane
     * the header toggle opens. The slash command is a shortcut to this control,
     * not a second terminal.
     */
    open?: boolean;
  } = $props();
  let environment = $state<ExecutionEnvironment | null>(null);
  let runs = $state<CommandRunView[]>([]);
  let selectedId = $state<string | null>(null);
  let chunks = $state<CommandChunkView[]>([]);
  let receipt = $state<CommandReceiptView | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setInterval> | null = null;
  let refreshRequest = 0;

  const selected = $derived(runs.find((run) => run.run_id === selectedId) ?? null);
  const terminal = $derived(
    selected !== null && ["succeeded", "failed", "timed_out", "cancelled", "contained", "lost"].includes(selected.state),
  );
  const output = $derived(chunks.map((chunk) => chunk.text).join(""));
  // A failed run has to lead somewhere. Without this the owner sees a red
  // state and no way to reach either the receipt or the decision that allowed
  // the command to run at all.
  const failed = $derived(
    selected !== null && ["failed", "timed_out", "contained", "lost"].includes(selected.state),
  );

  function reason(exc: unknown): string {
    if (exc instanceof ApiError) return humanize(exc.reasonCode ?? "command_request_failed");
    return exc instanceof Error ? exc.message : "Command request failed";
  }

  /**
   * What actually ran this command (BUG-197).
   *
   * Empty for a run recorded before the column was written, and empty is shown
   * as nothing rather than as a guess — a run whose backend was never recorded
   * genuinely does not know, and inventing "native" for it would put a claim on
   * screen the receipt could contradict.
   */
  function backendLabel(run: CommandRunView | null): string {
    return run === null || run.backend === "" ? "" : humanize(run.backend);
  }

  async function loadEnvironment() {
    try {
      const view = await api.executionEnvironments();
      environment = view.environments.find((item) => item.selected) ?? null;
    } catch { environment = null; }
  }

  async function refresh(targetSessionId: string | null = sessionId) {
    const request = ++refreshRequest;
    try {
      const view = await api.commandRuns(targetSessionId ?? "build_workspace");
      if (request !== refreshRequest) return;
      runs = view.runs;
      const nextSelectedId =
        selectedId !== null && runs.some((run) => run.run_id === selectedId)
          ? selectedId
          : (runs[0]?.run_id ?? null);
      selectedId = nextSelectedId;
      chunks = [];
      receipt = null;
      if (nextSelectedId !== null) {
        const outputView = await api.commandOutput(nextSelectedId, 0);
        if (request !== refreshRequest) return;
        chunks = outputView.chunks;
        const current = runs.find((run) => run.run_id === nextSelectedId);
        if (current?.receipt_digest) {
          const receiptView = await api.commandReceipt(nextSelectedId);
          if (request !== refreshRequest) return;
          receipt = receiptView.receipt;
        }
      }
      error = null;
    } catch (exc) { error = reason(exc); }
  }

  async function select(runId: string | null) {
    if (runId === null) return;
    chunks = [];
    receipt = null;
    try {
      const outputView = await api.commandOutput(runId, 0);
      chunks = outputView.chunks;
      const current = runs.find((run) => run.run_id === runId);
      if (current?.receipt_digest) receipt = (await api.commandReceipt(runId)).receipt;
      error = null;
    } catch (exc) { error = reason(exc); }
  }

  async function stop() {
    if (selectedId === null) return;
    busy = true;
    try { await api.stopCommand(selectedId); await refresh(); }
    catch (exc) { error = reason(exc); }
    finally { busy = false; }
  }

  function toggle(): void {
    open = !open;
    if (open) {
      // Build remains mounted while the owner reviews an approval. Re-read on
      // open so a command executed on that other page appears immediately.
      void loadEnvironment();
      void refresh();
    }
  }

  function statusLabel(run: CommandRunView | null): string {
    if (run === null) return "Idle";
    return humanize(run.state);
  }

  $effect(() => {
    if (!visible) return;
    void loadEnvironment();
    void refresh(sessionId);
  });

  onMount(() => {
    timer = setInterval(() => { if (open && selected && !terminal) void refresh(); }, 800);
    return () => { if (timer !== null) clearInterval(timer); };
  });
</script>

<section class="command-pane" class:expanded={open} aria-labelledby="command-pane-title">
  <button class="pane-toggle" type="button" onclick={toggle} aria-expanded={open}>
    <span class="terminal-mark" aria-hidden="true">&gt;_</span>
    <span class="pane-heading">
      <strong id="command-pane-title">Governed terminal</strong>
      <small>{environment?.name ?? "Environment unavailable"} · {statusLabel(selected)}</small>
    </span>
    {#if selected && !terminal}<span class="live-dot" aria-label="Command active"></span>{/if}
    <span class="chevron" aria-hidden="true">{open ? "−" : "+"}</span>
  </button>

  {#if open}
    <div class="pane-body">
      <div class="receipt-rail" aria-label="Command governance path">
        <span class:ready={environment?.available}><i></i>Environment</span>
        <b aria-hidden="true"></b>
        <span class:ready={Boolean(selected?.authority_kind && selected?.authority_id)}><i></i>Authority</span>
        <b aria-hidden="true"></b>
        <span class:ready={selected !== null}><i></i>{statusLabel(selected)}</span>
        <b aria-hidden="true"></b>
        <span class:ready={receipt !== null}><i></i>Receipt</span>
      </div>

      <div class="command-row command-notice">
        <Icon name="shield" size="sm" />
        <span>Commands start through the governed agent path after an approval or bounded session grant.</span>
        {#if selected && !terminal}
          <button class="btn btn-ghost btn-sm" type="button" onclick={() => void stop()} disabled={busy}>
            <Icon name="stop" size="sm" /> Stop
          </button>
        {/if}
      </div>

      <div class="posture" role="status">
        <span><Icon name="shield" size="sm" /> {boundaryLabel(environment)}</span>
        <span>{posturaLine(environment)}</span>
      </div>

      {#if runs.length > 1}
        <!-- The pane keeps the owner's selection across refreshes, which is
             right — a new command must not yank the transcript they are
             reading. It also means the newest run is not always the one on
             screen, so the session's runs have to be reachable. -->
        <label class="run-picker">
          <span>Command</span>
          <select bind:value={selectedId} onchange={() => void select(selectedId)}>
            {#each runs as run}
              <option value={run.run_id}>{run.safe_display} · {humanize(run.state)}{backendLabel(run) ? ` · ${backendLabel(run)}` : ""}</option>
            {/each}
          </select>
        </label>
      {/if}

      <div class="output-shell" aria-live="polite">
        <div class="output-head">
          <span>{selected?.safe_display ?? "No command selected"}</span>
          {#if selected}
            <span>
              <!-- BUG-197 — the run names its own backend from the moment it
                   starts, so a command in flight already says where it is
                   running rather than waiting for its receipt to say so. -->
              {#if backendLabel(selected)}<b class="run-backend">{backendLabel(selected)}</b> · {/if}{selected.stdout_bytes + selected.stderr_bytes} bytes{selected.truncated ? " · truncated" : ""}
            </span>
          {/if}
        </div>
        <pre>{output || (selected ? `Command ${statusLabel(selected).toLowerCase()}…` : "Run a governed command to see redacted output here.")}</pre>
      </div>

      {#if receipt}
        <details class="receipt-card">
          <summary>Immutable receipt <code>{receipt.digest.slice(0, 12)}</code></summary>
          <dl>
            <div><dt>Outcome</dt><dd>{humanize(receipt.state)}</dd></div>
            <div><dt>Exit</dt><dd>{receipt.exit_code ?? "—"}</dd></div>
            <div><dt>Isolation</dt><dd>{String(receipt.evidence.backend ?? "recorded")}</dd></div>
            <div><dt>Authority</dt><dd>{String(selected?.authority_kind ?? "unverified")}</dd></div>
            <div><dt>Completed</dt><dd>{receipt.completed_at}</dd></div>
          </dl>
        </details>
      {/if}
      {#if selected}
        <CredentialDeltaReview runId={selected.run_id} profileId={selected.profile_id} />
      {/if}
      {#if selected && failed}
        <p class="failure-nav" role="status">
          <Icon name="warning" size="sm" />
          <span>
            {humanize(selected.termination_reason ?? selected.state)}{selected.exit_code !== null ? ` · exit ${selected.exit_code}` : ""}
          </span>
          <a href="#/approvals">Open the {selected.authority_kind || "authority"} that allowed it</a>
        </p>
      {/if}
      {#if error}<p class="pane-error" role="alert">{error}</p>{/if}
    </div>
  {/if}
</section>

<style>
  .command-pane { margin: 0 1.5rem .7rem; border: 1px solid var(--border); border-radius: var(--r-lg); background: var(--surface); overflow: hidden; box-shadow: var(--shadow-0); }
  .command-pane.expanded { border-color: color-mix(in srgb, var(--accent) 28%, var(--border)); }
  .pane-toggle { width: 100%; min-height: 48px; display: flex; align-items: center; gap: .7rem; padding: .55rem .8rem; border: 0; background: transparent; color: var(--text-1); text-align: left; cursor: pointer; }
  .pane-toggle:hover { background: var(--sunken); }
  .terminal-mark { display: grid; place-items: center; width: 30px; height: 28px; border-radius: var(--r-sm); background: var(--text-1); color: var(--surface); font: 700 var(--text-xs)/1 var(--font-mono); }
  .pane-heading { display: grid; gap: .08rem; flex: 1; }
  .pane-heading strong { font-size: var(--text-sm); letter-spacing: .01em; }
  .pane-heading small { color: var(--text-3); font-size: var(--text-2xs); }
  .chevron { color: var(--text-3); font-size: var(--text-base); }
  .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 12%, transparent); }
  .pane-body { padding: .15rem .8rem .8rem; border-top: 1px solid var(--border); }
  .receipt-rail { display: grid; grid-template-columns: auto 1fr auto 1fr auto 1fr auto; align-items: center; gap: .35rem; padding: .72rem 0; color: var(--text-3); font-size: var(--text-2xs); text-transform: uppercase; letter-spacing: .07em; }
  .receipt-rail span { display: flex; align-items: center; gap: .32rem; white-space: nowrap; }
  .receipt-rail i { width: 7px; height: 7px; border: 1px solid var(--border-strong); border-radius: 50%; background: var(--surface); }
  .receipt-rail span.ready { color: var(--text-2); }
  .receipt-rail span.ready i { border-color: var(--ok); background: var(--ok); }
  .receipt-rail b { height: 1px; background: var(--border); }
  .command-row { display: flex; align-items: center; gap: .45rem; padding: .42rem .5rem; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--sunken); }
  .command-notice { color: var(--text-2); font-size: var(--text-xs); }
  .posture { display: flex; justify-content: space-between; gap: .8rem; padding: .48rem .1rem; color: var(--text-3); font-size: var(--text-2xs); }
  .posture span { display: inline-flex; align-items: center; gap: .28rem; }
  .output-shell { min-height: 112px; overflow: hidden; border: 1px solid var(--term-border); border-radius: var(--r-md); background: var(--term-bg); color: var(--term-fg); color-scheme: dark; }
  .output-head { display: flex; justify-content: space-between; gap: .8rem; padding: .42rem .58rem; border-bottom: 1px solid var(--term-rule); color: var(--term-dim); font: var(--text-2xs) var(--font-mono); }
  .run-backend { color: var(--term-bright); font-weight: 600; }
  pre { margin: 0; min-height: 72px; max-height: 240px; overflow: auto; padding: .62rem; white-space: pre-wrap; word-break: break-word; font: var(--text-xs)/1.55 var(--font-mono); }
  .receipt-card { margin-top: .55rem; padding: .42rem .55rem; border: 1px solid var(--border); border-radius: var(--r-md); color: var(--text-2); font-size: var(--text-2xs); }
  .receipt-card summary { cursor: pointer; }
  .receipt-card code { color: var(--text-3); }
  dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .45rem; margin: .55rem 0 0; }
  dl div { min-width: 0; } dt { color: var(--text-3); font-size: var(--text-2xs); text-transform: uppercase; } dd { margin: .12rem 0 0; overflow: hidden; text-overflow: ellipsis; }
  .pane-error { margin: .55rem 0 0; color: var(--danger); font-size: var(--text-2xs); }
  .run-picker { display: flex; align-items: center; gap: .5rem; margin: .5rem 0 .35rem; color: var(--text-3); font-size: var(--text-2xs); }
  .run-picker select { flex: 1; min-width: 0; font-family: var(--font-mono); font-size: var(--text-2xs); }
  .failure-nav { display: flex; align-items: center; gap: .45rem; flex-wrap: wrap; margin: .55rem 0 0; padding: .42rem .5rem; border: 1px solid color-mix(in srgb, var(--danger) 35%, var(--border)); border-radius: var(--r-md); background: color-mix(in srgb, var(--danger) 6%, transparent); color: var(--text-2); font-size: var(--text-2xs); }
  .failure-nav a { margin-left: auto; color: var(--accent); }
  @media (max-width: 720px) { .command-pane { margin-inline: .75rem; } .receipt-rail { grid-template-columns: repeat(4, 1fr); } .receipt-rail b { display: none; } .receipt-rail span { justify-content: center; } .posture { display: grid; } dl { grid-template-columns: repeat(2, 1fr); } }
  @media (prefers-reduced-motion: reduce) { .live-dot { box-shadow: none; } }
</style>
