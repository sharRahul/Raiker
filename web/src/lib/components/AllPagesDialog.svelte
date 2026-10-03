<script lang="ts">
  /**
   * Everything that is not the daily work, behind one control.
   *
   * Work that happens on a handful of days — connecting a provider, setting a
   * gate — is reached from here, not from permanent sidebar rows beside the
   * destinations an owner opens many times an hour. Only where a link is drawn
   * differs: deep links resolve, and `nav.ts` holds every destination in
   * `NAV_GROUPS` because `routeFromHash` resolves against it.
   *
   * **REM-POPUP-01 — it is `More`, and it says so.** A gear means "the settings
   * screen"; this is an overflow control and a route launcher, so it is named
   * after what it is, and a direct link to Settings leads its Settings group.
   *
   * **UX-SETPOP-04 — grouped by what an owner comes to do.** Review, Connect,
   * Settings, then Diagnostics & help last, read from `PRODUCT_AREAS` on the
   * route registry rather than from which sidebar group a row used to sit in.
   *
   * **UX-SETPOP-02 — the palette finds; More lists.** This window had a search
   * box of its own beside the command palette's, two places answering "where is
   * that page" with different indexes. The palette already finds every page,
   * every Settings section and the commands beside them, so the box here opens
   * it, and More keeps what a list does better: stable groups and the places you
   * were a moment ago.
   *
   * **UX-SETPOP-03 — on a phone it is a sheet.** Full height, its own scroll,
   * safe-area padding, a Back control where a thumb reaches it, and a line that
   * says where you are, so navigating from it reads as navigation rather than
   * as a desktop dialog shrunk to fit.
   */
  import Icon from "./Icon.svelte";
  import { HUB_TABS, MORE_GROUPS, navItem } from "../nav";
  import { recentPages } from "../recentPages";
  import { settingsSection } from "../settingsSections";
  import { shortcutLabel } from "../shortcutLabel";
  import { activateModalDrawer, type DeactivateModalDrawer } from "../modalDrawer";
  import type { IconName } from "../icons";

  let {
    open = false,
    current = "",
    returnFocusTo = null,
    onClose = () => {},
    onOpenPalette = () => {},
  }: {
    open?: boolean;
    current?: string;
    returnFocusTo?: HTMLElement | null;
    onClose?: () => void;
    /** Hand page and setting search to the command palette. */
    onOpenPalette?: () => void;
  } = $props();

  let panel = $state<HTMLElement>();
  let deactivate: DeactivateModalDrawer | null = null;

  interface Row {
    href: string;
    id: string;
    label: string;
    icon: IconName;
  }

  /**
   * The groups, with Settings' own sections listed under Settings.
   *
   * `HUB_TABS.settings` is the rail's order and the only list allowed to
   * disagree with it, so each section is named and drawn as the rail names and
   * draws it. "Settings" itself is not a row in the group: the direct link leads
   * the group instead, because a bare row would open General while sitting above
   * a row that says General.
   */
  const groups = $derived(
    MORE_GROUPS.map((group) => ({
      id: group.id,
      label: group.label,
      items: [
        ...group.items
          .filter((item) => item.id !== "settings")
          .map<Row>((item) => ({ href: `#/${item.id}`, id: item.id, label: item.label, icon: item.icon })),
        ...(group.id === "settings"
          ? (HUB_TABS.settings ?? []).map<Row>((section) => ({
              // `?tab=`, not `?section=`: `tabFromHash` reads `?tab=`, and a
              // deep link that lands on the wrong page looks exactly like one
              // that works.
              href: `#/settings?tab=${section}`,
              id: `settings-${section}`,
              label: settingsSection(section)?.label ?? section,
              icon: (settingsSection(section)?.icon ?? "settings") as IconName,
            }))
          : []),
      ],
    })),
  );

  /** Read when the window opens, so it reflects the visit that led here. */
  let recent = $state<Row[]>([]);
  const here = $derived(navItem(current));
  const shortcut = shortcutLabel("mod", "K");

  $effect(() => {
    if (!open || panel === undefined) return;
    recent = recentPages(current).map((item) => ({
      href: `#/${item.id}`,
      id: `recent-${item.id}`,
      label: item.label,
      icon: item.icon,
    }));
    deactivate = activateModalDrawer({
      id: "all-pages",
      container: panel,
      returnFocusTo,
      backgroundElements: [],
      onDismiss: () => {
        deactivate = null;
        onClose();
      },
    });
    return () => {
      deactivate?.(false);
      deactivate = null;
    };
  });

  function close() {
    deactivate?.(true);
    deactivate = null;
    onClose();
  }

  function search() {
    deactivate?.(false);
    deactivate = null;
    onClose();
    onOpenPalette();
  }
</script>

