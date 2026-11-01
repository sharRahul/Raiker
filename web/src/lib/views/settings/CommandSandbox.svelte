<script lang="ts">
  /**
   * Which boundary sandboxed commands use on Windows.
   *
   * The restricted account runs Windows toolchains; WSL2 runs Linux ones in
   * Raiker's own distribution, under the same boundary Linux uses. Only shown
   * on Windows, where the choice applies. Choosing WSL2 before it is set up is
   * allowed and fails closed: commands refuse rather than fall back.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import type { CommandSandboxView } from "../../apiTypes";

  type Backend = "account" | "wsl";

  const MISSING: Record<string, string> = {
    distribution_present: "Raiker's WSL distribution is not installed",
    wsl_conf_current: "its configuration is not Raiker's (Windows programs or drives may be reachable)",
    runner_installed: "the Linux runner is not installed in it",
    bubblewrap_present: "Bubblewrap is not installed in it",
  };

  let view = $state<CommandSandboxView | null>(null);
  let busy = $state(false);
  let notice = $state<{ kind: "ok" | "error"; text: string } | null>(null);

  async function load() {
    try {
      view = await api.commandSandbox();
    } catch {
      view = null;
    }
  }

  async function choose(backend: Backend) {
    busy = true;
    notice = null;
    try {
      view = await api.setCommandSandbox(backend);
      notice = {
        kind: "ok",
        text: backend === "wsl" ? "Commands now run in WSL2." : "Commands now run as the sandbox account.",
      };
    } catch {
      notice = { kind: "error", text: "The setting could not be saved." };
    } finally {
      busy = false;
    }
  }

  // Reasons the runner gives, in words the owner can act on.
  const REFUSED: Record<string, string> = {
    native_sandbox_wsl_rootfs_invalid: "That file is not a .tar or .tar.gz root filesystem.",
    native_sandbox_wsl_runner_missing: "This install does not include the Linux runner WSL2 needs.",
    native_sandbox_wsl_unavailable: "WSL is not available on this PC. Install it with `wsl --install`, restart, and try again.",
    native_sandbox_wsl_import_failed: "WSL could not import that file. Check it is a Linux root filesystem.",
    native_sandbox_wsl_bubblewrap_missing: "Bubblewrap could not be installed in the distribution (it needs the internet once).",
    native_sandbox_wsl_setup_timed_out: "Setup took longer than 15 minutes and was stopped.",
  };

  let rootfs = $state("");
  let confirmingRemove = $state(false);

  async function setUp() {
    busy = true;
    notice = { kind: "ok", text: "Setting up WSL2. This can take a few minutes…" };
    try {
      view = await api.setupCommandSandboxWsl(rootfs.trim());
      notice = { kind: "ok", text: view.wsl_configured ? "WSL2 is set up." : "Setup finished, but WSL2 is not ready yet." };
    } catch (e) {
      const reason = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      notice = { kind: "error", text: REFUSED[reason] ?? `WSL2 could not be set up (${reason || "unknown error"}).` };
    } finally {
      busy = false;
    }
  }

  async function remove() {
    busy = true;
    confirmingRemove = false;
    notice = null;
    try {
      view = await api.removeCommandSandboxWsl();
      notice = { kind: "ok", text: "WSL2 removed. Commands run as the sandbox account." };
    } catch {
      notice = { kind: "error", text: "WSL2 could not be removed." };
    } finally {
      busy = false;
    }
  }

  onMount(() => void load());
</script>

{#if view?.applies}
  <section class="settings-card" aria-label="Command sandbox">
    <div class="card-heading"><h3>Command sandbox</h3></div>
    <p>Where sandboxed commands run on this PC. Hooks, MCP servers and plugins always use the sandbox account.</p>
    <fieldset disabled={busy}>
      <legend class="sr-only">Command sandbox</legend>
      <label class="option">
        <input
          type="radio"
          name="command-sandbox"
          value="account"
          checked={view.windows_backend === "account"}
          onchange={() => void choose("account")}
        />
        <span><strong>Sandbox account</strong> — Windows toolchains (Python, Node, Git for Windows)</span>
      </label>
      <label class="option">
        <input
          type="radio"
          name="command-sandbox"
          value="wsl"
          checked={view.windows_backend === "wsl"}
          onchange={() => void choose("wsl")}
        />
        <span><strong>WSL2</strong> — Linux toolchains, in Raiker's own distribution. No downloads, no terminals.</span>
      </label>
    </fieldset>
    {#if view.wsl_configured}
      <p class="notice notice-ok">WSL2 is set up.</p>
      {#if confirmingRemove}
        <p class="notice notice-danger" role="alert">
          This deletes Raiker's WSL distribution and every task copy inside it, including changes not yet applied.
        </p>
        <div class="actions">
          <button class="btn btn-danger btn-sm" type="button" disabled={busy} onclick={() => void remove()}>Remove WSL2</button>
          <button class="btn btn-ghost btn-sm" type="button" disabled={busy} onclick={() => (confirmingRemove = false)}>Keep it</button>
        </div>
      {:else}
        <button class="btn btn-ghost btn-sm" type="button" disabled={busy} onclick={() => (confirmingRemove = true)}>Remove WSL2…</button>
      {/if}
    {:else}
      <p class="notice {view.windows_backend === 'wsl' ? 'notice-danger' : ''}" role="status">
        WSL2 is not set up{view.windows_backend === "wsl" ? ", so commands will be refused until it is" : ""}:
        {view.wsl_missing.map((name) => MISSING[name] ?? name).join("; ")}.
      </p>
      {#if view.wsl_setup_command}
        <form class="setup" onsubmit={(event) => { event.preventDefault(); void setUp(); }}>
          <label>
            <span>
              Linux root filesystem (.tar or .tar.gz), for example the Ubuntu base image from
              cdimage.ubuntu.com/ubuntu-base. Raiker imports it as its own distribution; your existing
              WSL distributions are not touched.
            </span>
            <input type="text" bind:value={rootfs} placeholder="C:\Users\you\Downloads\ubuntu-base-24.04-base-amd64.tar.gz" disabled={busy} required />
          </label>
          <button class="btn btn-primary btn-sm" type="submit" disabled={busy || !rootfs.trim()}>Set up WSL2</button>
          <small>No administrator rights needed. Setup installs Bubblewrap inside the distribution, which needs the internet once.</small>
        </form>
      {:else}
        <p>This install does not include the Linux runner WSL2 needs.</p>
      {/if}
    {/if}
    {#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}
  </section>
{/if}

<style>
  fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: var(--space-2); }
  .option { display: flex; align-items: center; gap: var(--space-2); }
  .setup { display: grid; gap: var(--space-2); }
  .setup input { width: 100%; font-family: var(--font-mono); font-size: var(--text-xs); }
  .actions { display: flex; gap: var(--space-2); }
</style>
