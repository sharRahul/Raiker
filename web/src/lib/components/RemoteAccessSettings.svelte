<script lang="ts">
  /**
   * BUG-347 / BUG-358 — Settings → Security → Remote access.
   *
   * Rows first (state, connection, two-step sign-in, HTTPS), one action each.
   * Changing it is a guided dialog: choose how other devices reach Raiker,
   * fill in only what that needs (advanced fields stay folded), let the server
   * check it, review what it exposes and confirm with a fresh code. The change
   * opens on the next start; until the running host reports it, nothing here
   * says it is on. Turning it off is one press, from any signed-in device, and
   * takes effect at once.
   */
  import { api, ApiError } from "../api";
  import { askConfirm } from "../confirm.svelte";
  import { relativeTime } from "../format";
  import type { RemoteAccessCheckView, RemoteAccessStatusView } from "../generated/apiContract";
  import {
    MODE_CHOICES,
    configFrom,
    connectionLabel,
    eventLabel,
    exposureSentence,
    formFrom,
    httpsLabel,
    mfaReadiness,
    modeLabel,
    proxyExample,
    stateLabel,
    stateTone,
    withFreshMfa,
    type RemoteForm,
  } from "../remoteAccess";
  import FormDialog from "./FormDialog.svelte";

  let { onopenmfa }: { onopenmfa?: () => void } = $props();

  let status = $state<RemoteAccessStatusView | null>(null);
  let loadError = $state<string | null>(null);
  let panel = $state<"configure" | "details" | null>(null);
  let step = $state<"choose" | "details" | "review" | "done">("choose");
  let form = $state<RemoteForm>(formFrom({ mode: "local", proxy_kind: "port", proxy_port: null, proxy_socket: null, private_host: null, private_port: null, tls_cert: null, tls_key: null }));
  let checks = $state<RemoteAccessCheckView[]>([]);
  let checkedOk = $state(false);
  let busy = $state(false);
  let problem = $state<string | null>(null);
  let confirmExposure = $state(false);
  let password = $state("");
  let code = $state("");
  let restarting = $state(false);
  let notice = $state<string | null>(null);

  async function load() {
    try {
      status = await api.remoteAccess();
      loadError = null;
    } catch {
      loadError = "Remote access status could not be read. Nothing about it has changed.";
    }
  }

  function reasonText(error: unknown, fallback: string): string {
    if (error instanceof ApiError) {
      switch (error.reasonCode) {
        case "fresh_mfa_required":
          return "Enter your password and a current code from your authenticator.";
        case "loopback_only":
          return "Remote access can be changed only on the computer Raiker runs on.";
        case "remote_access_set_by_start_options":
          return "Remote access is set by the options Raiker was started with. Change them where Raiker is started.";
        case "remote_access_unconfirmed":
          return "Confirm that you understand who will be able to reach Raiker.";
        case "mfa_required":
          return "Turn on two-step sign-in first.";
        case "nothing_to_roll_back":
          return "There is no earlier setting to go back to.";
      }
      if (error.status === 401) return "That password or code was not accepted.";
      if (error.status === 422 && error.reasonCode) return `The setting did not pass its checks (${error.reasonCode}). Check it again.`;
    }
    return fallback;
  }

  function openConfigure() {
    if (!status) return;
    form = formFrom(status.desired.mode === "local" ? { ...status.desired, mode: "proxy" } : status.desired);
    if (status.platform === "windows") form.proxyKind = "port";
    step = "choose";
    checks = [];
    checkedOk = false;
    problem = null;
    confirmExposure = false;
    password = "";
    code = "";
    notice = null;
    panel = "configure";
  }

  async function runChecks(): Promise<boolean> {
    busy = true;
    problem = null;
    try {
      const answer = await api.checkRemoteAccess(configFrom(form));
      checks = answer.checks;
      checkedOk = answer.ok;
      return answer.ok;
    } catch (error) {
      problem = reasonText(error, "The setting could not be checked. Nothing was saved.");
      return false;
    } finally {
      busy = false;
    }
  }

  async function next() {
    if (step === "choose") {
      if (form.mode === "local") {
        // Choosing this device only is turning it off, which needs no code.
        panel = null;
        await turnOff();
        return;
      }
      step = "details";
      return;
    }
    if (step === "details" && (await runChecks())) step = "review";
  }

  async function apply() {
    busy = true;
    problem = null;
    try {
      status = await withFreshMfa(password, code, () => api.applyRemoteAccess(configFrom(form), confirmExposure));
      step = "done";
      password = "";
      code = "";
    } catch (error) {
      problem = reasonText(error, "Remote access was not changed.");
    } finally {
      busy = false;
    }
  }

  async function restartNow() {
    if (!status) return;
    const yes = await askConfirm({
      title: "Restart Raiker now?",
      body: "Raiker stops for a few seconds and starts again with the new remote-access setting. Work in progress reaches a safe point first.",
      confirmLabel: "Restart",
    });
    if (!yes) return;
    restarting = true;
    try {
      await api.restartHost(true);
    } catch (error) {
      restarting = false;
      problem = reasonText(error, "Raiker could not restart itself. Quit it and open it again to apply the change.");
      return;
    }
    // The host is gone for a moment; ask again until the running host answers
    // with its own account of what is open.
    const deadline = Date.now() + 90_000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        status = await api.remoteAccess();
        restarting = false;
        notice = status.restart_required
          ? "Raiker restarted, but the new setting is not open yet. See the connection details for why."
          : "Raiker restarted with the new setting.";
        return;
      } catch {
        // still starting
      }
    }
    restarting = false;
    problem = "Raiker did not come back within a minute and a half. Check that it is running.";
  }

  async function turnOff() {
    const yes = await askConfirm({
      title: "Turn off remote access?",
      body: "Other devices are refused from now on, and their sessions stop working. This computer is not affected.",
      confirmLabel: "Turn off",
      danger: true,
    });
    if (!yes) return;
    busy = true;
    try {
      status = await api.disableRemoteAccess();
      notice = status.active.refusing
        ? "Remote access is off. Other devices are refused now; the listener closes when Raiker next restarts."
        : "Remote access is off.";
    } catch (error) {
      notice = reasonText(error, "Remote access could not be turned off. Try again.");
    } finally {
      busy = false;
    }
  }

  async function rollBack() {
    busy = true;
    problem = null;
    try {
      status = await withFreshMfa(password, code, () => api.rollbackRemoteAccess());
      password = "";
      code = "";
      notice = "The previous setting is back. It opens when Raiker restarts.";
    } catch (error) {
      problem = reasonText(error, "The previous setting was not restored.");
    } finally {
      busy = false;
    }
  }

  const readiness = $derived(status ? mfaReadiness(status) : null);
  const remoteOn = $derived(status !== null && (status.desired.mode !== "local" || (status.active.address !== null && !status.active.refusing)));
  const visibleChecks = $derived(checks.filter((check) => !check.ok || check.severity !== "error"));

  load();
