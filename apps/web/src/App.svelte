<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Topbar from "./lib/components/Topbar.svelte";
  import ResponsivePage from "./lib/components/ResponsivePage.svelte";
  import {
    DEFAULT_ROUTE,
    navItem,
    routeFromHash,
    tabFromHash,
  } from "./lib/nav";
  import { routeStateFromHash } from "./lib/routeState";
  import { api } from "./lib/api";
  import { applyUiPrefs, startupRoute } from "./lib/prefs.svelte";
  import type { ProjectsList } from "./lib/apiTypes";
  import LoginView from "./lib/views/LoginView.svelte";
  import ChatView from "./lib/views/ChatView.svelte";
  import BuildView from "./lib/views/BuildView.svelte";
  import SearchChatView from "./lib/views/SearchChatView.svelte";
  import MemoryView from "./lib/views/MemoryView.svelte";
  import ProjectsView from "./lib/views/ProjectsView.svelte";
  import ApprovalsView from "./lib/views/ApprovalsView.svelte";
  import TasksView from "./lib/views/TasksView.svelte";
  import BrainView from "./lib/views/BrainView.svelte";
  import SessionsView from "./lib/views/SessionsView.svelte";
  import CapabilitiesView from "./lib/views/CapabilitiesView.svelte";
  import ModelsView from "./lib/views/ModelsView.svelte";
  import ExtensionsView from "./lib/views/ExtensionsView.svelte";
  import ObserveView from "./lib/views/ObserveView.svelte";
  import SettingsView from "./lib/views/SettingsView.svelte";
  import WorkbenchView from "./lib/views/WorkbenchView.svelte";
  import ModelSetupView from "./lib/views/ModelSetupView.svelte";
  import ModelSetupDialog from "./lib/components/ModelSetupDialog.svelte";
  import ModelOperationTray from "./lib/components/ModelOperationTray.svelte";

  let current = $state(
    typeof window === "undefined"
      ? DEFAULT_ROUTE
      : routeFromHash(window.location.hash),
  );
  // The hub tab lives in the hash so a deep link, the sidebar, and the hub's own
  // tab strip all resolve to the same panel.
  let currentTab = $state(
    typeof window === "undefined" ? null : tabFromHash(window.location.hash),
  );
  let chatVisited = $state(false);
  // Build keeps its transcript, its unsent draft, and its streaming turn alive
  // across route visits for the same reason Chat does: a coding conversation is
  // long-running, and stepping over to Approvals must not throw it away.
  let buildVisited = $state(false);
  const activeItem = $derived(navItem(current));

  $effect(() => {
    if (current === "new-chat") chatVisited = true;
    if (current === "build") buildVisited = true;
  });

  // Honest auth/bootstrap state machine. The workspace shell mounts only in
  // "ready": authentication alone is not enough — the runtime must verify
  // (bootstrap reads succeed) first, and a failed verification stays locked.
  let authState = $state<
    "locked" | "verifying" | "ready" | "verification_failed"
  >("locked");
  let principal = $state("—");
  let projects = $state<ProjectsList | null>(null);
  const activeProjectId = $derived(projects?.active_project_id ?? null);
  let continuedSessionId = $state<string | null>(
    typeof window === "undefined"
      ? null
      : routeStateFromHash(window.location.hash).sessionId,
  );

  onMount(() => {
    const handler = () => {
      current = routeFromHash(window.location.hash);
      currentTab = tabFromHash(window.location.hash);
      continuedSessionId = routeStateFromHash(window.location.hash).sessionId;
      // Route changes move focus to the main landmark so keyboard and screen
      //-reader users land on the new page content, not mid-shell.
      document.getElementById("main")?.focus();
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
      const [, , projectsList, setup] = await Promise.all([
        api.runtimeMode(),
        api.diagnostics(),
        api.projects(),
        api.modelSetup(),
      ]);
      projects = projectsList;
      if (setup.status === "required" || setup.status === "in_progress") {
        window.location.hash = "#/model-setup";
        current = "model-setup";
      }
      authState = "ready";
      // Preferences are presentation only, so a failed read never locks the
      // workspace: spacing/font/notifications apply, and the saved startup
      // route wins only when the URL doesn't already name a route.
      try {
        const s = await api.settings();
        applyUiPrefs(s.settings);
        const route = startupRoute(s.settings);
        const hash = window.location.hash.replace(/^#\/?/, "");
        if (route !== null && hash === "") {
          window.location.hash = `#/${route}`;
          current = route;
        }
      } catch {
        // Defaults stay in effect.
      }
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
        <!-- The topbar already shows the route title + hint; the page itself
           opens with its own lead so nothing is said twice. -->
        <ResponsivePage>
          {#if current === "model-setup"}
            <ModelSetupView />
          {:else if chatVisited}
            <div hidden={current !== "new-chat"}>
              <ChatView
                sessionId={continuedSessionId}
                {projects}
                onProjectsChanged={refreshProjects}
              />
            </div>
          {/if}
          {#if buildVisited}
            <div hidden={current !== "build"}>
              <BuildView
                {projects}
                onProjectsChanged={refreshProjects}
                visible={current === "build"}
              />
            </div>
          {/if}
          {#if current === "home"}
            <WorkbenchView />
          {:else if current === "search-chat"}
            <SearchChatView />
          {:else if current === "memory"}
            <MemoryView />
          {:else if current === "approvals"}
            <ApprovalsView sessionId={continuedSessionId} />
          {:else if current === "tasks"}
            <TasksView
              projectId={activeProjectId}
              sessionId={continuedSessionId}
            />
          {:else if current === "brain"}
            <BrainView />
          {:else if current === "sessions"}
            <SessionsView
              projectId={activeProjectId}
              sessionId={continuedSessionId}
            />
          {:else if current === "projects"}
            <ProjectsView onchanged={refreshProjects} />
          {:else if current === "capabilities"}
            <CapabilitiesView {principal} />
          {:else if current === "models"}
            <ModelsView tab={currentTab ?? "providers"} />
          {:else if current === "extensions"}
            <ExtensionsView tab={currentTab ?? "connectors"} />
          {:else if current === "observe"}
            <ObserveView
              tab={currentTab ?? "overview"}
              sessionId={continuedSessionId}
              projectId={activeProjectId}
            />
          {:else if current !== "new-chat" && current !== "build"}
            <SettingsView {principal} tab={currentTab ?? "general"} />
          {/if}
        </ResponsivePage>
      </main>
    </div>
  </div>
  <ModelSetupDialog />
  <ModelOperationTray />
{/if}

<style>
  /* The shell *is* the viewport. Clipping here is what guarantees the sidebar
     and topbar can never scroll away: whatever a page renders, the only thing
     that scrolls is `.content`. Without it a page that overflows its column
     hands the overflow to the document, and the whole shell — navigation
     included — slides up with the content. */
  .app-shell {
    display: flex;
    height: 100vh;
    height: 100dvh;
    overflow: hidden;
  }
  .app-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    /* Flex items refuse to shrink below their content unless told otherwise;
       without this the column grows past the shell and takes the scroll with it. */
    min-height: 0;
  }
  .content {
    flex: 1;
    min-height: 0;
    overflow: auto;
    /* Containing block for absolutely-positioned descendants. Without it an
       element that has no positioned ancestor — a visually-hidden `.sr-only`
       label, say — resolves against the viewport instead of this scroller and
       reports its offset as root overflow, which some browsers answer with a
       stray page scrollbar. */
    position: relative;
    padding: var(--space-5) var(--space-6);
    background: var(--bg);
    /* The room a page has between the topbar and the bottom of the viewport.
       Views that pin a footer — a chat composer — size themselves from this
       instead of re-deriving the shell's padding, so they stay correct when the
       padding changes at a breakpoint. */
    --content-h: calc(100dvh - var(--topbar-h) - var(--space-5) * 2);
  }
  .content:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }
  @media (max-width: 639px) {
    .content {
      padding: var(--space-4) var(--space-3)
        calc(var(--space-5) + 4rem + env(safe-area-inset-bottom));
      /* Same room, minus the phone bottom navigation the padding reserves. */
      --content-h: calc(
        100dvh - var(--topbar-h) - var(--space-4) - var(--space-5) - 4rem -
          env(safe-area-inset-bottom)
      );
    }
  }
</style>
