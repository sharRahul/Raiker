<script lang="ts">
  import { onMount } from "svelte";
  import Nav from "./lib/Nav.svelte";
  import RuntimeStatusBanner from "./lib/RuntimeStatusBanner.svelte";
  import StopSwitch from "./lib/StopSwitch.svelte";
  import { DEFAULT_ROUTE, NAV_ITEMS, routeFromHash } from "./lib/nav";
  import { api, connect } from "./lib/api";
  import Home from "./routes/Home.svelte";
  import Placeholder from "./routes/Placeholder.svelte";
  import CapabilityMatrix from "./lib/CapabilityMatrix.svelte";
  import RuntimeGatesView from "./lib/RuntimeGatesView.svelte";
  import ModelsView from "./lib/ModelsView.svelte";
  import EventLogViewer from "./lib/EventLogViewer.svelte";
  import CheckpointViewer from "./lib/CheckpointViewer.svelte";
  import DiagnosticsPanel from "./lib/DiagnosticsPanel.svelte";
  import ApprovalQueue from "./lib/ApprovalQueue.svelte";

  let current = $state(typeof window === "undefined" ? DEFAULT_ROUTE : routeFromHash(window.location.hash));
  const activeItem = $derived(NAV_ITEMS.find((item) => item.id === current) ?? NAV_ITEMS[0]);

  let authState = $state<"connecting" | "ready" | "error">("connecting");
  let principal = $state("—");
  let runtimeMode = $state("—");
  let ready = $state(false);
  let warnings = $state<string[]>([]);

  onMount(() => {
    const handler = () => {
      current = routeFromHash(window.location.hash);
    };
    window.addEventListener("hashchange", handler);
    void bootstrap();
    return () => window.removeEventListener("hashchange", handler);
  });

  async function bootstrap() {
    try {
      const session = await connect();
      principal = session.principal_id;
      const [mode, diag] = await Promise.all([api.runtimeMode(), api.diagnostics()]);
      runtimeMode = mode.mode_name;
      ready = diag.production_ready_local_single_user_runtime;
      warnings =
        diag.disabled_capabilities.length > 0
          ? [`${diag.disabled_capabilities.length} capabilities disabled / deferred`]
          : [];
      authState = "ready";
    } catch {
      authState = "error";
    }
  }
</script>

<a class="skip-link" href="#main">Skip to content</a>

<div class="app-shell">
  <header class="topbar">
    <RuntimeStatusBanner
      {runtimeMode}
      {principal}
      {ready}
      {warnings}
      connecting={authState === "connecting"}
    />
    <StopSwitch />
  </header>
  <div class="app-body">
    <Nav items={NAV_ITEMS} {current} />
    <main id="main" class="content" tabindex="-1">
      {#if authState === "error"}
        <div class="conn-error" role="alert">
          <h1>Cannot reach the local Raiker API</h1>
          <p>
            Start the local server with <code>raiker-web</code> and ensure an owner is bootstrapped
            (<code>raiker</code> → <code>/bootstrap-owner</code>). The UI talks only to the local
            governed API and never fabricates data.
          </p>
        </div>
      {:else if authState === "connecting"}
        <p class="state-loading">Connecting to the local Raiker runtime…</p>
      {:else if current === "home"}
        <Home />
      {:else if current === "approvals"}
        <ApprovalQueue />
      {:else if current === "capabilities"}
        <CapabilityMatrix />
      {:else if current === "runtime-gates"}
        <RuntimeGatesView />
      {:else if current === "models"}
        <ModelsView />
      {:else if current === "events"}
        <EventLogViewer />
      {:else if current === "checkpoints"}
        <CheckpointViewer />
      {:else if current === "diagnostics"}
        <DiagnosticsPanel />
      {:else}
        <Placeholder title={activeItem.label} />
      {/if}
    </main>
  </div>
</div>

<style>
  .app-shell {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.6rem 1rem;
    border-bottom: 1px solid #2a2a2e;
    background: #0a0a0d;
  }
  .app-body {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .content {
    flex: 1;
    padding: 1.25rem 1.5rem;
    overflow: auto;
  }
  .content:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: -2px;
  }
  .conn-error {
    border: 1px solid #5a2a2a;
    background: #1a0f0f;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    max-width: 64ch;
  }
  .conn-error code {
    color: #ffc9c0;
  }
  .state-loading {
    color: #9a9aa2;
  }
  .skip-link {
    position: absolute;
    left: -999px;
    top: 0;
    background: #1c2a3a;
    color: #cfe5ff;
    padding: 0.5rem 0.75rem;
    z-index: 100;
  }
  .skip-link:focus {
    left: 0.5rem;
    top: 0.5rem;
  }
</style>
