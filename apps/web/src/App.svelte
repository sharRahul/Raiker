<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Topbar from "./lib/components/Topbar.svelte";
  import { DEFAULT_ROUTE, navItem, routeFromHash } from "./lib/nav";
  import { api, connect } from "./lib/api";
  import type { ModelsView as ModelsSnapshot } from "./lib/apiTypes";
  import ChatView from "./lib/views/ChatView.svelte";
  import ApprovalsView from "./lib/views/ApprovalsView.svelte";
  import TasksView from "./lib/views/TasksView.svelte";
  import SessionsView from "./lib/views/SessionsView.svelte";
  import CapabilitiesView from "./lib/views/CapabilitiesView.svelte";
  import ModelsView from "./lib/views/ModelsView.svelte";
  import ConnectionsView from "./lib/views/ConnectionsView.svelte";
  import CheckpointsView from "./lib/views/CheckpointsView.svelte";
  import ActivityView from "./lib/views/ActivityView.svelte";
  import DiagnosticsView from "./lib/views/DiagnosticsView.svelte";
  import SettingsView from "./lib/views/SettingsView.svelte";

  let current = $state(
    typeof window === "undefined" ? DEFAULT_ROUTE : routeFromHash(window.location.hash),
  );
  const activeItem = $derived(navItem(current));

  let authState = $state<"connecting" | "ready" | "error">("connecting");
  let principal = $state("—");
  let runtimeMode = $state("—");
  let ready = $state(false);
  let models = $state<ModelsSnapshot | null>(null);

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
      const [mode, diag, modelsView] = await Promise.all([
        api.runtimeMode(),
        api.diagnostics(),
        api.models(),
      ]);
      runtimeMode = mode.mode_name;
      ready = diag.production_ready_local_single_user_runtime;
      models = modelsView;
      authState = "ready";
    } catch {
      authState = "error";
    }
  }
</script>

<a class="skip-link" href="#main">Skip to content</a>

<div class="app-shell">
  <Sidebar {current} />
  <div class="app-main">
    <Topbar
      title={activeItem.label}
      hint={activeItem.hint}
      {principal}
      {runtimeMode}
      {ready}
      {models}
      connecting={authState === "connecting"}
    />
    <main id="main" class="content" tabindex="-1">
      {#if authState === "error"}
        <div class="card conn-error" role="alert">
          <h2>Cannot reach the local Raiker API</h2>
          <p>
            Start the local server with <code>raiker-web</code> and ensure an owner is bootstrapped
            (<code>raiker</code> → <code>/bootstrap-owner</code>). The UI talks only to the local
            governed API and never fabricates data.
          </p>
          <button type="button" class="btn btn-primary" onclick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      {:else if authState === "connecting"}
        <p class="loading" role="status">Connecting to the local Raiker runtime…</p>
      {:else if current === "chat"}
        <ChatView />
      {:else if current === "approvals"}
        <ApprovalsView />
      {:else if current === "tasks"}
        <TasksView />
      {:else if current === "sessions"}
        <SessionsView />
      {:else if current === "capabilities"}
        <CapabilitiesView {principal} />
      {:else if current === "models"}
        <ModelsView />
      {:else if current === "connections"}
        <ConnectionsView />
      {:else if current === "checkpoints"}
        <CheckpointsView />
      {:else if current === "activity"}
        <ActivityView />
      {:else if current === "diagnostics"}
        <DiagnosticsView />
      {:else}
        <SettingsView {principal} />
      {/if}
    </main>
  </div>
</div>

<style>
  .app-shell {
    display: flex;
    height: 100vh;
  }
  .app-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .content {
    flex: 1;
    overflow: auto;
    padding: var(--space-5) var(--space-6);
    background: var(--bg);
  }
  .content:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }
  .conn-error {
    max-width: 40rem;
  }
  .loading {
    color: var(--text-2);
  }
</style>
