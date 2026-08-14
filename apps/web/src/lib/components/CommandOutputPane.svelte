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
  import Icon from "./Icon.svelte";

  let { sessionId = null }: { sessionId?: string | null } = $props();
  let open = $state(false);
  let command = $state("git status --short");
  let environment = $state<ExecutionEnvironment | null>(null);
  let runs = $state<CommandRunView[]>([]);
  let selectedId = $state<string | null>(null);
  let chunks = $state<CommandChunkView[]>([]);
  let receipt = $state<CommandReceiptView | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setInterval> | null = null;

  const selected = $derived(runs.find((run) => run.run_id === selectedId) ?? null);
  const terminal = $derived(
    selected !== null && ["succeeded", "failed", "timed_out", "cancelled", "contained", "lost"].includes(selected.state),
  );
  const output = $derived(chunks.map((chunk) => chunk.text).join(""));

  function reason(exc: unknown): string {
    if (exc instanceof ApiError) return humanize(exc.reasonCode ?? "command_request_failed");
    return exc instanceof Error ? exc.message : "Command request failed";
  }

  async function loadEnvironment() {
    try {
      const view = await api.executionEnvironments();
      environment = view.environments.find((item) => item.selected) ?? null;
    } catch { environment = null; }
  }

  async function refresh() {
    try {
      const view = await api.commandRuns(sessionId ?? "build_workspace");
      runs = view.runs;
      if (selectedId === null && runs.length > 0) selectedId = runs[0].run_id;
      if (selectedId !== null) {
        const outputView = await api.commandOutput(selectedId, 0);
        chunks = outputView.chunks;
        const current = runs.find((run) => run.run_id === selectedId);
        if (current?.receipt_digest) receipt = (await api.commandReceipt(selectedId)).receipt;
      }
      error = null;
    } catch (exc) { error = reason(exc); }
  }

  async function run() {
    if (command.trim() === "") return;
    busy = true;
    error = null;
    try {
      const result = await api.startCommand({
        session_id: sessionId ?? "build_workspace",
        command: command.trim(),
      });
      selectedId = result.run.run_id;
      chunks = [];
      receipt = null;
      open = true;
      await refresh();
    } catch (exc) {
      error = reason(exc);
      await refresh();
    } finally { busy = false; }
  }

  async function stop() {
    if (selectedId === null) return;
    busy = true;
    try { await api.stopCommand(selectedId); await refresh(); }
    catch (exc) { error = reason(exc); }
    finally { busy = false; }
  }

  function statusLabel(run: CommandRunView | null): string {
    if (run === null) return "Idle";
    return humanize(run.state);
  }

  onMount(() => {
    void loadEnvironment();
    void refresh();
    timer = setInterval(() => { if (open && selected && !terminal) void refresh(); }, 800);
    return () => { if (timer !== null) clearInterval(timer); };
  });
</script>

