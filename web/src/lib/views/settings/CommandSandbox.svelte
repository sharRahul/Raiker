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
  import { api } from "../../api";
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
    {:else}
      <p class="notice {view.windows_backend === 'wsl' ? 'notice-danger' : ''}" role="status">
        WSL2 is not set up{view.windows_backend === "wsl" ? ", so commands will be refused until it is" : ""}:
        {view.wsl_missing.map((name) => MISSING[name] ?? name).join("; ")}.
        {#if view.wsl_setup_command}
          Set it up from a terminal (no administrator needed): <code>{view.wsl_setup_command}</code>
        {:else}
          This install does not include the Linux runner WSL2 needs.
        {/if}
      </p>
    {/if}
    {#if notice}<p class="notice {notice.kind === 'ok' ? 'notice-ok' : 'notice-danger'}" role="status">{notice.text}</p>{/if}
  </section>
{/if}

<style>
  fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: var(--space-2); }
  .option { display: flex; align-items: center; gap: var(--space-2); }
</style>
