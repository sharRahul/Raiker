<script lang="ts">
  import Icon from "./Icon.svelte";
  import Logo from "./Logo.svelte";
  import { SIDEBAR_GROUPS, type NavGroup, type NavGroupId } from "../nav";
  import { activateModalDrawer, type DeactivateModalDrawer } from "../modalDrawer";

  const STORAGE_KEY = "raiker.navigation.groups";
  const COLLAPSIBLE_IDS = new Set<NavGroupId>(["knowledge"]);

  let { current, desktopOpen = true, drawerOpen = false, compact = false, returnFocusTo = null,
    backgroundElement = undefined, onDrawerClose = () => {} }: {
    current: string; desktopOpen?: boolean; drawerOpen?: boolean; compact?: boolean;
    returnFocusTo?: HTMLElement | null; backgroundElement?: HTMLElement; onDrawerClose?: () => void;
  } = $props();

  function readExpanded(): NavGroupId[] {
    const defaults: NavGroupId[] = ["knowledge", "manage", "observe", "support"];
    if (typeof localStorage === "undefined") return defaults;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === null) return defaults;
      const value: unknown = JSON.parse(saved);
      return Array.isArray(value)
        ? value.filter((id): id is NavGroupId => typeof id === "string" && COLLAPSIBLE_IDS.has(id as NavGroupId))
        : [];
    } catch { return []; }
  }

  let expanded = $state<NavGroupId[]>(readExpanded());
  let navigationElement = $state<HTMLElement>();
  let deactivate: DeactivateModalDrawer | null = null;
  const activeGroup = $derived(SIDEBAR_GROUPS.find((group) => group.items.some((item) => item.id === current)));

  /** True while the desktop sidebar is showing only icons. */
  const rail = $derived(!compact && !desktopOpen);
  function isOpen(group: NavGroup): boolean {
    // A rail hides the group headers, so a folded group would hide its icons
    // with nothing left to unfold it. Everything is open at rail width.
    if (rail) return true;
    return !group.collapsible || activeGroup?.id === group.id || expanded.includes(group.id);
  }
  function toggleGroup(group: NavGroup) {
    if (!group.collapsible || activeGroup?.id === group.id) return;
    expanded = expanded.includes(group.id) ? expanded.filter((id) => id !== group.id) : [...expanded, group.id];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(expanded));
  }
  function closeNavigation(restoreFocus = true) {
    deactivate?.(restoreFocus); deactivate = null; onDrawerClose();
  }

  $effect(() => {
    if (!compact || !drawerOpen || navigationElement === undefined) return;
    deactivate = activateModalDrawer({ id: "navigation", container: navigationElement, returnFocusTo,
      backgroundElements: backgroundElement === undefined ? [] : [backgroundElement], onDismiss: () => closeNavigation(true) });
    return () => { deactivate?.(false); deactivate = null; };
  });
</script>