</script>

<section class="card" aria-labelledby="security-remote-h" data-testid="remote-access">
  <h2 id="security-remote-h">Remote access</h2>
  {#if loadError}
    <p class="notice notice-danger" role="alert">{loadError}</p>
  {:else if status === null}
    <p class="sub" role="status">Reading remote access…</p>
  {:else}
    {#if notice && panel === null}<p class="notice notice-ok" role="status">{notice}</p>{/if}
    <div class="setting-row">
      <h3>Remote access</h3>
      <span class="setting-value">
        <span class="state state-{stateTone(status.state)}" data-testid="remote-state">{stateLabel(status)}</span>
      </span>
      <span class="row-actions">
        {#if status.can_configure}
          <button type="button" class="btn btn-sm" onclick={openConfigure}>{status.desired.mode === "local" ? "Set up" : "Change"}</button>
        {/if}
        {#if remoteOn}
          <button type="button" class="btn btn-sm btn-danger" disabled={busy} onclick={turnOff}>Turn off</button>
        {/if}
      </span>
    </div>
    <div class="setting-row">
      <h3>Connection</h3>
      <span class="setting-value" data-testid="remote-connection">{connectionLabel(status)}</span>
      <button type="button" class="btn btn-sm" onclick={() => { problem = null; password = ""; code = ""; panel = "details"; }}>Details</button>
    </div>
    <div class="setting-row">
      <h3>Two-step sign-in</h3>
      <span class="setting-value"><span class="state state-{readiness?.tone}">{readiness?.label}</span>{#if !status.mfa.ready} <span class="sub">— needed before other devices can reach Raiker</span>{/if}</span>
      {#if onopenmfa}<button type="button" class="btn btn-sm" onclick={onopenmfa}>{status.mfa.enrolled ? "Manage" : "Turn on"}</button>{/if}
    </div>
    <div class="setting-row">
      <h3>HTTPS</h3>
      <span class="setting-value">{httpsLabel(status.https)}</span>
      <span></span>
    </div>
    {#each status.problems as item (item.code)}
      <p class="problem" role="alert" data-testid="remote-problem">{item.message}</p>
    {/each}
    {#if !status.can_configure && status.active.source === "start_options"}
      <p class="sub small">Set by the options Raiker was started with, so it is changed where Raiker is started.</p>
    {:else if !status.can_configure}
      <p class="sub small">Remote access is changed on the computer Raiker runs on. You can turn it off from here.</p>
    {/if}
  {/if}
</section>

{#if panel === "configure" && status}
  <FormDialog title="Remote access" onclose={() => (panel = null)}>
    {#if step === "choose"}
      <p class="sub">How should your other devices reach Raiker?</p>
      <div class="choices" role="radiogroup" aria-label="Connection method">
        {#each MODE_CHOICES as choice (choice.mode)}
          <label class="choice" class:selected={form.mode === choice.mode}>
            <input type="radio" name="remote-mode" value={choice.mode} bind:group={form.mode} />
            <span><strong>{choice.label}</strong><span class="sub">{choice.detail}</span></span>
          </label>
        {/each}
      </div>
      {#if form.mode !== "local"}
        <ul class="requirements" aria-label="What this needs">
          <li class:missing={!status.mfa.ready}>
            {status.mfa.ready ? "Two-step sign-in is on." : "Two-step sign-in must be on for every account."}
            {#if !status.mfa.ready && onopenmfa}<button type="button" class="link" onclick={() => { panel = null; onopenmfa?.(); }}>Turn it on</button>{/if}
          </li>
          <li>Every sign-in from another device needs your password and a code from your authenticator.</li>
          <li>Raiker answers other devices only over HTTPS.</li>
        </ul>
      {/if}
      <div class="actions">
        <button type="button" class="btn btn-primary" disabled={form.mode !== "local" && !status.mfa.ready} onclick={next}>Continue</button>
      </div>
    {:else if step === "details"}
      {#if form.mode === "private"}
        <p class="sub">Raiker serves HTTPS on this computer's address on your private network or VPN. It never listens on a public address.</p>
        <label>
          This computer's private address
          <input type="text" bind:value={form.privateHost} placeholder="100.101.102.103" autocomplete="off" spellcheck="false" />
        </label>
        <label>
          Certificate file (PEM)
          <input type="text" bind:value={form.tlsCert} placeholder="/home/you/raiker.crt" autocomplete="off" spellcheck="false" />
        </label>
        <label>
          Private key file (PEM)
          <input type="text" bind:value={form.tlsKey} placeholder="/home/you/raiker.key" autocomplete="off" spellcheck="false" />
        </label>
        <details class="advanced">
          <summary>Advanced</summary>
          <label>
            Port
            <input type="text" inputmode="numeric" bind:value={form.privatePort} />
          </label>
        </details>
      {:else}
        <p class="sub">Raiker opens a listener for your proxy. Point the proxy there.</p>
        <p class="warning" role="note">
          Never point the proxy at {status.local_listener}. That is Raiker's listener for this computer, and it refuses
          anything a proxy sends.
        </p>
        <details class="advanced" open={form.proxyKind === "socket"}>
          <summary>Advanced</summary>
          {#if status.platform !== "windows"}
            <fieldset class="kind">
              <legend>Listener</legend>
              <label class="inline"><input type="radio" name="proxy-kind" value="port" bind:group={form.proxyKind} /> A port on this computer</label>
              <label class="inline"><input type="radio" name="proxy-kind" value="socket" bind:group={form.proxyKind} /> A Unix socket</label>
            </fieldset>
          {/if}
          {#if form.proxyKind === "socket"}
            <label>
              Socket path
              <input type="text" bind:value={form.proxySocket} placeholder="/run/raiker/proxy.sock" autocomplete="off" spellcheck="false" />
            </label>
          {:else}
            <label>
              Port on 127.0.0.1
              <input type="text" inputmode="numeric" bind:value={form.proxyPort} />
            </label>
          {/if}
        </details>
        <details class="advanced">
          <summary>Example proxy configuration (Caddy)</summary>
          <pre class="example">{proxyExample(form)}</pre>
        </details>
      {/if}
      {#if visibleChecks.length > 0}
        <ul class="checks" aria-label="Checks">
          {#each visibleChecks as check (check.code + check.message)}
            <li class="check-{check.ok ? check.severity : 'error'}">{check.message}</li>
          {/each}
        </ul>
      {/if}
      {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
      <div class="actions">
        <button type="button" class="btn btn-ghost" onclick={() => (step = "choose")}>Back</button>
        <button type="button" class="btn btn-primary" disabled={busy} onclick={next}>{busy ? "Checking…" : "Check and continue"}</button>
      </div>
    {:else if step === "review"}
      <dl class="review">
        <dt>Connection</dt><dd>{modeLabel(form.mode)}</dd>
        {#if form.mode !== "local"}<dt>Who can reach Raiker</dt><dd>{exposureSentence(form)}</dd>{/if}
        <dt>When</dt><dd>When Raiker next restarts. Until then nothing changes.</dd>
      </dl>
      {#each checks.filter((check) => check.severity === "warning") as check (check.code)}
        <p class="sub small">{check.message}</p>
      {/each}
      {#if form.mode !== "local"}
        <label class="confirm">
          <input type="checkbox" bind:checked={confirmExposure} />
          I understand that other devices will be able to reach Raiker's sign-in page.
        </label>
      {/if}
      <p class="sub">Confirm it is you.</p>
      <label>
        Password
        <input type="password" bind:value={password} autocomplete="current-password" />
      </label>
      <label>
        Authenticator code
        <input type="text" inputmode="numeric" bind:value={code} autocomplete="one-time-code" />
      </label>
      {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
      <div class="actions">
        <button type="button" class="btn btn-ghost" onclick={() => (step = form.mode === "local" ? "choose" : "details")}>Back</button>
        <button
          type="button"
          class="btn btn-primary"
          disabled={busy || !password || !code || (form.mode !== "local" && (!confirmExposure || !checkedOk))}
          onclick={apply}
        >
          {form.mode === "local" ? "Save" : "Turn on remote access"}
        </button>
      </div>
    {:else}
      <p class="notice notice-ok" role="status">
        {status.restart_required
          ? "Saved. Raiker opens it when it restarts."
          : "Saved."}
      </p>
      {#if status.restart_required}
        {#if status.restartable}
          <div class="actions">
            <button type="button" class="btn btn-primary" disabled={restarting} onclick={restartNow}>{restarting ? "Restarting…" : "Restart now"}</button>
          </div>
        {:else}
          <p class="sub">Quit Raiker and open it again to apply it. Raiker is not set to start in the background, so it cannot restart itself.</p>
        {/if}
      {/if}
      {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
      {#if notice}<p class="sub">{notice}</p>{/if}
    {/if}
  </FormDialog>
{:else if panel === "details" && status}
  <FormDialog title="Connection details" onclose={() => (panel = null)}>
    <dl class="review">
      <dt>Open now</dt><dd>{status.active.address ?? "Nothing — this device only"}{status.active.refusing ? " (refusing everything until a restart)" : ""}</dd>
      <dt>Raiker's own listener</dt><dd>{status.local_listener} — this computer only</dd>
      {#if status.connection_address}<dt>Open Raiker at</dt><dd>{status.connection_address}</dd>{/if}
      {#if status.active.mode === "proxy" && status.active.address}<dt>Open Raiker at</dt><dd>Your proxy's https:// address</dd>{/if}
      <dt>Chosen setting</dt><dd>{modeLabel(status.desired.mode)}{status.restart_required ? " — applies at the next restart" : ""}</dd>
      <dt>Set by</dt><dd>{status.active.source === "start_options" ? "Raiker's start options" : "Settings"}</dd>
      {#if status.last_start}
        <dt>Last start</dt>
        <dd>{status.last_start.message ?? (status.last_start.outcome === "started" ? "The remote listener opened." : status.last_start.outcome === "local" ? "This device only." : status.last_start.outcome)}{status.last_start.at ? ` · ${relativeTime(status.last_start.at)}` : ""}</dd>
      {/if}
    </dl>
    {#if status.recent_events.length > 0}
      <h3 class="events-h">Recent</h3>
      <ul class="events">
        {#each status.recent_events as event, index (index)}
          <li><span>{eventLabel(event.kind)}</span><span class="sub">{relativeTime(event.at)}</span></li>
        {/each}
      </ul>
    {/if}
    {#if status.can_configure && status.previous !== null}
      <details class="advanced">
        <summary>Go back to the previous setting ({modeLabel(status.previous.mode)})</summary>
        <label>
          Password
          <input type="password" bind:value={password} autocomplete="current-password" />
        </label>
        <label>
          Authenticator code
          <input type="text" inputmode="numeric" bind:value={code} autocomplete="one-time-code" />
        </label>
        {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
        <div class="actions">
          <button type="button" class="btn btn-soft" disabled={busy || !password || !code} onclick={rollBack}>Go back</button>
        </div>
      </details>
    {/if}
    {#if notice}<p class="sub">{notice}</p>{/if}
  </FormDialog>
{/if}

<style>
  .setting-row {
    display: grid;
    grid-template-columns: minmax(10rem, 1fr) minmax(0, 1.4fr) auto;
    align-items: center;
    gap: var(--space-3);
    min-height: 52px;
    border-top: 1px solid var(--border);
  }
  .setting-row:first-of-type { border-top: none; }
  .setting-row h3 { margin: 0; font-size: var(--text-sm); }
  .setting-value { color: var(--text-2); font-size: var(--text-sm); }
  .row-actions { display: flex; gap: var(--space-2); }
  .state { font-weight: 500; }
  .state-ok { color: var(--ok, var(--text-1)); }
  .state-warn { color: var(--warn, var(--text-1)); }
  .state-danger { color: var(--danger); }
  .sub { color: var(--text-2); }
  .small { font-size: var(--text-sm); margin: var(--space-2) 0 0; }
  .problem { margin: var(--space-2) 0 0; color: var(--danger); font-size: var(--text-sm); }
  .warning {
    margin: var(--space-2) 0;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--r-md);
    background: var(--warn-soft);
    border: 1px solid var(--warn-border);
    font-size: var(--text-sm);
  }
  .choices { display: grid; gap: var(--space-2); margin-top: var(--space-2); }
  .choice {
    display: flex;
    gap: var(--space-2);
    align-items: flex-start;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    cursor: pointer;
  }
  .choice.selected { border-color: var(--accent); }
  .choice span { display: grid; gap: 0.15rem; }
  .choice .sub { font-size: var(--text-sm); }
  .requirements { margin: var(--space-3) 0 0; padding-left: 1.1rem; font-size: var(--text-sm); color: var(--text-2); display: grid; gap: var(--space-1); }
  .requirements .missing { color: var(--danger); }
  label { display: flex; flex-direction: column; gap: var(--space-1); margin-top: var(--space-2); max-width: 30rem; }
  label.inline, label.confirm { flex-direction: row; align-items: center; gap: var(--space-2); }
  label input:not([type="checkbox"]):not([type="radio"]) { padding: var(--space-2) var(--space-3); }
  .advanced { margin-top: var(--space-3); }
  .advanced summary { cursor: pointer; color: var(--text-2); font-size: var(--text-sm); }
  .kind { border: none; padding: 0; margin: var(--space-2) 0 0; display: grid; gap: var(--space-1); }
  .kind legend { font-size: var(--text-sm); color: var(--text-2); padding: 0; }
  .example {
    margin: var(--space-2) 0 0;
    padding: var(--space-2) var(--space-3);
    background: var(--sunken);
    border-radius: var(--r-md);
    font-size: var(--text-sm);
    white-space: pre-wrap;
  }
  .checks { margin: var(--space-3) 0 0; padding-left: 1.1rem; font-size: var(--text-sm); display: grid; gap: var(--space-1); }
  .check-error { color: var(--danger); }
  .check-warning, .check-info { color: var(--text-2); }
  .review { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: var(--space-1) var(--space-3); margin: var(--space-2) 0; font-size: var(--text-sm); }
  .review dt { color: var(--text-2); }
  .review dd { margin: 0; overflow-wrap: anywhere; }
  .actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); flex-wrap: wrap; }
  .link { background: none; border: none; color: var(--accent); cursor: pointer; padding: 0; margin-left: var(--space-1); }
  .events-h { font-size: var(--text-sm); margin: var(--space-3) 0 var(--space-1); }
  .events { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); font-size: var(--text-sm); }
  .events li { display: flex; justify-content: space-between; gap: var(--space-3); }
  @media (max-width: 560px) {
    .setting-row { grid-template-columns: 1fr; padding: var(--space-2) 0; }
  }
</style>
