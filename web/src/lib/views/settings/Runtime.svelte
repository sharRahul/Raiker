<script lang="ts">
  /**
   * Runtime configuration.
   *
   * Raiker used to ship five runtime modes — development preview, two
   * single-user modes, a multi-user mode and a hosted mode — and this panel
   * was where you picked one. Picking never told anyone anything: what the
   * agent may do is decided by each capability's own gate, its threat-model
   * acknowledgement, its human confirmation and whether a real executor is
   * registered. The mode was a fifth answer that could only say "not yet" to
   * work the other four had already authorised, and choosing wrong left a
   * correctly-configured install refusing to run.
   *
   * There is one runtime now and it does all of it, so this panel states what
   * is running instead of asking. The one runtime-level decision that remains
   * is binary and stays here in the danger zone: whether the runtime accepts
   * new executions at all.
   */
  import { onMount } from "svelte";
  import Icon from "../../components/Icon.svelte";
  import StepUpDialog from "../../components/StepUpDialog.svelte";
  import type { StepUpValues } from "../../components/StepUpDialog.svelte";
  import GuideLink from "../../components/GuideLink.svelte";
  import { api, ApiError } from "../../api";
  import type { ExecutionEnvironmentsView, RuntimeMode } from "../../apiTypes";
  import { explainReasonCode } from "../../reasonCodes";
  import { boundaryLabel, observationRows } from "../../sandboxPosture";

  let {
    principal = "—",
    settings = {},
    save = () => {},
  }: {
    principal?: string;
    settings?: Record<string, unknown>;
    save?: (patch: Record<string, unknown>) => void;
  } = $props();

  // BUG-83 — the readiness observation window used to be a hard-coded five
  // minutes with no way to move it, so a long session traded a stale-ready
  // window for a spurious-stale interruption and offered no control over
  // either. The bounds are the server's: under a minute is a check on every
  // keystroke, over two hours is not a check.
  const readinessTtl = $derived(
    Number(settings["models.readiness_ttl_minutes"] ?? 5),
  );
  let mode = $state<RuntimeMode | null>(null);
  let loadError = $state<string | null>(null);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);
  type Pending = { kind: "enable" } | { kind: "disable" };
  let pending = $state<Pending | null>(null);
  let busy = $state(false);
  let dialogError = $state<string | null>(null);
  let environments = $state<ExecutionEnvironmentsView | null>(null);
  let environmentKind = $state<"ssh" | "daytona" | "container">("ssh");
  let environmentName = $state("");
  let host = $state("");
  let remoteUser = $state("");
  let hostPublicKey = $state("");
  let hostKeySha256 = $state("");
  let credentialEnv = $state("RAIKER_SSH_IDENTITY_FILE");
  let sandboxId = $state("");
  let maxCost = $state(10);
  let containerRuntime = $state<"docker" | "podman">("docker");
  let containerImage = $state("");
  let selectedContainerTools = $state<string[]>([]);
  let egressDomains = $state("");
  let egressPorts = $state("443");
  let probing = $state<string | null>(null);

  // The runtime is on unless the owner switched it off. An unreadable state is
  // never reported as running — the card says it could not be read instead.
  const running = $derived(mode !== null && mode.status === "active");

  async function load() {
    loadError = null;
    try {
      mode = await api.runtimeMode();
      try {
        environments = await api.executionEnvironments();
        const options = environments.container_options;
        if (options?.runtimes.length && !options.runtimes.includes(containerRuntime)) containerRuntime = options.runtimes[0];
        if (options?.images.length && !options.images.includes(containerImage)) containerImage = options.images[0];
      } catch { environments = null; }
    } catch (e) {
      mode = null;
      loadError = e instanceof ApiError ? `Unavailable (${e.status})` : "Unavailable";
    }
  }
  async function saveEnvironment() {
    busy = true; notice = null;
    try {
      const config = environmentKind === "ssh"
        ? { host, user: remoteUser, credential_env: credentialEnv, host_public_key: hostPublicKey, host_key_sha256: hostKeySha256, max_runtime_seconds: 300 }
        : environmentKind === "daytona"
          ? { sandbox_id: sandboxId, api_key_env: credentialEnv, max_cost: maxCost, max_runtime_seconds: 300 }
          : {
              runtime: containerRuntime,
              image: containerImage,
              tools: selectedContainerTools,
              repository_access: "read_only",
              writable_output: true,
              egress_domains: egressDomains.split(/[,\s]+/).map((value) => value.trim()).filter(Boolean),
              egress_ports: egressDomains.trim()
                ? egressPorts.split(/[,\s]+/).map(Number).filter((value) => Number.isInteger(value))
                : [],
            };
      await api.configureExecutionEnvironment({ kind: environmentKind, name: environmentName, config, enabled: true });
      notice = { kind: "ok", text: environmentKind === "container" ? "Container execution profile saved." : `${environmentKind === "ssh" ? "SSH" : "Daytona"} environment saved. Credential values remain in the named environment variable.` };
      environmentName = ""; host = ""; remoteUser = ""; hostPublicKey = ""; hostKeySha256 = ""; sandboxId = "";
      selectedContainerTools = [];
      egressDomains = ""; egressPorts = "443";
      await load();
    } catch { notice = { kind: "error", text: "The execution profile could not be saved." }; }
    finally { busy = false; }
  }
  function runtimeName(runtime: string | undefined): string {
    return runtime ? runtime.charAt(0).toUpperCase() + runtime.slice(1) : "Container";
  }
  function containerReason(reason: string | null | undefined): string | null {
    if (!reason) return null;
    if (reason.startsWith("container_runtime_unavailable:")) return `${runtimeName(reason.split(":", 2)[1])} is not available on this host.`;
    if (reason === "container_gate_disabled") return "Enable container execution in Permissions.";
    if (reason === "container_image_not_allowlisted") return "Choose an operator-approved container image.";
    return "This container profile is not ready.";
  }
  // BUG-194 — what a boundary actually does between commands, stated on the
  // card. Only capabilities that are true are listed: an environment that does
  // not persist says nothing here rather than showing a greyed-out promise,
  // which is the same rule the absent filtered-network control follows.
  const CAPABILITY_LABELS: Array<[string, string]> = [
    ["background", "Runs work in the background"],
    ["pty", "Gives a command a real terminal"],
    ["persistent_environment", "Keeps its state between commands"],
    ["restart_recovery", "Survives a Raiker restart"],
    ["process_tree_stop", "Stops the whole process tree"],
    ["concurrent_runs", "Runs commands side by side"],
  ];
  function capabilityRows(features: Record<string, boolean> | undefined): string[] {
    if (!features) return [];
    return CAPABILITY_LABELS.filter(([key]) => features[key]).map(([, label]) => label);
  }
  const LIMITATION_LABELS: Array<[string, string]> = [
    ["pty", "PTY"],
    ["background", "background execution"],
    ["persistent_environment", "persistence"],
    ["restart_recovery", "restart recovery"],
    ["filtered_network", "filtered egress"],
    ["credential_delivery", "command credential delivery"],
  ];
  function limitationSummary(features: Record<string, boolean> | undefined): string {
    const missing = LIMITATION_LABELS.filter(([key]) => !features?.[key]).map(([, label]) => label);
    if (!missing.length) return "All governed execution capabilities are available.";
    const names = missing.length === 1
      ? missing[0]
      : `${missing.slice(0, -1).join(", ")} and ${missing.at(-1)}`;
    return `${names} ${missing.length === 1 ? "is" : "are"} unavailable.`;
  }
  function egressList(config: Record<string, unknown> | undefined, key: string): string[] {
    const value = config?.[key];
    return Array.isArray(value) ? value.map(String) : [];
  }
  let resetting = $state<string | null>(null);
  async function resetEnvironment(profileId: string, recreate: boolean) {
    const question = recreate
      ? "Discard this session's environment and its cached files? The next command starts from the approved image."
      : "Discard this session's environment? The next command starts from the approved image; cached files are kept.";
    if (!window.confirm(question)) return;
    resetting = profileId; notice = null;
    try {
      await api.resetExecutionEnvironment(profileId, "settings", recreate);
      notice = { kind: "ok", text: recreate ? "Environment and cache discarded." : "Environment discarded; cache kept." };
    } catch (e) {
      const reason = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      notice = {
        kind: "error",
        text: reason === "execution_environment_reset_unavailable"
          ? "This session has no environment standing, so there is nothing to reset."
          : "The environment could not be reset.",
      };
    } finally { resetting = null; }
  }
  function toggleContainerTool(tool: string, checked: boolean) {
    selectedContainerTools = checked
      ? [...selectedContainerTools, tool]
      : selectedContainerTools.filter((item) => item !== tool);
  }
  async function reprobe(profileId: string) {
    // Native re-measures its host boundary; remote targets invoke only the
    // fixed read-only supervisor probe. Both are explicit owner actions.
    probing = profileId;
    notice = null;
    try {
      await api.probeExecutionEnvironment(profileId);
      await load();
      notice = { kind: "ok", text: "The execution boundary was checked." };
    } catch {
      notice = { kind: "error", text: "The boundary could not be measured on this host." };
    } finally {
      probing = null;
    }
  }

  async function selectEnvironment(profileId: string) {
    try { await api.selectExecutionEnvironment(profileId); await load(); }
    catch { notice = { kind: "error", text: "That environment is not ready. Complete its configuration and credential reference first." }; }
  }

  async function confirm(values: StepUpValues) {
    if (!pending) return;
    busy = true;
    dialogError = null;
    try {
      if (pending.kind === "enable") await api.activateRuntimeMode("raiker_runtime", values.reason);
      else await api.disableRuntimeMode(values.reason);
      notice = {
        kind: "ok",
        text: pending.kind === "enable" ? "The agent runtime is accepting work again." : "Agent runtime disabled.",
      };
      pending = null;
      await load();
    } catch (e) {
      const explained = e instanceof ApiError ? explainReasonCode(e.reasonCode) : null;
      dialogError = explained
        ? `${explained.plain} ${explained.remediation ?? ""}`
        : "The change was rejected by the runtime.";
    } finally {
      busy = false;
    }
  }
  onMount(load);