{#if compact && drawerOpen}<button type="button" class="drawer-scrim" aria-label="Close navigation" onclick={() => closeNavigation()}></button>{/if}

<!-- `inert`/`aria-hidden` used to include the collapsed desktop case, because
     collapsed meant the sidebar was translated off screen. A rail is on screen
     and clickable, so only the closed mobile drawer is hidden from anyone. -->
<nav id="all-navigation" class="sidebar" class:open={drawerOpen} class:desktop-hidden={!compact && !desktopOpen}
  aria-label="All navigation" aria-hidden={compact && !drawerOpen ? "true" : undefined}
  inert={compact && !drawerOpen} bind:this={navigationElement}>
  <button type="button" class="drawer-close btn btn-ghost" onclick={() => closeNavigation()}>Close</button>
  <a class="brand" href="#/home"><Logo size={30} /><span class="brand-text"><span class="brand-name">Raiker</span><span class="brand-sub">Governed agent</span></span></a>

  <div class="navigation-sections">
    {#each SIDEBAR_GROUPS as group (group.id)}
      <section class="group">
        {#if group.collapsible}
          <button type="button" class="group-toggle" aria-label={group.label} aria-expanded={isOpen(group)} aria-controls={`navigation-group-${group.id}`} onclick={() => toggleGroup(group)}>
            <span>{group.label}</span><Icon name="chevron-right" size="sm" />
          </button>
        {:else}<p class="group-label">{group.label}</p>{/if}
        {#if isOpen(group)}
          <ul id={`navigation-group-${group.id}`}>
            {#each group.items as item (item.id)}
              {#if !(compact && item.id === "brain")}
                <li><a href={`#/${item.id}`} class="nav-link" class:active={current === item.id}
                  aria-current={current === item.id ? "page" : undefined} aria-label={item.label} title={item.hint}
                  onclick={() => { if (compact) closeNavigation(false); }}>
                  <Icon name={item.icon} size="lg" filled={current === item.id} /><span>{item.label}</span>
                </a></li>
              {/if}
            {/each}
          </ul>
        {/if}
      </section>
    {/each}
  </div>
</nav>

<style>
  .sidebar { width:var(--sidebar-w); flex-shrink:0; display:flex; flex-direction:column; min-height:0; overflow-y: auto; overflow-x:hidden; padding:var(--space-4) var(--space-3); border-right:1px solid var(--border); background:var(--surface); position: relative; transition:width var(--motion-shell) var(--ease-shell),padding var(--motion-shell) var(--ease-shell),transform var(--motion-shell) var(--ease-shell); }

  /* Collapsed used to mean *gone* — width 0 and translated off screen — so the
     only way to see where you were was to bring the whole 256px back. It is a
     rail now: the icons stay, the active row stays marked, and the labels are
     what the width buys you. Same control, same toggle; what changes is that
     collapsing costs you the words rather than the navigation. */
  .sidebar.desktop-hidden { width:var(--sidebar-rail-w); padding-inline:var(--space-2); }
  .sidebar.desktop-hidden .brand-text,
  .sidebar.desktop-hidden .group-label,
  .sidebar.desktop-hidden .group-toggle,
  .sidebar.desktop-hidden .nav-link span { display:none; }
  .sidebar.desktop-hidden .brand { justify-content:center; padding-inline:0; }
  .sidebar.desktop-hidden .nav-link { justify-content:center; padding-inline:0; }
  .drawer-scrim,.drawer-close { display:none; }
  .brand { display:flex; align-items:center; gap:.6rem; padding:.25rem .5rem var(--space-3); text-decoration:none; }
  .brand:hover { text-decoration:none; }
  .brand-text { display:flex; flex-direction:column; line-height:1.15; }
  /* VIS-07 — the brand should not rest on a letter-spaced wordmark. .45em was
     spacing the name out until it read as a logotype by force; the mark beside
     it is the identity. */
  .brand-name { font-weight:800; font-size:var(--text-sm); letter-spacing:.14em; text-transform:uppercase; color:var(--text-1); }
  .brand-sub { font-size:var(--text-2xs); font-weight:600; letter-spacing:normal; color:var(--text-3); }
  .navigation-sections { display:grid; gap:var(--space-2); }
  .group { position:relative; }
  /* VIS-06 — a navigation group label in caps at 2xs with .09em tracking is
     four typographic devices doing one job. Sentence case at xs, and the colour
     and weight are what separate it from the rows beneath. */
  .group-label,.group-toggle { width:100%; min-height:2rem; margin:0; padding:.35rem .55rem; color:var(--text-3); font-size:var(--text-xs); font-weight:650; letter-spacing:normal; }
  .group-toggle { display:grid; grid-template-columns:1fr auto auto; align-items:center; gap:.35rem; border:0; background:transparent; text-align:left; }
  .group-toggle:hover { background:var(--sunken); color:var(--text-1); }
  .group-toggle[aria-expanded="true"] :global(svg) { transform:rotate(90deg); }
  ul { list-style:none; margin:0; padding:0; display:grid; gap:2px; }
  .nav-link { display:flex; align-items:center; gap:.65rem; min-height:2.35rem; padding:.42rem .55rem; border-radius:var(--r-sm); color:var(--text-2); font-size:var(--text-md); font-weight:550; text-decoration:none; transition:background var(--motion-fast) var(--ease),color var(--motion-fast) var(--ease); }
  .nav-link:hover { background:var(--sunken); color:var(--text-1); text-decoration:none; }
  /* VIS2-08 — the current row carried five cues at once: a group bar in the
     gutter, a tinted background, accent text, a heavier weight, and the word
     "Current" beside the group name. Five ways of saying one thing is not
     emphasis, it is noise, and the row still had to be read to find out which
     one it was. Two remain, and they are the two that survive a rail with no
     labels: the tinted row, and the filled glyph. */
  .nav-link.active { background:var(--accent-soft); color:var(--text-1); }
  @media (max-width:1023px) {
    .drawer-scrim { display:block; position:fixed; inset:0; z-index:90; border:0; background:var(--overlay); }
    .sidebar,.sidebar.desktop-hidden { position:fixed; inset:0 auto 0 0; z-index:100; width:min(19rem,84vw); padding:var(--space-4) var(--space-3); border-right-width:1px; transform:translateX(-105%); box-shadow:var(--shadow-2); }
    .sidebar.open { transform:translateX(0); }
    .drawer-close { display:inline-flex; align-self:flex-end; }
  }
</style>
