<script lang="ts">
  import { onMount } from "svelte";
  import type { Notification as RaikerNotification } from "../apiTypes";
  import { api } from "../api";
  import { relativeTime } from "../format";
  import Icon from "./Icon.svelte";
  import HostControl from "./HostControl.svelte";
  import StopSwitch from "./StopSwitch.svelte";
  import { WORK_MODES } from "../nav";
  import { shortcutLabel, shortcutSpoken } from "../shortcutLabel";

  // The top bar carries the shell's own controls only. The project selector
  // moved into Build, where the execution boundary it sets is visible for the
  // whole session; the theme toggle moved into Settings, where a preference
  // belongs. A global selector that silently retargeted every surface was the
  // thing worth removing: nothing about a page told you which project it meant.
  let { title, hint, current = "", quietHeader = false, connecting = false,
    navigationOpen = true, compactNavigation = false, onNavigationToggle = () => {},
    onOpenAllPages = () => {}, onOpenPalette = () => {} }: {
    title: string;
    hint: string;
    /** The active route id, so the Work-mode switch can mark itself. */
    current?: string;
    /** Work surfaces hide the route title and hint; see the markup (VIS-03). */
    quietHeader?: boolean;
    connecting?: boolean;
    navigationOpen?: boolean;
    compactNavigation?: boolean;
    onNavigationToggle?: (trigger: HTMLElement) => void;
    /** Opens the window holding Settings and every page not on the rail. */
    onOpenAllPages?: (trigger: HTMLElement) => void;
    /** Opens the command palette. */
    onOpenPalette?: () => void;
  } = $props();

  // VIS-01 — Approvals came off the rail. A decision waiting on you is not a
  // place you navigate to, it is a thing that arrives, so it is a counted
  // button here: visible from every route rather than only when the sidebar is.
  let pendingApprovals = $state(0);
  async function loadApprovals() {
    try {
      pendingApprovals = (await api.approvals("pending")).length;
    } catch {
      // A failed read leaves the last known count. Never a broken shell.
    }
  }

  // Owner-scoped notifications, reachable from every route. Reads are
  // best-effort: a failed read shows an empty panel, never a broken shell.
  let notifications = $state<RaikerNotification[]>([]);
  let panelOpen = $state(false);
  let marking = $state(false);
  let notificationTrigger = $state<HTMLButtonElement>();
  const unread = $derived(notifications.filter((n) => !n.read));

  async function loadNotifications() {
    try {
      notifications = await api.notifications();
    } catch {
      // Keep the last known list.
    }
  }

  function togglePanel() {
    if (panelOpen) {
      closePanel();
    } else {
      panelOpen = true;
      void loadNotifications();
    }
  }

  function closePanel() {
    panelOpen = false;
    notificationTrigger?.focus();
  }

  async function markAllRead() {
    marking = true;
    try {
      for (const n of unread) await api.markNotificationRead(n.notification_id);
      await loadNotifications();
    } catch {
      await loadNotifications();
    } finally {
      marking = false;
    }
  }

  onMount(() => {
    void loadNotifications();
    void loadApprovals();
  });

  $effect(() => {
    if (!panelOpen) return;
    const closeForEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closePanel();
    };
    window.addEventListener("keydown", closeForEscape);
    return () => window.removeEventListener("keydown", closeForEscape);
  });
</script>

