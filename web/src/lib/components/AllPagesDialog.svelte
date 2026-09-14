<script lang="ts">
  /**
   * Everything that is not the daily work, behind one control.
   *
   * The sidebar used to carry eight rows — Approvals, Permissions, Models,
   * Extensions, Observability, Guide, Settings — for work that happens on a
   * handful of days: you connect a provider once, set a gate once, and come
   * back when something needs changing. They were permanent furniture beside
   * the six destinations an owner opens many times an hour.
   *
   * They live here now, reached from the gear in the top right. The routes
   * themselves are untouched — `#/models` still renders Models, deep links
   * still resolve, and `nav.ts` still holds every destination in `NAV_GROUPS`
   * because `routeFromHash` resolves against it. What changed is only where a
   * link to them is drawn.
   *
   * Settings' own sections are listed too, so this answers "where is that
   * setting" without making the owner open Settings and then hunt its rail.
   *
   * **REM-POPUP-01 — it is `More`, and it says so.** The trigger was a gear and
   * the heading was "Settings & pages", which is one control making two
   * promises: a gear means "the settings screen" everywhere else an owner has
   * used a computer, and this opens a route launcher whose largest group is
   * pages that are not settings at all. Worse, the one thing the icon named was
   * the one row deliberately missing — Settings itself was omitted because its
   * sections are listed below, so pressing a gear could not open Settings.
   *
   * The control is an overflow control, so it is named after what it is, and a
   * direct link to Settings leads the window. Nothing about the routes, the
   * groups or the deep links changed.
   */
  import Icon from "./Icon.svelte";
  import { HUB_GROUPS, HUB_TABS } from "../nav";
  import { activateModalDrawer, type DeactivateModalDrawer } from "../modalDrawer";

  let {
    open = false,
    current = "",
    returnFocusTo = null,
    onClose = () => {},
  }: {
    open?: boolean;
    current?: string;
    returnFocusTo?: HTMLElement | null;
    onClose?: () => void;
  } = $props();

  let panel = $state<HTMLElement>();
  let deactivate: DeactivateModalDrawer | null = null;
  let query = $state("");

  /**
   * The settings sections, as their own group.
   *
   * `HUB_TABS.settings` is the rail's order and the only list that is allowed
   * to disagree with it — the comment on that array says why. Reading it here
   * rather than restating it means this window cannot drift from the rail.
   */
  const SETTINGS_LABELS: Record<string, string> = {
    general: "General",
    notification: "Notifications",
    personalisation: "Personalisation",
    security: "Security & sign-in",
    privacy: "Privacy",
    account: "Account",
    "web-access": "Web access",
    "git-credential": "Git credentials",
    runtime: "Runtime",
    updates: "Updates",
  };

  const groups = $derived.by(() => {
    const q = query.trim().toLowerCase();
    const base = HUB_GROUPS.map((group) => ({
      id: group.id,
      label: group.label,
      // "Settings" itself is not listed as a page: every one of its sections is
      // a row in the group below, so the bare link would open General while
      // sitting above a row that says General.
      items: group.items
        .filter((item) => item.id !== "settings")
        .map((item) => ({
          href: `#/${item.id}`,
          id: item.id,
          label: item.label,
          hint: item.hint,
          icon: item.icon,
        })),
    })).filter((group) => group.items.length > 0);
    base.push({
      id: "settings-sections" as never,
      label: "Settings",
      // `?tab=`, not `?section=`. This emitted `?section=` and `tabFromHash`
      // reads `?tab=`, so every one of these ten rows opened Settings on
      // **General** — and since Settings left the sidebar, the gear's window is
      // the only route to it, so the whole destination was reachable only at its
      // first panel. Exactly the failure `nav.test.ts` names: "a deep link that
      // lands on the wrong page looks exactly like one that works."
      items: (HUB_TABS.settings ?? []).map((section) => ({
        href: `#/settings?tab=${section}`,
        id: `settings-${section}`,
        label: SETTINGS_LABELS[section] ?? section,
        hint: "",
        icon: "settings" as never,
      })),
    });
    if (q === "") return base;
    return base
      .map((group) => ({
        ...group,
        items: group.items.filter(
          (item) =>
            item.label.toLowerCase().includes(q) || item.hint.toLowerCase().includes(q),
        ),
      }))
      .filter((group) => group.items.length > 0);
  });

  $effect(() => {
    if (!open || panel === undefined) return;
    query = "";
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
</script>

{#if open}
  <button type="button" class="scrim" aria-label="Close" onclick={close}></button>
  <div class="panel" bind:this={panel} role="dialog" aria-modal="true" aria-labelledby="all-pages-h">
    <header>
      <h2 id="all-pages-h">More</h2>
      <button type="button" class="btn btn-ghost btn-sm" onclick={close}>Close</button>
    </header>
    <label class="find">
      <Icon name="search" size="sm" />
      <input bind:value={query} placeholder="Find a page or setting" aria-label="Find a page or setting" />
    </label>
    <!-- REM-POPUP-01 — the one destination the old gear icon promised and the
         window would not go to. Its ten sections are still listed below as deep
         links, which is how an owner finds *a* setting; this is how they open
         *Settings*. Above the search box rather than in a group, because it is
         the answer to "I pressed this to change something" and a row in the
         last group is not. Hidden while a query is running: a search is a
         request to see matches, and a fixed row that is not one of them is the
         same noise the groups fold away to avoid. -->
    {#if query.trim() === ""}
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
    <div class="groups">
      {#each groups as group (group.id)}
        <section aria-labelledby={`all-pages-${group.id}`}>
          <h3 id={`all-pages-${group.id}`}>{group.label}</h3>
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
      {#if groups.length === 0}
        <p class="none">Nothing matches “{query}”.</p>
      {/if}
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
  h2 { margin:0; font-size:var(--text-md); }
  .find { display:flex; align-items:center; gap:.5rem; padding:.4rem .6rem; border:1px solid var(--border); border-radius:var(--r-sm); background:var(--sunken); color:var(--text-3); }
  .find input { width:100%; min-width:0; border:0; outline:0; background:transparent; color:var(--text-1); font:inherit; font-size:var(--text-sm); }
  .groups { overflow-y:auto; display:grid; gap:var(--space-4); }
  h3 { margin:0 0 var(--space-2); color:var(--text-3); font-size:var(--text-2xs); font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
  ul { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fill, minmax(min(13rem, 100%), 1fr)); gap:2px; }
  a { display:flex; align-items:center; gap:.6rem; min-height:2.35rem; padding:.42rem .55rem; border-radius:var(--r-sm); color:var(--text-2); font-size:var(--text-sm); text-decoration:none; }
  a:hover { background:var(--sunken); color:var(--text-1); text-decoration:none; }
  a.active { background:var(--accent-soft); color:var(--accent); font-weight:650; }
  .label { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .direct {
    display:flex; align-items:center; gap:.6rem; min-height:2.6rem; padding:.5rem .6rem;
    border:1px solid var(--border); border-radius:var(--r-sm); background:var(--sunken);
    color:var(--text-1); font-size:var(--text-sm); font-weight:600; text-decoration:none;
  }
  .direct:hover { border-color:var(--border-strong); text-decoration:none; }
  .direct.active { border-color:var(--accent); background:var(--accent-soft); color:var(--accent); }
  .direct-hint {
    flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    color:var(--text-3); font-size:var(--text-xs); font-weight:400; text-align:right;
  }
  .none { margin:0; color:var(--text-3); font-size:var(--text-sm); }
  @media (max-width:720px) {
    .panel { right:var(--space-2); left:var(--space-2); width:auto; }
  }
</style>