{#if open}
  <button type="button" class="scrim" aria-label="Close" onclick={close}></button>
  <div class="panel" bind:this={panel} role="dialog" aria-modal="true" aria-labelledby="all-pages-h">
    <header>
      <!-- UX-SETPOP-03 — on a phone the sheet covers the page, so its way back
           sits where the page's own back control would. -->
      <button type="button" class="btn btn-ghost btn-sm back" onclick={close} aria-label="Back">
        <Icon name="chevron-left" size="sm" /> Back
      </button>
      <div class="title">
        <h2 id="all-pages-h">More</h2>
        <p class="where">You are on <strong>{here.label}</strong></p>
      </div>
      <button type="button" class="btn btn-ghost btn-sm close" onclick={close}>Close</button>
    </header>
    <button type="button" class="find" onclick={search}>
      <Icon name="search" size="sm" />
      <span>Search pages, settings and commands</span>
      <kbd>{shortcut}</kbd>
    </button>
    <div class="groups">
      {#if recent.length > 0}
        <section aria-labelledby="all-pages-recent">
          <h3 id="all-pages-recent">Recent</h3>
          <ul>
            {#each recent as item (item.id)}
              <li>
                <a href={item.href} onclick={close}>
                  <Icon name={item.icon} size="md" />
                  <span class="label">{item.label}</span>
                </a>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
      {#each groups as group (group.id)}
        <section aria-labelledby={`all-pages-${group.id}`}>
          <h3 id={`all-pages-${group.id}`}>{group.label}</h3>
          {#if group.id === "settings"}
            <!-- REM-POPUP-01 — the one destination the old gear icon promised
                 and the window would not go to. Its sections follow as deep
                 links, which is how an owner finds *a* setting; this is how they
                 open *Settings*. -->
            <a
              class="direct"
              href="#/settings"
              class:active={current === "settings"}
              aria-current={current === "settings" ? "page" : undefined}
              onclick={close}
            >
              <Icon name="settings" size="md" />
              <span class="label">Settings</span>
              <span class="direct-hint">General, security, privacy, account and the rest</span>
            </a>
          {/if}
          <ul>
            {#each group.items as item (item.id)}
              <li>
                <a
                  href={item.href}
                  class:active={item.id === current}
                  aria-current={item.id === current ? "page" : undefined}
                  onclick={close}
                >
                  <Icon name={item.icon} size="md" />
                  <span class="label">{item.label}</span>
                </a>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  </div>
{/if}

<style>
  .scrim { position:fixed; inset:0; z-index:var(--z-scrim); border:0; background:var(--overlay); }
  .panel {
    position:fixed; z-index:var(--z-modal); right:var(--space-4); top:calc(var(--topbar-h) + var(--space-2));
    width:min(34rem, calc(100vw - 2 * var(--space-4))); max-height:calc(100vh - var(--topbar-h) - 2 * var(--space-4));
    display:flex; flex-direction:column; gap:var(--space-3);
    padding:var(--space-4); border:1px solid var(--border-strong); border-radius:var(--r-lg);
    background:var(--raised); box-shadow:var(--shadow-2);
  }
  header { display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); }
  .title { display:grid; gap:.1rem; min-width:0; }
  h2 { margin:0; font-size:var(--text-md); }
  .where { margin:0; color:var(--text-3); font-size:var(--text-xs); }
  .where strong { color:var(--text-2); font-weight:600; }
  /* Back is the phone's control; on a desktop the dialog has Close. */
  .back { display:none; }
  .find {
    display:flex; align-items:center; gap:.5rem; width:100%; min-height:2.35rem; padding:.4rem .6rem;
    border:1px solid var(--border); border-radius:var(--r-sm); background:var(--sunken);
    color:var(--text-3); font:inherit; font-size:var(--text-sm); text-align:left; cursor:pointer;
  }
  .find:hover { border-color:var(--border-strong); color:var(--text-2); }
  .find span { flex:1 1 auto; min-width:0; }
  .find kbd { font-family:var(--font-mono, monospace); font-size:var(--text-2xs); color:var(--text-3); border:1px solid var(--border); border-radius:var(--r-xs, 4px); padding:0 .3rem; }
  .groups { overflow-y:auto; overscroll-behavior:contain; display:grid; gap:var(--space-4); }
  h3 { margin:0 0 var(--space-2); color:var(--text-3); font-size:var(--text-2xs); font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
  ul { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fill, minmax(min(13rem, 100%), 1fr)); gap:2px; }
  a { display:flex; align-items:center; gap:.6rem; min-height:2.35rem; padding:.42rem .55rem; border-radius:var(--r-sm); color:var(--text-2); font-size:var(--text-sm); text-decoration:none; }
  a:hover { background:var(--sunken); color:var(--text-1); text-decoration:none; }
  a.active { background:var(--accent-soft); color:var(--accent); font-weight:650; }
  .label { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .direct {
    display:flex; align-items:center; gap:.6rem; min-height:2.6rem; padding:.5rem .6rem; margin-bottom:var(--space-2);
    border:1px solid var(--border); border-radius:var(--r-sm); background:var(--sunken);
    color:var(--text-1); font-size:var(--text-sm); font-weight:600; text-decoration:none;
  }
  .direct:hover { border-color:var(--border-strong); text-decoration:none; }
  .direct.active { border-color:var(--accent); background:var(--accent-soft); color:var(--accent); }
  .direct-hint {
    flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    color:var(--text-3); font-size:var(--text-xs); font-weight:400; text-align:right;
  }
  /* UX-SETPOP-03 — a full-height sheet on a phone: edge to edge, its own scroll,
     clear of the notch and the home indicator, Back where a thumb reaches it. */
  @media (max-width:720px) {
    .panel {
      inset:0; width:auto; max-height:none; border:0; border-radius:0;
      padding:calc(var(--space-3) + env(safe-area-inset-top, 0px)) calc(var(--space-4) + env(safe-area-inset-right, 0px))
        calc(var(--space-4) + env(safe-area-inset-bottom, 0px)) calc(var(--space-4) + env(safe-area-inset-left, 0px));
    }
    .back { display:inline-flex; align-items:center; gap:.3rem; }
    .close { display:none; }
    header { justify-content:flex-start; }
    .direct-hint { display:none; }
    ul { grid-template-columns:1fr; }
    a { min-height:2.75rem; }
  }
</style>