</script>

<header class="section-heading">
  <h2>Runtime configuration</h2>
</header>

{#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}

<section class="settings-card">
  <GuideLink route="settings" />
  <div class="card-heading">
    <span class="eyebrow">Agent runtime</span>
    <h3>
      Raiker runtime
      {#if mode}<span class="status" class:stopped={!running}>· {running ? "Accepting work" : "Disabled"}</span>{/if}
    </h3>
  </div>
  {#if loadError}
    <p class="error" role="alert">{loadError}</p>
  {:else if mode === null}
    <p class="description" role="status">Loading…</p>
  {:else}
    <p class="description">
      {running
        ? "New executions run under this runtime. What each one may actually do is decided by Permissions, project boundaries, and your approvals."
        : "New executions are refused. Work already running continues to its next safe boundary."}
    </p>
    <dl>
      <div><dt>State</dt><dd>{running ? "Accepting new executions" : "Not accepting new executions"}</dd></div>
      <div><dt>Last changed</dt><dd>{mode.activated_at || "Not recorded"}</dd></div>
      <div><dt>Changed by</dt><dd>{mode.activated_by || "Administrator"}</dd></div>
    </dl>
    <div class="actions">
      <a href="#/activity">View change history</a>
      <a class="btn btn-ghost btn-sm" href="#/capabilities"><Icon name="capabilities" size="sm" /> Review permissions</a>
    </div>
  {/if}
</section>

<section class="settings-card" aria-labelledby="model-readiness-heading">
  <div class="card-heading">
    <span class="eyebrow">Model readiness</span>
    <h3 id="model-readiness-heading">How long a model check stays good for</h3>
  </div>
  <label>
    <span>Re-confirm after</span>
    <small>Between 1 and 120 minutes. The default is 5.</small>
    <input
      type="number"
      min="1"
      max="120"
      step="1"
      value={readinessTtl}
      onchange={(event) =>
        save({
          "models.readiness_ttl_minutes": Math.min(
            120,
            Math.max(1, Number(event.currentTarget.value) || 5),
          ),
        })}
    />
  </label>
</section>

<section class="settings-card environment-settings">
  <div class="card-heading"><span class="eyebrow">Execution targets</span><h3>Local, remote, and cloud environments</h3></div>
  {#if environments}
    <div class="environment-grid">
      {#each environments.environments as environment}
        <article class:selected={environment.selected}>
          <div>
            <strong>{environment.name}</strong>
            {#if environment.kind === "native" || environment.kind === "local"}
              <span class="container-runtime">{boundaryLabel(environment)}</span>
              <ul class="observations">
                {#each observationRows(environment.probe_observations) as observation}
                  <li class={observation.verdict}>
                    <span>{observation.label}</span>
                    <strong>{observation.verdictLabel}</strong>
                  </li>
                {:else}
                  <li class="indeterminate">
                    <span>This host has not been measured</span>
                    <strong>Not proven</strong>
                  </li>
                {/each}
              </ul>
              <span class="boundary">{environment.features?.background ? "Foreground and background command execution" : "Foreground command execution"}</span>
              <small class="plain">{limitationSummary(environment.features)}</small>
              <small class="trust-posture" class:verified={environment.runner_trust === "publisher_verified"}>
                {environment.runner_trust === "publisher_verified"
                  ? "Publisher verified"
                  : environment.runner_trust === "package_relative_integrity"
                    ? "Package-relative integrity only"
                    : "Developer build — runner publisher unverified"}
              </small>
              {#if environment.availability_reason}
                <small class="remediation">{explainReasonCode(environment.availability_reason)?.plain ?? environment.availability_reason.replaceAll("_", " ")}</small>
              {/if}
              <button
                class="btn btn-ghost btn-sm reprobe"
                type="button"
                disabled={probing === environment.profile_id}
                onclick={() => void reprobe(environment.profile_id)}
              >
                {probing === environment.profile_id ? "Measuring…" : "Re-measure boundary"}
              </button>
              <small class="plain">Re-measuring opens one connection to this host's default gateway on a closed port.</small>
            {:else if environment.kind === "container"}
              <span class="container-runtime">{runtimeName(environment.runtime)} · {environment.image ?? "No approved image"}</span>
              <span class="boundary">Read-only repository → writable output</span>
              <small>{environment.assigned_tool_count ?? 0} tools</small>
              {#if containerReason(environment.availability_reason)}<small class="remediation">{containerReason(environment.availability_reason)}</small>{/if}
              {#if egressList(environment.config, "egress_domains").length}
                <section class="egress-status" aria-label="Filtered network status" role="status">
                  <strong>Filtered network · not proven</strong>
                  <span>{egressList(environment.config, "egress_domains").join(", ")} · ports {egressList(environment.config, "egress_ports").join(", ")}</span>
                  <small>Configured destinations stay blocked until the container bypass and revocation probe passes.</small>
                </section>
              {/if}
            {:else}
              <span>{environment.kind} · {environment.status.replaceAll("_", " ")}</span>
              <span class="boundary">Foreground command execution</span>
              <small class="plain">PTY, background execution, persistence, restart recovery, filtered egress, and command credential delivery are unavailable.</small>
              {#if environment.availability_reason}<small class="remediation">{environment.availability_reason.replaceAll("_", " ")}</small>{/if}
              <button class="btn btn-ghost btn-sm reprobe" type="button" disabled={probing === environment.profile_id} onclick={() => void reprobe(environment.profile_id)}>{probing === environment.profile_id ? "Checking…" : "Check supervisor"}</button>
              {#if environment.cost}<small>USD {environment.cost.committed_cost.toFixed(2)} committed · {environment.cost.remaining_cost?.toFixed(2) ?? "0.00"} remaining · {environment.cost.reconciliation_status.replaceAll("_", " ")}</small>{/if}
            {/if}
            <!-- BUG-194 — what this boundary does between commands. Only true
                 capabilities appear: an absent line is the honest projection of
                 something this environment does not do, where a disabled one
                 would imply it is a setting away. -->
            {#if capabilityRows(environment.features).length}
              <ul class="capabilities">
                {#each capabilityRows(environment.features) as capability (capability)}<li><Icon name="check" size="sm" /> {capability}</li>{/each}
              </ul>
            {/if}
            {#if environment.features?.persistent_environment}
              <div class="reset-actions">
                <button class="btn btn-ghost btn-sm" type="button" disabled={resetting === environment.profile_id} onclick={() => void resetEnvironment(environment.profile_id, false)}>Reset environment</button>
                <button class="btn btn-ghost btn-sm danger" type="button" disabled={resetting === environment.profile_id} onclick={() => void resetEnvironment(environment.profile_id, true)}>Reset and clear cache</button>
              </div>
              <small class="plain">Resetting discards what commands left behind. The next command starts from the approved image.</small>
            {/if}
          </div>
          <button class="btn btn-ghost btn-sm" disabled={!environment.available || environment.selected} onclick={() => void selectEnvironment(environment.profile_id)}>{environment.selected ? "Selected" : "Select"}</button>
        </article>
      {/each}
    </div>
  {/if}
  <details>
    <summary>Add execution profile</summary>
    <form class="environment-form" onsubmit={(event) => { event.preventDefault(); void saveEnvironment(); }}>
      <label>Environment type<select bind:value={environmentKind} onchange={() => credentialEnv = environmentKind === "ssh" ? "RAIKER_SSH_IDENTITY_FILE" : "DAYTONA_API_KEY"}><option value="ssh">SSH remote host</option><option value="daytona">Daytona cloud sandbox</option><option value="container">Container boundary</option></select></label>
      <label>Display name<input bind:value={environmentName} required placeholder="Build host" /></label>
      {#if environmentKind === "ssh"}
        <label>Host<input bind:value={host} required placeholder="build.example.com" /></label><label>Remote user<input bind:value={remoteUser} required placeholder="raiker" /></label>
        <label>Pinned host public key<input bind:value={hostPublicKey} required placeholder="ssh-ed25519 AAAA…" /></label>
        <label>Host fingerprint<input bind:value={hostKeySha256} required pattern={"SHA256:[A-Za-z0-9+/]{43}"} placeholder="SHA256:…" /></label>
      {:else if environmentKind === "daytona"}
        <label>Sandbox ID<input bind:value={sandboxId} required placeholder="sandbox-id" /></label><label>Maximum run cost (USD)<input type="number" min="0.01" step="0.01" bind:value={maxCost} /></label>
      {:else}
        <label>Container runtime<select bind:value={containerRuntime}>{#each environments?.container_options?.runtimes ?? [] as runtime}<option value={runtime}>{runtimeName(runtime)}</option>{/each}</select></label>
        <label>Approved image<select bind:value={containerImage}>{#each environments?.container_options?.images ?? [] as image}<option value={image}>{image}</option>{/each}</select></label>
        <fieldset><legend>Container tools</legend>{#each environments?.container_options?.supported_tools ?? [] as tool}<label class="tool-choice"><input type="checkbox" checked={selectedContainerTools.includes(tool)} onchange={(event) => toggleContainerTool(tool, event.currentTarget.checked)} /> {tool}</label>{/each}</fieldset>
        <label>Allowed network domains<input bind:value={egressDomains} placeholder="api.example.com, *.packages.example" /><small>Exact domains or boundary-safe wildcards. Empty keeps networking off.</small></label>
        <label>Allowed destination ports<input bind:value={egressPorts} inputmode="numeric" placeholder="443" /><small>Usually 443. Configuration alone never enables egress.</small></label>
        <div class="boundary-preview"><span>Repository</span><strong>Read only</strong><i>→</i><span>Output</span><strong>Writable</strong></div>
      {/if}
      {#if environmentKind !== "container"}<label>Credential environment variable<input bind:value={credentialEnv} required pattern={"[A-Z][A-Z0-9_]{2,127}"} /></label>
      <small>{environmentKind === "ssh" ? "The variable must contain the path to an OpenSSH private key; known-host verification stays strict." : "The variable must contain the Daytona API key. Every run reserves against cumulative spend; estimates remain reserved when provider billing data is unavailable."}</small>{/if}
      <button class="btn btn-primary" disabled={busy}>Save environment</button>
    </form>
  </details>
</section>

<section class="danger-zone">
  <h3>Danger zone</h3>
  {#if running}
    <h4>Disable agent runtime</h4>
    <p>Prevent Raiker from accepting new executions. Active work continues to its next safe boundary.</p>
    <button class="btn btn-danger" type="button" onclick={() => (pending = { kind: "disable" })}>Disable agent runtime</button>
  {:else}
    <h4>Enable agent runtime</h4>
    <p>Let Raiker accept new executions again. Every capability keeps the permission it already had.</p>
    <button class="btn btn-primary" type="button" onclick={() => (pending = { kind: "enable" })}>Enable agent runtime</button>
  {/if}
</section>

{#if pending}
  <StepUpDialog
    title={pending.kind === "enable" ? "Enable agent runtime" : "Disable agent runtime"}
    {principal}
    requireToken={false}
    requireThreatAck={false}
    {busy}
    error={dialogError}
    onConfirm={confirm}
    onCancel={() => { pending = null; dialogError = null; }}
  />
{/if}

<style>
  .section-heading { margin-bottom: var(--space-4); } .section-heading h2, h3, h4 { margin: 0; } .description, .danger-zone p { color: var(--text-2); }
  /* The readiness window is the one editable field in this section, so it needs
     the same stacked label/hint/control shape the other settings sections use
     rather than the browser's inline default. */
  .settings-card label { display: grid; gap: .25rem; max-width: 22rem; margin-top: var(--space-3); }
  .settings-card label > span { font-weight: 650; }
  .settings-card label > small { color: var(--text-2); }
  .settings-card label > input { min-height: 40px; padding: 0 .65rem; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--sunken); color: var(--text-1); font: inherit; }
  .settings-card, .danger-zone { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--card-pad-y) var(--card-pad-x); }
  .environment-settings { margin-top:var(--space-5); } .environment-grid { display:grid; gap:var(--space-2); margin:var(--space-4) 0; } .environment-grid article { display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); padding:var(--space-3); border:1px solid var(--border); border-radius:var(--r-md); } .environment-grid article.selected { border-color:var(--accent-border); background:var(--accent-soft); } .environment-grid article div { display:grid; gap:.2rem; } .environment-grid article span { color:var(--text-3); font-size:var(--text-xs); text-transform:capitalize; } .environment-grid article .container-runtime { color:var(--text-2); font-family:var(--font-mono); text-transform:none; } .environment-grid article .boundary { width:fit-content; padding:.18rem .45rem; border-left:2px solid var(--accent); background:var(--sunken); color:var(--text-2); text-transform:none; } .environment-grid article small { color:var(--text-2); font-size:var(--text-xs); text-transform:capitalize; } .environment-grid article .remediation { color:var(--warn); text-transform:none; }
  .observations { display:grid; gap:.15rem; margin:.35rem 0 0; padding:0; list-style:none; }
  .observations li { display:flex; align-items:baseline; justify-content:space-between; gap:.75rem; font-size:var(--text-xs); }
  /* The card capitalises its short labels. These are sentences —
     "Cannot read Raiker's own state" — so they opt out of that. */
  .observations li span, .observations li strong, .environment-grid article small.plain { text-transform:none; }
  .observations li span { color:var(--text-2); }
  .observations li strong { font-size:var(--text-2xs); font-weight:650; white-space:nowrap; }
  /* VIS2-16 — an enforced boundary is the normal case and reads as plain
     fact; the two states that are not normal keep their tone. */
  .observations li.enforced strong { color:var(--text-1); }
  .observations li.unenforced strong { color:var(--danger); }
  .observations li.indeterminate strong { color:var(--warn); }
  .trust-posture { color:var(--warn) !important; text-transform:none !important; }
  .trust-posture.verified { color:var(--text-1) !important; }
  .reprobe { justify-self:start; margin-top:.35rem; }
  /* BUG-194 — the capabilities a boundary really has. Same weight as the
     measured observations above them, because they are the same kind of claim:
     a statement of what was built, not of what was configured. */
  .capabilities { display:grid; gap:.15rem; margin:.35rem 0 0; padding:0; list-style:none; }
  .capabilities li { display:flex; align-items:center; gap:.35rem; color:var(--text-2); font-size:var(--text-xs); text-transform:none; }
  .capabilities li :global(svg) { flex:none; color:var(--text-3); }
  .egress-status { display:grid; gap:.2rem; margin-top:.45rem; padding:.65rem .75rem; border-left:3px solid var(--warn); background:var(--sunken); }
  .egress-status strong { color:var(--warn); font-size:var(--text-xs); }
  .egress-status span { color:var(--text-1); font-family:var(--font-mono); font-size:var(--text-xs); text-transform:none; overflow-wrap:anywhere; }
  .egress-status small { color:var(--text-2); text-transform:none; }
  .reset-actions { display:flex; flex-wrap:wrap; gap:var(--space-2); margin-top:.45rem; }
  .reset-actions .danger { color:var(--danger); }
  details { margin-top:var(--space-4); } summary { cursor:pointer; font-weight:650; } .environment-form { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:var(--space-3); margin-top:var(--space-3); } .environment-form label { display:grid; gap:.35rem; min-width:0; color:var(--text-2); font-size:var(--text-sm); } /* `minmax(0,1fr)` on the track is only half of it: a grid item's automatic minimum is its content, and a <select> is at least as wide as its longest option ('Daytona cloud workspace'), so the label held a 183px minimum inside a 152px track and bled at 390px. Found by the width sweep once it started covering Settings — FIXED-416. */ .environment-form input,.environment-form select { min-width:0; max-width:100%; background:var(--sunken); } .environment-form small,.environment-form button,.environment-form fieldset,.boundary-preview { grid-column:1/-1; } .environment-form fieldset { display:flex; flex-wrap:wrap; gap:.5rem 1rem; margin:0; padding:var(--space-3); border:1px solid var(--border); border-radius:var(--r-md); } .environment-form fieldset legend { padding:0 .35rem; color:var(--text-2); font-size:var(--text-sm); } .environment-form .tool-choice { display:flex; grid-template-columns:auto 1fr; align-items:center; gap:.35rem; color:var(--text-1); font-family:var(--font-mono); } .environment-form .tool-choice input { min-height:0; } .boundary-preview { display:grid; grid-template-columns:auto auto 1fr auto auto; align-items:center; gap:.55rem; padding:.7rem .8rem; border-left:3px solid var(--accent); background:var(--sunken); color:var(--text-3); font-size:var(--text-xs); } .boundary-preview strong { color:var(--text-1); } .boundary-preview i { text-align:center; color:var(--accent); font-style:normal; }
  .status { color: var(--ok); font-size: var(--text-sm); } .status.stopped { color: var(--warn); }
  .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .08em; font-size: var(--text-xs); font-weight: 700; }
  dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); padding: var(--space-4) 0; border-block: 1px solid var(--border); } dl div { display: grid; gap: .2rem; } dt { color: var(--text-3); font-size: var(--text-xs); } dd { margin: 0; }
  .actions { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-5); }
  .danger-zone { margin-top: var(--space-5); border-color: color-mix(in srgb, var(--danger) 40%, var(--border)); } .danger-zone h4 { margin-top: var(--space-4); } .error { color: var(--danger); }
  @media (max-width: 40rem) { dl { grid-template-columns: 1fr; } .actions { align-items: stretch; flex-direction: column; } .environment-form { grid-template-columns: minmax(0, 1fr); } }
</style>
