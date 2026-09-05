<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Topbar from "./lib/components/Topbar.svelte";
  import AllPagesDialog from "./lib/components/AllPagesDialog.svelte";
  import ResponsivePage from "./lib/components/ResponsivePage.svelte";
  import {
    DEFAULT_ROUTE,
    navItem,
    routeFromHash,
    sectionFromHash,
    tabFromHash,
  } from "./lib/nav";
  import { routeStateFromHash } from "./lib/routeState";
  import { api } from "./lib/api";
  import { applyUiPrefs, startupRoute } from "./lib/prefs.svelte";
  import type { ProjectsList } from "./lib/apiTypes";
  import LoginView from "./lib/views/LoginView.svelte";
  import ChatView from "./lib/views/ChatView.svelte";
  import BuildView from "./lib/views/BuildView.svelte";
  import WorkbenchView from "./lib/views/WorkbenchView.svelte";
  // BUG-74 — every other destination is code-split. Workbench, Chat and Build
  // stay eager: they are what a session opens with, and Chat and Build also stay
  // mounted across route visits to keep their transcripts alive.
  import LazyRoute from "./lib/components/LazyRoute.svelte";
  import { prefetchRoutes } from "./lib/routeComponents";
  import { startReadinessRevalidation } from "./lib/modelReadiness.svelte";
  import ApprovalPrompt from "./lib/components/ApprovalPrompt.svelte";
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
  // The guide page a deep link names, so "Learn more" from another surface can
  // open the section it means rather than the guide's front page.
  let currentSection = $state(
    typeof window === "undefined" ? null : sectionFromHash(window.location.hash),
  );
  let chatVisited = $state(false);
  // Build keeps its transcript, its unsent draft, and its streaming turn alive
  // across route visits for the same reason Chat does: a coding conversation is
  // long-running, and stepping over to Approvals must not throw it away.
  let buildVisited = $state(false);
  const activeItem = $derived(navItem(current));
  let compactNavigation = $state(false);
  let desktopNavigationOpen = $state(true);
  let navigationDrawerOpen = $state(false);
  let navigationTrigger = $state<HTMLElement | null>(null);
  // The gear's window. Manage, Observe and Support left the sidebar for it, so
  // this is the only place several destinations are linked from — `nav.ts`
  // still holds them all, because routing resolves against that list.
  let allPagesOpen = $state(false);
  let allPagesTrigger = $state<HTMLElement | null>(null);
  function openAllPages(trigger: HTMLElement) {
    allPagesTrigger = trigger;
    allPagesOpen = !allPagesOpen;
  }
  let appMain = $state<HTMLElement>();
  const pageLayout = $derived(
    // Design joins Chat and Build here: all three are a transcript that fills
    // the room the shell gives it, with a composer on the floor of the page.
    current === "new-chat" || current === "build" || current === "design"
      ? "work-surface" as const
      : current === "search-chat" || current === "guide"
        ? "reading" as const
        : current === "models" || current === "extensions" || current === "observe" ||
            current === "home" || current === "tasks" || current === "projects" ||
            current === "memory" || current === "brain" || current === "approvals" ||
            current === "capabilities"
          ? "operational" as const
          : "workspace" as const,
  );

  function toggleNavigation(trigger: HTMLElement) {
    navigationTrigger = trigger;
    if (compactNavigation) {
      navigationDrawerOpen = !navigationDrawerOpen;
      return;
    }
    desktopNavigationOpen = !desktopNavigationOpen;
    localStorage.setItem("raiker.navigation.desktop", String(desktopNavigationOpen));
  }

  function closeNavigationDrawer() {
    navigationDrawerOpen = false;
  }

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
  let continuedSessionId = $state<string | null>(
    typeof window === "undefined"
      ? null
      : routeStateFromHash(window.location.hash).sessionId,
  );
  // MEM-08 — the exchange a link is pointing at inside that conversation. It
  // travels with the session id and nothing else reads it: only Chat and Build
  // render a transcript to land in.
  let anchoredTurnId = $state<string | null>(
    typeof window === "undefined"
      ? null
      : routeStateFromHash(window.location.hash).turnId,
  );

  onMount(() => {
    // BUG-253 — a refresh used to land on the unlock screen, which is exactly
    // what applying a UI change asks an owner to do. The session now rides in an
    // HttpOnly cookie, so the question "is this browser still signed in?" has an
    // answer, and only the server can give it.
    void api.restoreSession().then((principalId) => {
      if (principalId !== null) onAuthenticated(principalId);
    });
    desktopNavigationOpen = localStorage.getItem("raiker.navigation.desktop") !== "false";
    const navigationQuery = typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 1023px)")
      : null;
    const updateNavigationMode = () => {
      compactNavigation = navigationQuery?.matches ?? false;
      if (!compactNavigation) navigationDrawerOpen = false;
    };
    updateNavigationMode();
    navigationQuery?.addEventListener("change", updateNavigationMode);
    const handler = () => {
      navigationDrawerOpen = false;
      current = routeFromHash(window.location.hash);
      currentTab = tabFromHash(window.location.hash);
      currentSection = sectionFromHash(window.location.hash);
      continuedSessionId = routeStateFromHash(window.location.hash).sessionId;
      anchoredTurnId = routeStateFromHash(window.location.hash).turnId;
      // Route changes move focus to the main landmark so keyboard and screen
      //-reader users land on the new page content, not mid-shell.
      document.getElementById("main")?.focus();
    };
    window.addEventListener("hashchange", handler);
    // BUG-83 — while a work surface is open, the selected model's readiness is
    // re-confirmed in the background as its window runs down, so a long session
    // does not spontaneously disable Send.
    const stopRevalidation = startReadinessRevalidation();
    // Warm the split route chunks off the critical path, so the first click on
    // a secondary destination is as instant as it was in the single-chunk build.
    prefetchRoutes();
    return () => {
      window.removeEventListener("hashchange", handler);
      navigationQuery?.removeEventListener("change", updateNavigationMode);
      stopRevalidation();
    };
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
        api.setup(),
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

  // One projects snapshot for the whole shell, so Build's selector and the
  // Projects page never disagree about what exists. It is a *list*, not an
  // application-wide selection: a project no longer silently retargets other
  // routes, which is why the list views below no longer receive one.
  async function refreshProjects() {
    try {
      projects = await api.projects();
    } catch {
      // Keep the last known snapshot.
    }
  }

</script>

<a class="skip-link" href="#main">Skip to content</a>

{#if authState !== "ready"}
  <LoginView {onAuthenticated} runtimeState={authState} />
{:else}
  <div class="app-shell" data-navigation-open={compactNavigation ? navigationDrawerOpen : desktopNavigationOpen}>
    <Sidebar
      {current}
      desktopOpen={desktopNavigationOpen}
      drawerOpen={navigationDrawerOpen}
      compact={compactNavigation}
      returnFocusTo={navigationTrigger}
      backgroundElement={appMain}
      onDrawerClose={closeNavigationDrawer}
    />
    <div class="app-main" bind:this={appMain}>
      <Topbar
        title={activeItem.label}
        hint={activeItem.hint}
        navigationOpen={compactNavigation ? navigationDrawerOpen : desktopNavigationOpen}
        {compactNavigation}
        onNavigationToggle={toggleNavigation}
        onOpenAllPages={openAllPages}
      />
      <AllPagesDialog
        open={allPagesOpen}
        {current}
        returnFocusTo={allPagesTrigger}
        onClose={() => (allPagesOpen = false)}
      />
      <main id="main" class="content" tabindex="-1">
        <!-- The topbar already shows the route title + hint; the page itself
           opens with its own lead so nothing is said twice. -->
        <ResponsivePage layout={pageLayout}>
          {#if current === "model-setup"}
            <LazyRoute route="model-setup" />
          {:else if chatVisited}
            <div hidden={current !== "new-chat"}>
              <ChatView
                sessionId={current === "new-chat" ? continuedSessionId : null}
                anchoredTurnId={current === "new-chat" ? anchoredTurnId : null}
                {projects}
                onProjectsChanged={refreshProjects}
                visible={current === "new-chat"}
              />
            </div>
          {/if}
          {#if buildVisited}
            <div hidden={current !== "build"}>
              <BuildView
                sessionId={current === "build" ? continuedSessionId : null}
                anchoredTurnId={current === "build" ? anchoredTurnId : null}
                {projects}
                onProjectsChanged={refreshProjects}
                visible={current === "build"}
              />
            </div>
          {/if}
          {#if current === "home"}
            <WorkbenchView />
          {:else if current === "search-chat"}
            <LazyRoute route="search-chat" />
          {:else if current === "memory"}
            <LazyRoute route="memory" />
          {:else if current === "approvals"}
            <LazyRoute
              route="approvals"
              props={{ sessionId: continuedSessionId }}
            />
          {:else if current === "tasks"}
            <LazyRoute
              route="tasks"
              props={{ sessionId: continuedSessionId }}
            />
          {:else if current === "brain"}
            <LazyRoute route="brain" />
          {:else if current === "sessions"}
            <LazyRoute
              route="sessions"
              props={{ sessionId: continuedSessionId }}
            />
          {:else if current === "projects"}
            <LazyRoute
              route="projects"
              props={{ onchanged: refreshProjects }}
            />
          {:else if current === "capabilities"}
            <LazyRoute route="capabilities" props={{ principal }} />
          {:else if current === "models"}
            <LazyRoute
              route="models"
              props={{ tab: currentTab ?? "providers" }}
            />
          {:else if current === "extensions"}
            <LazyRoute
              route="extensions"
              props={{ tab: currentTab ?? "connectors" }}
            />
          {:else if current === "messaging"}
            <LazyRoute route="messaging" />
          {:else if current === "design"}
            <LazyRoute route="design" />
          {:else if current === "guide"}
            <LazyRoute route="guide" props={{ section: currentSection }} />
          {:else if current === "observe"}
            <LazyRoute
              route="observe"
              props={{
                tab: currentTab ?? "overview",
                sessionId: continuedSessionId,
              }}
            />
            <!-- Settings is the fallback route, so every guard that renders
                 something else above has to be repeated here. `model-setup` is
                 handled by the first block, not this chain, so without naming
                 it the first-run sheet rendered with the whole Settings page
                 stacked underneath it. -->
          {:else if
            current !== "new-chat" &&
            current !== "build" &&
            current !== "guide" &&
            current !== "model-setup"}
            <LazyRoute
              route="settings"
              props={{ principal, tab: currentTab ?? "general" }}
            />
          {/if}
        </ResponsivePage>
      </main>
    </div>
  </div>
  <ModelSetupDialog />
  <ApprovalPrompt />
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
    background: var(--bg);
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
    padding: var(--space-5) var(--content-gutter);
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
      padding: var(--space-4) var(--space-3) calc(var(--space-5) + env(safe-area-inset-bottom));
      --content-h: calc(100dvh - var(--topbar-h) - var(--space-4) - var(--space-5));
    }
  }
</style>
