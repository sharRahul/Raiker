<script lang="ts">
  import { onMount } from "svelte";
  import type { Notification as RaikerNotification, ProjectsList } from "../apiTypes";
  import { api } from "../api";
  import { relativeTime } from "../format";
  import Icon from "./Icon.svelte";
  import StopSwitch from "./StopSwitch.svelte";
  import ThemeToggle from "./ThemeToggle.svelte";

  let { title, hint, connecting = false, projects = null, onProjectSelect = undefined }: {
    title: string;
    hint: string;
    connecting?: boolean;
    projects?: ProjectsList | null;
    onProjectSelect?: (projectId: string | null) => void;
  } = $props();

  // Owner-scoped notifications, reachable from every route. Reads are
  // best-effort: a failed read shows an empty panel, never a broken shell.
  let notifications = $state<RaikerNotification[]>([]);
  let panelOpen = $state(false);
  let marking = $state(false);
  const unread = $derived(notifications.filter((n) => !n.read));

  async function loadNotifications() {
    try {
      notifications = await api.notifications();
    } catch {
      // Keep the last known list.
    }
  }

  function togglePanel() {
    panelOpen = !panelOpen;
    if (panelOpen) void loadNotifications();
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

  onMount(loadNotifications);
</script>

<header class="topbar">
  <div class="page-id"><h1 class="page-title">{title}</h1><p class="page-hint">{hint}</p></div>
  <div class="status" role="status" aria-live="polite">
    {#if connecting}<span class="pill">Connecting…</span>
    {:else if projects !== null && projects.projects.length > 0}
      <select class="project-select" aria-label="Active project" value={projects.active_project_id ?? ""} onchange={(e) => onProjectSelect?.((e.currentTarget as HTMLSelectElement).value || null)}>
        <option value="">No project</option>{#each projects.projects as p (p.project_id)}<option value={p.project_id}>{p.name}</option>{/each}
      </select>
    {/if}
  </div>
  <div class="controls">
    <div class="bell-wrap">
      <button
        type="button"
        class="btn btn-ghost bell"
        aria-label={unread.length > 0 ? `Notifications (${unread.length} unread)` : "Notifications"}
        aria-expanded={panelOpen}
        onclick={togglePanel}
      >
        <Icon name="bell" size={17} />
        {#if unread.length > 0}<span class="unread-count">{unread.length}</span>{/if}
      </button>
      {#if panelOpen}
        <button
          type="button"
          class="panel-backdrop"
          aria-label="Close notifications"
          tabindex="-1"
          onclick={() => (panelOpen = false)}
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
    <ThemeToggle />
    <StopSwitch />
  </div>
</header>

<style>
  .topbar{height:var(--topbar-h);display:flex;align-items:center;gap:var(--space-4);padding:0 var(--space-5);border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0}.page-id{min-width:0}.page-title{font-size:1rem;margin:0;line-height:1.2}.page-hint{font-size:.72rem;color:var(--text-3);margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.status{display:flex;align-items:center;gap:.45rem;margin-left:auto}.pill,.project-select{font-size:.74rem;font-weight:600;padding:.18rem .6rem;border-radius:var(--r-pill);border:1px solid var(--neutral-border);background:var(--neutral-soft);color:var(--text-2)}.controls{display:flex;align-items:center;gap:.5rem}
  .bell-wrap{position:relative}
  .bell{position:relative;padding:.35rem .5rem}
  .unread-count{position:absolute;top:-2px;right:-2px;min-width:1rem;height:1rem;display:grid;place-items:center;font-size:.62rem;font-weight:700;border-radius:var(--r-pill);background:var(--danger);color:#fff;padding:0 .2rem}
  .panel-backdrop{position:fixed;inset:0;z-index:55;border:0;background:transparent;cursor:default}
  .panel{position:absolute;right:0;top:calc(100% + 6px);z-index:60;width:min(21rem,86vw);border:1px solid var(--border);border-radius:var(--r-md);background:var(--raised);box-shadow:var(--shadow-2);padding:var(--space-3)}
  @media(max-width:720px){.panel{position:fixed;left:var(--space-3);right:var(--space-3);top:calc(var(--topbar-h) + 6px);width:auto}}
  .panel-head{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);margin-bottom:var(--space-2)}
  .panel-empty{color:var(--text-3);font-size:.84rem;margin:0}
  .panel ul{list-style:none;margin:0;padding:0;display:grid;gap:.5rem;max-height:19rem;overflow:auto}
  .panel li{display:grid;gap:.1rem;font-size:.82rem;border-left:2px solid transparent;padding-left:.5rem}
  .panel li.unread{border-left-color:var(--accent)}
  .panel li span{color:var(--text-2)}
  .panel li time{color:var(--text-3);font-size:.72rem}
  @media(max-width:900px){.page-hint{display:none}}@media(max-width:720px){.topbar{gap:var(--space-2);padding:0 var(--space-3)}.page-title{font-size:.9rem}.status{display:none}}
  @media (min-width:640px) and (max-width:1023px){.topbar{padding-left:calc(var(--space-3) + 3rem)}}
</style>