<header class="topbar">
  <!-- On desktop this collapses to a rail rather than hiding: the icons stay,
       so "Hide"/"Show" described a behaviour the control no longer has. -->
  <div class="navigation-reveal-zone" data-navigation-open={navigationOpen}>
    <button
      type="button"
      class="btn btn-ghost navigation-toggle"
      aria-label={compactNavigation ? (navigationOpen ? "Close navigation" : "Open navigation") : (navigationOpen ? "Collapse navigation" : "Expand navigation")}
      aria-controls="all-navigation"
      aria-expanded={navigationOpen}
      onclick={(event) => onNavigationToggle(event.currentTarget)}
    ><Icon name="panel" size="md" /></button>
  </div>
  <!-- VIS-03 — on a work surface the mode switch beside this already says
       where you are, so the title repeated it and the hint explained a route
       the owner is already inside. Both go, and the transcript gets the room.
       The heading still exists for screen readers and for the document outline;
       it is only visually hidden. Operational pages keep their full header. -->
  <div class="page-id" class:quiet={quietHeader}>
    <h1 class="page-title">{title}</h1>
    <p class="page-hint">{hint}</p>
  </div>
  <!-- VIS-02 — Raiker's product story is Assistant + Agent, and the shell said
       so only by listing two rows among nine. These are modes, not destinations:
       one control, always in the same place, showing which one you are in.

       VIS2-03 — and there are three of them. Drawing Chat and Build here while
       Design lived behind a gear said Design was a different kind of thing; it
       is not, it is the third way to give Raiker something to do. The list comes
       from `WORK_MODES` so the rail and this control cannot disagree. -->
  <nav class="modes" aria-label="Work mode">
    {#each WORK_MODES as workMode (workMode.id)}
      <a
        href={workMode.hash}
        class="mode"
        class:active={current === workMode.id}
        aria-label={workMode.label}
        aria-current={current === workMode.id ? "page" : undefined}
      ><Icon name={workMode.icon} size="sm" /><span class="mode-label">{workMode.label}</span></a>
    {/each}
  </nav>
  <div class="status" role="status" aria-live="polite">
    {#if connecting}<span class="pill">Connecting…</span>{/if}
  </div>
  <div class="controls">
    <button
      type="button"
      class="btn btn-ghost palette-button"
      aria-label={`Search and commands (${shortcutSpoken("mod", "K")})`}
      onclick={onOpenPalette}
    ><Icon name="search" size="md" /><kbd class="palette-key" aria-hidden="true"
      >{shortcutLabel("mod", "K")}</kbd></button>
    <a
      href="#/approvals"
      class="btn btn-ghost approvals-link"
      class:waiting={pendingApprovals > 0}
      aria-label={pendingApprovals > 0
        ? `Approvals (${pendingApprovals} waiting on you)`
        : "Approvals"}
    >
      <Icon name="approvals" size="md" />
      {#if pendingApprovals > 0}<span class="approval-count">{pendingApprovals}</span>{/if}
    </a>
    <div class="bell-wrap">
      <button
        type="button"
        class="btn btn-ghost bell"
        aria-label={unread.length > 0 ? `Notifications (${unread.length} unread)` : "Notifications"}
        aria-expanded={panelOpen}
        onclick={togglePanel}
        bind:this={notificationTrigger}
      >
        <Icon name="bell" size="md" />
        {#if unread.length > 0}<span class="unread-count">{unread.length}</span>{/if}
      </button>
      {#if panelOpen}
        <button
          type="button"
          class="panel-backdrop"
          aria-label="Close notifications"
          tabindex="-1"
          onclick={closePanel}
        ></button>
        <section class="panel" aria-label="Notification panel">
          <div class="panel-head">
            <strong>Notifications</strong>
            {#if unread.length > 0}
              <button type="button" class="btn btn-ghost btn-sm" onclick={markAllRead} disabled={marking}>
                {marking ? "Marking…" : "Mark all read"}
              </button>
            {/if}
          </div>
          {#if notifications.length === 0}
            <p class="panel-empty">Nothing to review.</p>
          {:else}
            <ul>
              {#each notifications.slice(0, 8) as n (n.notification_id)}
                <li class:unread={!n.read}>
                  <strong>{n.title}</strong>
                  <span>{n.body}</span>
                  <time title={n.created_at}>{relativeTime(n.created_at)}</time>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {/if}
    </div>
    <!-- Settings, and with it every destination that left the sidebar. The gear
         is the last thing before the host controls because it is the one an
         owner reaches for least often and knows where to find. -->
    <button
      type="button"
      class="btn btn-ghost"
      aria-label="Settings and pages"
      aria-haspopup="dialog"
      onclick={(event) => onOpenAllPages(event.currentTarget)}
    ><Icon name="settings" size="md" /></button>
    <span class="cluster-rule" aria-hidden="true"></span>
    <div class="runtime-cluster">
      <HostControl />
      <StopSwitch />
    </div>
  </div>
</header>

<style>
  .topbar{height:var(--topbar-h);display:flex;align-items:center;gap:var(--space-3);padding:0 var(--space-5);border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0}.navigation-reveal-zone{width:48px;height:48px;margin-left:-.75rem;display:grid;place-items:center}.navigation-toggle{transition:opacity var(--motion-shell) var(--ease-shell),background var(--motion-fast) var(--ease)}.navigation-reveal-zone[data-navigation-open="false"] .navigation-toggle{opacity:.28}.navigation-reveal-zone:hover .navigation-toggle,.navigation-toggle:focus-visible{opacity:1!important}.page-id{min-width:0}
  /* Visually hidden, not removed: the page keeps exactly one h1 and the
     document outline is unchanged. */
  .page-id.quiet{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
  .page-title{font-size:var(--text-base);margin:0;line-height:1.2}.page-hint{font-size:var(--text-xs);color:var(--text-3);margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status{display:flex;align-items:center;gap:.45rem;margin-left:auto}.pill{font-size:var(--text-xs);font-weight:600;padding:.18rem .6rem;border-radius:var(--r-pill);border:1px solid var(--neutral-border);background:var(--neutral-soft);color:var(--text-2)}.controls{display:flex;align-items:center;gap:.5rem}
  /* VIS2-03 — navigation and attention on one side of the rule, where the
     workspace runs and how it is stopped on the other. */
  .cluster-rule{width:1px;height:1.35rem;background:var(--border);margin:0 .1rem;flex-shrink:0}
  .runtime-cluster{display:flex;align-items:center;gap:.5rem}
  /* VIS-02 — a segmented control, not two links: the pair reads as one choice
     with a current value. Sentence case and no tracking (VIS-06). */
  .modes{display:flex;gap:2px;padding:2px;margin-left:var(--space-3);border:1px solid var(--border);border-radius:var(--r-pill);background:var(--sunken)}
  .modes .mode{display:inline-flex;align-items:center;gap:.3rem;padding:.24rem .7rem;border-radius:var(--r-pill);font-size:var(--text-sm);font-weight:600;color:var(--text-2);text-decoration:none;white-space:nowrap;transition:background var(--motion-fast) var(--ease),color var(--motion-fast) var(--ease)}
  .modes .mode:hover{color:var(--text-1);text-decoration:none}
  .modes .mode.active{background:var(--raised);color:var(--text-1);box-shadow:var(--shadow-1)}
  .palette-button{display:inline-flex;align-items:center;gap:.4rem}
  .palette-key{font-family:var(--font-mono);font-size:var(--text-2xs);color:var(--text-3);border:1px solid var(--border);border-radius:var(--r-xs);padding:.05rem .3rem;background:var(--sunken)}
  /* VIS-15 — the resting state is neutral. Colour arrives only when something
     is actually waiting on the owner, which is what makes it mean anything. */
  .approvals-link{position:relative;display:inline-grid;place-items:center;padding:.35rem .5rem}
  .approvals-link.waiting{color:var(--accent)}
  .approval-count{position:absolute;top:-2px;right:-2px;min-width:1rem;height:1rem;display:grid;place-items:center;font-size:var(--text-2xs);font-weight:700;border-radius:var(--r-pill);background:var(--accent);color:var(--text-inverse);padding:0 .2rem}
  .bell-wrap{position:relative}
  .bell{position:relative;padding:.35rem .5rem}
  .unread-count{position:absolute;top:-2px;right:-2px;min-width:1rem;height:1rem;display:grid;place-items:center;font-size:var(--text-2xs);font-weight:700;border-radius:var(--r-pill);background:var(--danger);color:var(--text-inverse);padding:0 .2rem}
  .panel-backdrop{position:fixed;inset:0;z-index:55;border:0;background:transparent;cursor:default}
  .panel{position:absolute;right:0;top:calc(100% + 6px);z-index:60;width:min(21rem,86vw);border:1px solid var(--border);border-radius:var(--r-md);background:var(--raised);box-shadow:var(--shadow-2);padding:var(--space-3)}
  @media(max-width:720px){.panel{position:fixed;left:var(--space-3);right:var(--space-3);top:calc(var(--topbar-h) + 6px);width:auto}}
  .panel-head{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);margin-bottom:var(--space-2)}
  .panel-empty{color:var(--text-3);font-size:var(--text-sm);margin:0}
  .panel ul{list-style:none;margin:0;padding:0;display:grid;gap:.5rem;max-height:19rem;overflow:auto}
  .panel li{display:grid;gap:.1rem;font-size:var(--text-sm);border-left:2px solid transparent;padding-left:.5rem}
  .panel li.unread{border-left-color:var(--accent)}
  .panel li span{color:var(--text-2)}
  .panel li time{color:var(--text-3);font-size:var(--text-xs)}
  @media(max-width:1100px){.palette-key{display:none}}
  @media(max-width:900px){.page-hint{display:none}}
  @media(max-width:720px){
    .topbar{gap:var(--space-2);padding:0 var(--space-3)}
    .page-title{font-size:var(--text-md)}
    .status{display:none}
    .modes{margin-left:var(--space-2)}
    .modes .mode{padding:.24rem .6rem}
  }
  /* Below this the title and the mode switch compete for the same row; the
     title loses, because the mode switch is the only way back to the two
     surfaces the product is for. */
  @media(max-width:560px){.page-id{display:none}}
  /* At 375 the six controls plus the mode switch are wider than the bar, and
     the bar scrolls rather than the page — which is worse than either, because
     nothing tells you the rest is there. The palette button is the one to lose:
     it is a keyboard affordance (Ctrl/Cmd+K), there is no keyboard here, and
     everything it reaches is in the drawer and the gear's window. */
  @media(max-width:560px){.palette-button{display:none}}
  @media(max-width:480px){
    .modes .mode-label{display:none}
    .modes .mode{padding:.3rem .5rem}
    .cluster-rule{display:none}
  }
  @media(max-width:420px){.modes{margin-left:var(--space-1)}.controls{gap:.3rem}}
  @media(max-width:720px){.navigation-reveal-zone{margin-left:-.5rem}}
</style>
