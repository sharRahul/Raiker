<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Topbar from "./lib/components/Topbar.svelte";
  import { DEFAULT_ROUTE, navItem, routeFromHash } from "./lib/nav";
  import { api } from "./lib/api";
  import type { ModelsView as ModelsSnapshot, ProjectsList } from "./lib/apiTypes";
  import LoginView from "./lib/views/LoginView.svelte";
  import ChatView from "./lib/views/ChatView.svelte";
  import SearchChatView from "./lib/views/SearchChatView.svelte";
  import ProjectsView from "./lib/views/ProjectsView.svelte";
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

  let authenticated = $state(false);
  let authState = $state<"locked" | "authenticating" | "verifying" | "ready" | "error">("locked");
  let principal = $state("—");
  let runtimeMode = $state("—");
  let ready = $state(false);
  let models = $state<ModelsSnapshot | null>(null);
  let projects = $state<ProjectsList | null>(null);
  const activeProjectId = $derived(projects?.active_project_id ?? null);

  onMount(() => {
    const handler = () => {
      current = routeFromHash(window.location.hash);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  });

  // Called by the lock screen once a full control session exists.
  function onAuthenticated(principalId: string) {
    principal = principalId;
    authState = "verifying";
    void bootstrap();
  }

  async function bootstrap() {
    try {
      const [mode, diag, modelsView, projectsList] = await Promise.all([
        api.runtimeMode(),
        api.diagnostics(),
        api.models(),
        api.projects(),
      ]);
      runtimeMode = mode.mode_name;
      ready = diag.production_ready_local_single_user_runtime;
      models = modelsView;
      projects = projectsList;
      authenticated = true;
      authState = "ready";
    } catch {
      authenticated = false;
      authState = "error";
    }
  }

  // Re-read the models snapshot when the Models view changes the selection so
  // the topbar chip keeps telling the truth without a full reload.
  async function refreshModels() {
    try {
      models = await api.models();
    } catch {
      // Keep the last known snapshot; the chip never fabricates data.
    }
  }

  // Same for projects: the Projects view and the topbar switcher share one
  // snapshot so the active project reads identically everywhere.
  async function refreshProjects() {
    try {
      projects = await api.projects();
    } catch {
      // Keep the last known snapshot.
    }
  }

  async function selectProject(projectId: string | null) {
    try {
      await api.selectProject(projectId);
    } catch {
      // Server refused (e.g. not gate-manager); the refresh below re-reads truth.
    }
    await refreshProjects();
  }
</script>

<a class="skip-link" href="#main">Skip to content</a>

{#if !authenticated}
  <LoginView
    {onAuthenticated}
    runtimeState={authState === "verifying" ? "verifying" : authState === "error" ? "verification_failed" : "locked"}
  />
{:else}
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
      {projects}
      onProjectSelect={selectProject}
      connecting={authState === "verifying"}
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
      {:else if authState === "verifying"}
        <p class="loading" role="status">Verifying the local Raiker runtime…</p>
      {:else if current === "new-chat"}
        <ChatView />
      {:else if current === "search-chat"}
        <SearchChatView />
      {:else if current === "approvals"}
        <ApprovalsView />
      {:else if current === "tasks"}
        <TasksView />
      {:else if current === "sessions"}
        <SessionsView projectId={activeProjectId} />
      {:else if current === "projects"}
        <ProjectsView onchanged={refreshProjects} />
      {:else if current === "capabilities"}
        <CapabilitiesView {principal} />
      {:else if current === "models"}
        <ModelsView onchanged={refreshModels} />
      {:else if current === "connections"}
        <ConnectionsView />
      {:else if current === "checkpoints"}
        <CheckpointsView projectId={activeProjectId} />
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
{/if}

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
