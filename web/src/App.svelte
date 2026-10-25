<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import Topbar from "./lib/components/Topbar.svelte";
  import AllPagesDialog from "./lib/components/AllPagesDialog.svelte";
  import { rememberPage } from "./lib/recentPages";
  import CommandPalette from "./lib/components/CommandPalette.svelte";
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
  import WorkbenchView from "./lib/views/WorkbenchView.svelte";
  // BUG-74 — every other destination is code-split. Workbench, Chat and Build
  // stay eager: they are what a session opens with, and Chat and Build also stay
  // mounted across route visits to keep their transcripts alive.
  import LazyRoute from "./lib/components/LazyRoute.svelte";
  import { prefetchRoutes } from "./lib/routeComponents";
  import { mayLeave } from "./lib/leaveGuard";
  import { DESKTOP_COMMAND_EVENT, desktopBridge, inDesktopShell } from "./lib/desktopShell";
  import { startReadinessRevalidation } from "./lib/modelReadiness.svelte";
  import ApprovalPrompt from "./lib/components/ApprovalPrompt.svelte";
  // REM-SET-NOTIFY — unread notices belong wherever the owner is. The strip was
  // mounted on the MCP page alone, so the account-wide "In-app popups" setting
  // decided whether a banner appeared on one destination.
  import NotificationCenter from "./lib/components/NotificationCenter.svelte";
  import ModelSetupDialog from "./lib/components/ModelSetupDialog.svelte";
  import ModelOperationTray from "./lib/components/ModelOperationTray.svelte";
  import HelpPanel from "./lib/components/HelpPanel.svelte";
  import ConfirmDialog from "./lib/components/ConfirmDialog.svelte";
  import { helpSlugFromHash, isHelpAddress, openHelp } from "./lib/help.svelte";
  import { movedSettingsAddress } from "./lib/settingsSections";

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
  // UX-MEM-03 — a list filter a deep link names (`#/memory?tab=memories&filter=archived`),
  // so a count on an overview can open the records it counted.
  let currentFilter = $state<string | null>(
    typeof window === "undefined" ? null : routeStateFromHash(window.location.hash).filter,
  );
  // QUI-F22 — one memory a link names (`#/memory?tab=memories&record=…`).
  let currentRecord = $state<string | null>(
    typeof window === "undefined" ? null : routeStateFromHash(window.location.hash).recordId,
  );
  let chatVisited = $state(false);
  // Build keeps its transcript, its unsent draft, and its streaming turn alive
  // across route visits for the same reason Chat does: a coding conversation is
  // long-running, and stepping over to Approvals must not throw it away.
  let buildVisited = $state(false);
  const activeItem = $derived(navItem(current));
  let compactNavigation = $state(false);
  let desktopNavigationOpen = $state(true);
  // QUI-L14 — a 1,024–1,279 px window draws the sidebar as its 64 px icon rail.
  // The toggle can still widen it for a moment; that choice is not saved, so a
  // wider window goes back to the owner's own setting.
  let narrowWindow = $state(false);
  let narrowNavigationOpen = $state(false);
  const sidebarOpen = $derived(narrowWindow ? narrowNavigationOpen : desktopNavigationOpen);
  let navigationDrawerOpen = $state(false);
  let navigationTrigger = $state<HTMLElement | null>(null);
  // The gear's window. Manage, Observe and Support left the sidebar for it, so
  // this is the only place several destinations are linked from — `nav.ts`
  // still holds them all, because routing resolves against that list.
  let allPagesOpen = $state(false);
  let allPagesTrigger = $state<HTMLElement | null>(null);
  // UX-SETPOP-02 — the places this viewer opened last, for More's Recent group.
  $effect(() => {
    rememberPage(current);
  });
  function openAllPages(trigger: HTMLElement) {
    allPagesTrigger = trigger;
    allPagesOpen = !allPagesOpen;
  }
  // The launcher that lets the rail be short. Ctrl/Cmd+K from
  // anywhere, including from inside a field, because that is the one shortcut
  // people expect to work while they are typing.
  let paletteOpen = $state(false);
  let paletteTrigger = $state<HTMLElement | null>(null);
  let appMain = $state<HTMLElement>();
  const pageLayout = $derived(
    // Design joins Chat and Build here: all three are a transcript that fills
    // the room the shell gives it, with a composer on the floor of the page.
    current === "new-chat" || current === "build" || current === "design"
      ? "work-surface" as const
      : current === "models" || current === "connections" || current === "observe" ||
            current === "home" || current === "work" ||
            current === "memory" || current === "approvals" ||
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
    if (narrowWindow) {
      narrowNavigationOpen = !narrowNavigationOpen;
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
  /**
   * DEC-01 — who the owner is *to read*: their display name, never the internal
   * principal id. Pages show it in the step-up window ("Acting as …"); the
   * server knows who is acting from the session and never takes it from here.
   */
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
  // BUG-299 — the task a link is pointing at. Only Tasks reads it, and it opens
  // that task's attempt history over the board rather than instead of it.
  let openTaskId = $state<string | null>(
    typeof window === "undefined"
      ? null
      : routeStateFromHash(window.location.hash).taskId,
  );

  onMount(() => {
    // BUG-253 — a refresh keeps the session: it rides in an HttpOnly cookie, so
    // "is this browser still signed in?" has an answer, and only the server can
    // give it.
    void api.restoreSession().then((principalId) => {
      if (principalId !== null) onAuthenticated();
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
    const narrowQuery = typeof window.matchMedia === "function"
      ? window.matchMedia("(min-width: 1024px) and (max-width: 1279px)")
      : null;
    const updateNarrowWindow = () => {
      narrowWindow = narrowQuery?.matches ?? false;
      narrowNavigationOpen = false;
    };
    updateNarrowWindow();
    narrowQuery?.addEventListener("change", updateNarrowWindow);
    // DEC-09 step 5 — the address the shell last showed, so a page that asks
    // to stay (unsaved work) can be stayed on: the address is put back without
    // a second hashchange and nothing below runs.
    // QUI-L10 — a guide address opens the help panel over the page the owner
    // is on; it is no longer a page of its own.
    if (isHelpAddress(window.location.hash)) {
      openHelp(helpSlugFromHash(window.location.hash));
      history.replaceState(history.state, "", `#/${current}`);
    }
    // QUI-L09 — a Settings section that moved to another page (GitHub went to
    // Connections) forwards there.
    const movedAtStart = movedSettingsAddress(window.location.hash);
    if (movedAtStart !== null) window.location.replace(movedAtStart);
    let shownHash = window.location.hash;
    const handler = () => {
      if (isHelpAddress(window.location.hash)) {
        openHelp(helpSlugFromHash(window.location.hash));
        history.replaceState(history.state, "", shownHash || "#/");
        return;
      }
      const moved = movedSettingsAddress(window.location.hash);
      if (moved !== null) {
        window.location.replace(moved);
        return;
      }
      if (window.location.hash !== shownHash && !mayLeave(window.location.hash)) {
        history.replaceState(history.state, "", shownHash || "#/");
        return;
      }
      shownHash = window.location.hash;
      navigationDrawerOpen = false;
      // UX-SETPOP-03 — More is navigation: any route change, including the
      // browser's Back, closes it, so the sheet never stands over a page it did
      // not open.
      allPagesOpen = false;
      current = routeFromHash(window.location.hash);
      currentTab = tabFromHash(window.location.hash);
      currentFilter = routeStateFromHash(window.location.hash).filter;
      currentRecord = routeStateFromHash(window.location.hash).recordId;
      continuedSessionId = routeStateFromHash(window.location.hash).sessionId;
      anchoredTurnId = routeStateFromHash(window.location.hash).turnId;
      openTaskId = routeStateFromHash(window.location.hash).taskId;
      // Route changes move focus to the main landmark so keyboard and screen
      //-reader users land on the new page content, not mid-shell.
      document.getElementById("main")?.focus();
    };
    window.addEventListener("hashchange", handler);
    // Ctrl/Cmd+K opens the palette from anywhere. Deliberately not
    // gated on "is a field focused": this is the one shortcut people press
    // *while* typing, and a launcher that refuses mid-sentence is not a
    // launcher. `preventDefault` stops the browser's own find-in-page binding.
    const openPalette = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        paletteTrigger = document.activeElement as HTMLElement | null;
        paletteOpen = true;
      }
    };
    window.addEventListener("keydown", openPalette);
    // The desktop window's menu sends the same two shell controls a click or
    // Ctrl/Cmd+K reaches; routes it handles itself (`desktopShell.ts`).
    const onDesktopCommand = (event: Event) => {
      const command = (event as CustomEvent<string>).detail;
      if (command === "open-palette") {
        paletteTrigger = document.activeElement as HTMLElement | null;
        paletteOpen = true;
      } else if (command === "toggle-navigation") {
        const trigger = document.querySelector<HTMLElement>(".navigation-toggle");
        if (trigger !== null) toggleNavigation(trigger);
      }
    };
    window.addEventListener(DESKTOP_COMMAND_EVENT, onDesktopCommand);
    // Warm the split route chunks off the critical path, so the first click on
    // a secondary destination is as instant as it was in the single-chunk build.
    prefetchRoutes();
    return () => {
      window.removeEventListener("hashchange", handler);
      window.removeEventListener("keydown", openPalette);
      window.removeEventListener(DESKTOP_COMMAND_EVENT, onDesktopCommand);
      navigationQuery?.removeEventListener("change", updateNavigationMode);
      narrowQuery?.removeEventListener("change", updateNarrowWindow);
    };
  });

  // BUG-83 — while a work surface is open, the selected model's readiness is
  // re-confirmed in the background as its window runs down, so a long session
  // does not spontaneously disable Send. Only once the shell is ready: a stale
  // CSRF cookie from an earlier workspace on this host reads as "signed in"
  // until the boot probe says otherwise, and asking before then logged a 401.
  $effect(() => {
    if (authState !== "ready") return;
    return startReadinessRevalidation();
  });

  // Called by the lock screen once a full control session exists.
  function onAuthenticated() {
    principal = "you";
    authState = "verifying";
    void api
      .whoami()
      .then((me) => {
        principal = me.display_name || "you";
      })
      .catch(() => {});
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

  /** Quick Entry before sign-in: the main window holds the lock screen. */
  function openMainToSignIn(): void {
    const bridge = desktopBridge();
    if (bridge?.showMainWindow) bridge.showMainWindow();
    else window.location.hash = "#/home";
  }
</script>

<a class="skip-link" href="#main">Skip to content</a>

{#if authState !== "ready" && current === "quick-entry"}
  <!-- Quick Entry before sign-in: the 560×120 window cannot hold the lock
       screen, so it says what is needed and opens the main window for it. -->
  <main id="main" class="quick-entry-focus quick-entry-locked" tabindex="-1">
    <p><strong>Sign in to Raiker first.</strong> Quick Entry works once Raiker is unlocked.</p>
    <button type="button" class="btn btn-primary btn-sm" onclick={openMainToSignIn}>Open Raiker</button>
  </main>
{:else if authState !== "ready"}
  {#if inDesktopShell()}
    <!-- The desktop window has no native title bar. Before sign-in there is no
         top bar to drag it by, so this strip is that handle. -->
    <div class="desktop-drag-strip" aria-hidden="true"></div>
  {/if}
  <LoginView {onAuthenticated} runtimeState={authState} />
{:else if current === "quick-entry"}
  <!-- QUI-F01 — Quick Entry: the small window the desktop opens from anywhere
       on the computer. One input and a "send to" picker; no shell around it. -->
  <main id="main" class="quick-entry-focus" tabindex="-1">
    <LazyRoute route="quick-entry" />
  </main>
{:else if current === "model-setup"}
  <!-- First-run setup is a focused sheet: no navigation, top bar or palette
       around it, the way the desktop Setup window before sign-in has none.
       Its own links (Advanced setup, Review permissions) still lead into the
       app, which then opens with its navigation as usual. -->
  {#if inDesktopShell()}
    <div class="desktop-drag-strip" aria-hidden="true"></div>
  {/if}
  <main id="main" class="setup-focus" tabindex="-1">
    <LazyRoute route="model-setup" />
  </main>
{:else}
  <div class="app-shell" data-navigation-open={compactNavigation ? navigationDrawerOpen : sidebarOpen}>
    <Sidebar
      {current}
      desktopOpen={sidebarOpen}
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
        {current}
        quietHeader={pageLayout === "work-surface"}
        navigationOpen={compactNavigation ? navigationDrawerOpen : sidebarOpen}
        {compactNavigation}
        onNavigationToggle={toggleNavigation}
        onOpenAllPages={openAllPages}
        onOpenHelp={() => openHelp(null)}
        onOpenPalette={() => {
          paletteTrigger = document.activeElement as HTMLElement | null;
          paletteOpen = true;
        }}
      />
      <CommandPalette
        open={paletteOpen}
        returnFocusTo={paletteTrigger}
        onClose={() => (paletteOpen = false)}
      />
      <AllPagesDialog
        open={allPagesOpen}
        {current}
        returnFocusTo={allPagesTrigger}
        onClose={() => (allPagesOpen = false)}
        onOpenPalette={() => {
          paletteTrigger = allPagesTrigger;
          paletteOpen = true;
        }}
      />
      <main id="main" class="content" tabindex="-1">
        <!-- The topbar already shows the route title + hint; the page itself
           opens with its own lead so nothing is said twice. -->
        <ResponsivePage layout={pageLayout}>
          {#if chatVisited}
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
          {:else if current === "work"}
            <LazyRoute
              route="work"
              props={{
                tab: currentTab ?? "threads",
                sessionId: continuedSessionId,
                projects,
                taskId: openTaskId,
                onchanged: refreshProjects,
              }}
            />
          {:else if current === "memory"}
            <LazyRoute route="memory" props={{ tab: currentTab ?? "overview", filter: currentFilter, record: currentRecord }} />
          {:else if current === "approvals"}
            <LazyRoute
              route="approvals"
              props={{ sessionId: continuedSessionId }}
            />
          {:else if current === "sessions"}
            <LazyRoute
              route="sessions"
              props={{ sessionId: continuedSessionId }}
            />
          {:else if current === "capabilities"}
            <LazyRoute route="capabilities" props={{ principal }} />
          {:else if current === "models"}
            <LazyRoute route="models" />
          {:else if current === "connections"}
            <LazyRoute
              route="extensions"
              props={{ tab: currentTab ?? "services" }}
            />
          {:else if current === "design"}
            <LazyRoute route="design" props={{ projects }} />
          {:else if current === "state-gallery"}
            <LazyRoute route="state-gallery" />
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
            current !== "state-gallery" &&
            current !== "quick-entry" &&
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
  <NotificationCenter />
  <ModelOperationTray />
  <HelpPanel {current} />
  <ConfirmDialog />
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
  .setup-focus {
    height: 100vh;
    overflow-y: auto;
    background:
      radial-gradient(50% 40% at 100% 0%, color-mix(in srgb, var(--brand) 14%, transparent), transparent 70%),
      var(--bg);
  }
  .quick-entry-focus {
    height: 100vh;
    overflow: hidden;
    background: var(--surface);
  }
  .quick-entry-locked {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: 0 var(--space-5);
  }
  .quick-entry-locked p {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-sm);
  }
  .quick-entry-locked strong {
    color: var(--text-1);
  }
  .setup-focus:focus-visible {
    outline: none;
  }
  /* Clear of the window controls the desktop shell draws over the top strip. */
  :global(:root[data-desktop-shell]) .setup-focus {
    padding-top: calc(var(--topbar-h) - var(--space-3));
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