<section class="command-pane" class:expanded={open} aria-labelledby="command-pane-title">
  <button class="pane-toggle" type="button" onclick={() => (open = !open)} aria-expanded={open}>
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
        <span class:ready={selected !== null}><i></i>Policy</span>
        <b aria-hidden="true"></b>
        <span class:ready={selected !== null}><i></i>{statusLabel(selected)}</span>
        <b aria-hidden="true"></b>
        <span class:ready={receipt !== null}><i></i>Receipt</span>
      </div>

      <div class="command-row">
        <label for="governed-command" class="sr-only">Command arguments</label>
        <span class="prompt" aria-hidden="true">$</span>
        <input id="governed-command" bind:value={command} disabled={busy} onkeydown={(event) => {
          if (event.key === "Enter") { event.preventDefault(); void run(); }
        }} />
        <button class="btn btn-primary btn-sm" type="button" onclick={() => void run()} disabled={busy || command.trim() === "" || environment?.available === false}>
          <Icon name="play" size={13} /> Run
        </button>
        {#if selected && !terminal}
          <button class="btn btn-ghost btn-sm" type="button" onclick={() => void stop()} disabled={busy}>
            <Icon name="stop" size={13} /> Stop
          </button>
        {/if}
      </div>

      <div class="posture" role="status">
        <span><Icon name="shield" size={13} /> Selected environment is authoritative</span>
        <span>{environment?.kind === "local" ? "Argv only · no credential inheritance · no PTY · foreground" : "No host fallback"}</span>
      </div>

      <div class="output-shell" aria-live="polite">
        <div class="output-head">
          <span>{selected?.safe_display ?? "No command selected"}</span>
          {#if selected}<span>{selected.stdout_bytes + selected.stderr_bytes} bytes{selected.truncated ? " · truncated" : ""}</span>{/if}
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
            <div><dt>Completed</dt><dd>{receipt.completed_at}</dd></div>
          </dl>
        </details>
      {/if}
      {#if error}<p class="pane-error" role="alert">{error}</p>{/if}
    </div>
  {/if}
</section>

<style>
  .command-pane { margin: 0 1.5rem .7rem; border: 1px solid var(--border); border-radius: var(--r-lg); background: var(--surface); overflow: hidden; box-shadow: var(--shadow-sm); }
  .command-pane.expanded { border-color: color-mix(in srgb, var(--accent) 28%, var(--border)); }
  .pane-toggle { width: 100%; min-height: 48px; display: flex; align-items: center; gap: .7rem; padding: .55rem .8rem; border: 0; background: transparent; color: var(--text); text-align: left; cursor: pointer; }
  .pane-toggle:hover { background: var(--surface-2); }
  .terminal-mark { display: grid; place-items: center; width: 30px; height: 28px; border-radius: var(--r-sm); background: var(--text); color: var(--surface); font: 700 .72rem/1 var(--font-mono); }
  .pane-heading { display: grid; gap: .08rem; flex: 1; }
  .pane-heading strong { font-size: .8rem; letter-spacing: .01em; }
  .pane-heading small { color: var(--text-3); font-size: .68rem; }
  .chevron { color: var(--text-3); font-size: 1.1rem; }
  .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 12%, transparent); }
  .pane-body { padding: .15rem .8rem .8rem; border-top: 1px solid var(--border); }
  .receipt-rail { display: grid; grid-template-columns: auto 1fr auto 1fr auto 1fr auto; align-items: center; gap: .35rem; padding: .72rem 0; color: var(--text-3); font-size: .64rem; text-transform: uppercase; letter-spacing: .07em; }
  .receipt-rail span { display: flex; align-items: center; gap: .32rem; white-space: nowrap; }
  .receipt-rail i { width: 7px; height: 7px; border: 1px solid var(--border-strong); border-radius: 50%; background: var(--surface); }
  .receipt-rail span.ready { color: var(--text-2); }
  .receipt-rail span.ready i { border-color: var(--ok); background: var(--ok); }
  .receipt-rail b { height: 1px; background: var(--border); }
  .command-row { display: flex; align-items: center; gap: .45rem; padding: .42rem .5rem; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface-2); }
  .prompt { color: var(--accent); font: 700 .85rem var(--font-mono); }
  .command-row input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--text); font: .75rem/1.4 var(--font-mono); }
  .posture { display: flex; justify-content: space-between; gap: .8rem; padding: .48rem .1rem; color: var(--text-3); font-size: .66rem; }
  .posture span { display: inline-flex; align-items: center; gap: .28rem; }
  .output-shell { min-height: 112px; overflow: hidden; border: 1px solid color-mix(in srgb, var(--text) 18%, var(--border)); border-radius: var(--r-md); background: color-mix(in srgb, var(--text) 94%, #000); color: #e8e8e2; }
  .output-head { display: flex; justify-content: space-between; gap: .8rem; padding: .42rem .58rem; border-bottom: 1px solid #ffffff1a; color: #a9aaa4; font: .62rem var(--font-mono); }
  pre { margin: 0; min-height: 72px; max-height: 240px; overflow: auto; padding: .62rem; white-space: pre-wrap; word-break: break-word; font: .72rem/1.55 var(--font-mono); }
  .receipt-card { margin-top: .55rem; padding: .42rem .55rem; border: 1px solid var(--border); border-radius: var(--r-md); color: var(--text-2); font-size: .7rem; }
  .receipt-card summary { cursor: pointer; }
  .receipt-card code { color: var(--text-3); }
  dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .45rem; margin: .55rem 0 0; }
  dl div { min-width: 0; } dt { color: var(--text-3); font-size: .62rem; text-transform: uppercase; } dd { margin: .12rem 0 0; overflow: hidden; text-overflow: ellipsis; }
  .pane-error { margin: .55rem 0 0; color: var(--danger); font-size: .7rem; }
  @media (max-width: 720px) { .command-pane { margin-inline: .75rem; } .receipt-rail { grid-template-columns: repeat(4, 1fr); } .receipt-rail b { display: none; } .receipt-rail span { justify-content: center; } .posture { display: grid; } dl { grid-template-columns: repeat(2, 1fr); } }
  @media (prefers-reduced-motion: reduce) { .live-dot { box-shadow: none; } }
</style>
