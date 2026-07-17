<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Topbar from "./lib/components/Topbar.svelte";
  import { DEFAULT_ROUTE, navItem, routeFromHash } from "./lib/nav";
  import { api } from "./lib/api";
  import type { ProjectsList } from "./lib/apiTypes";
  import LoginView from "./lib/views/LoginView.svelte";
  import ChatView from "./lib/views/ChatView.svelte";
  import SearchChatView from "./lib/views/SearchChatView.svelte";
  import MemoryView from "./lib/views/MemoryView.svelte";
  import ProjectsView from "./lib/views/ProjectsView.svelte";
  import ApprovalsView from "./lib/views/ApprovalsView.svelte";
  import TasksView from "./lib/views/TasksView.svelte";
  import BrainView from "./lib/views/BrainView.svelte";
  import WorkInActionView from "./lib/views/WorkInActionView.svelte";
  import SessionsView from "./lib/views/SessionsView.svelte";
  import CapabilitiesView from "./lib/views/CapabilitiesView.svelte";
  import ModelsView from "./lib/views/ModelsView.svelte";
  import ConnectionsView from "./lib/views/ConnectionsView.svelte";
  import McpView from "./lib/views/McpView.svelte";
  import CheckpointsView from "./lib/views/CheckpointsView.svelte";
  import ActivityView from "./lib/views/ActivityView.svelte";
  import DiagnosticsView from "./lib/views/DiagnosticsView.svelte";
  import SettingsView from "./lib/views/SettingsView.svelte";

  let current = $state(
    typeof window === "undefined" ? DEFAULT_ROUTE : routeFromHash(window.location.hash),
  );
  const activeItem = $derived(navItem(current));

  // Honest auth/bootstrap state machine. The workspace shell mounts only in
  // "ready": authentication alone is not enough — the runtime must verify
  // (bootstrap reads succeed) first, and a failed verification stays locked.
  let authState = $state<"locked" | "verifying" | "ready" | "verification_failed">("locked");
  let principal = $state("—");
  let projects = $state<ProjectsList | null>(null);
  const activeProjectId = $derived(projects?.active_project_id ?? null);
  const continuedSessionId = $derived(typeof window === "undefined" ? null : new URLSearchParams(window.location.hash.split("?")[1]).get("session"));

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
      const [, , projectsList] = await Promise.all([
        api.runtimeMode(),
        api.diagnostics(),
        api.projects(),
      ]);
      projects = projectsList;
      authState = "ready";
    } catch {
      // Fail closed: the workspace stays unmounted behind the lock screen.
      authState = "verification_failed";
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

{#if authState !== "ready"}
  <LoginView {onAuthenticated} runtimeState={authState} />
{:else}
<div class="app-shell">
  <Sidebar {current} />
  <div class="app-main">
    <Topbar
      title={activeItem.label}
      hint={activeItem.hint}
      {projects}
      onProjectSelect={selectProject}
    />
    <main id="main" class="content" tabindex="-1">
      {#if current === "new-chat"}
        <ChatView sessionId={continuedSessionId} />
      {:else if current === "search-chat"}
        <SearchChatView />
      {:else if current === "memory"}
        <MemoryView />
      {:else if current === "approvals"}
        <ApprovalsView />
      {:else if current === "tasks"}
        <TasksView projectId={activeProjectId} />
      {:else if current === "brain"}
        <BrainView />
      {:else if current === "work"}
        <WorkInActionView />
      {:else if current === "sessions"}
        <SessionsView projectId={activeProjectId} />
      {:else if current === "projects"}
        <ProjectsView onchanged={refreshProjects} />
      {:else if current === "capabilities"}
        <CapabilitiesView {principal} />
      {:else if current === "models"}
        <ModelsView />
      {:else if current === "connections"}
        <ConnectionsView />
      {:else if current === "mcp"}
        <McpView />
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
</style>
